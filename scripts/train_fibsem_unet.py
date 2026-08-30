from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLBACKEND", "Agg")
RUNTIME_DEPS = PROJECT / "runtime_deps"
DEPS = PROJECT / ".deps"
if RUNTIME_DEPS.exists():
    sys.path.insert(0, str(RUNTIME_DEPS))
elif DEPS.exists():
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import pandas as pd
import torch
from PIL import Image
from scipy import ndimage as ndi
from skimage import exposure, filters, morphology
from torch import nn
from torch.utils.data import DataLoader, Dataset

from morphometry.unet import build_unet


SEED = 20260830
MATERIALS = ["HPC22", "HPC30", "HPC45"]


def seed_everything() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)


def normalize_image(path: Path) -> np.ndarray:
    image = np.asarray(Image.open(path), dtype=np.float32)
    lo, hi = np.percentile(image, [1, 99])
    return exposure.rescale_intensity(image, in_range=(lo, hi), out_range=(0, 1)).astype(np.float32)


class FibsemDataset(Dataset):
    def __init__(self, root: Path, split: str, augment: bool = False):
        self.split = split
        self.augment = augment
        image_dir, mask_dir = root / split / "images", root / split / "masks"
        images = {path.stem: path for path in image_dir.glob("*.tif")}
        masks = {path.stem: path for path in mask_dir.glob("*.png")}
        self.stems = sorted(set(images) & set(masks))
        self.images = [normalize_image(images[stem]) for stem in self.stems]
        self.masks = [
            (np.asarray(Image.open(masks[stem]).convert("L")) > 127).astype(np.float32)
            for stem in self.stems
        ]
        self.materials = [stem.split("-")[1] for stem in self.stems]

    def __len__(self) -> int:
        return len(self.stems)

    def __getitem__(self, index: int):
        image, mask = self.images[index], self.masks[index]
        if self.augment:
            transform = random.randrange(8)
            rotations, flip = transform % 4, transform >= 4
            image, mask = np.rot90(image, rotations), np.rot90(mask, rotations)
            if flip:
                image, mask = np.fliplr(image), np.fliplr(mask)
        return (
            torch.from_numpy(np.ascontiguousarray(image))[None],
            torch.from_numpy(np.ascontiguousarray(mask))[None],
            self.stems[index], self.materials[index],
        )


def loss_function(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    bce = nn.functional.binary_cross_entropy_with_logits(logits, target)
    probability = torch.sigmoid(logits)
    axes = (1, 2, 3)
    intersection = (probability * target).sum(dim=axes)
    soft_dice = (2 * intersection + 1.0) / (probability.sum(dim=axes) + target.sum(dim=axes) + 1.0)
    return 0.5 * bce + 0.5 * (1 - soft_dice.mean())


def dice_per_image(logits: torch.Tensor, target: torch.Tensor) -> np.ndarray:
    prediction = torch.sigmoid(logits) >= 0.5
    reference = target >= 0.5
    intersection = (prediction & reference).sum(dim=(1, 2, 3)).float()
    denominator = prediction.sum(dim=(1, 2, 3)).float() + reference.sum(dim=(1, 2, 3)).float()
    return (2 * intersection / denominator.clamp_min(1)).cpu().numpy()


def validation_score(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float, dict[str, float]]:
    model.eval()
    losses: list[float] = []
    material_scores: dict[str, list[float]] = {material: [] for material in MATERIALS}
    with torch.no_grad():
        for image, mask, _, materials in loader:
            image, mask = image.to(device), mask.to(device)
            logits = model(image)
            losses.append(float(loss_function(logits, mask)))
            scores = dice_per_image(logits, mask)
            for material, score in zip(materials, scores):
                material_scores[str(material)].append(float(score))
    means = {material: float(np.mean(values)) for material, values in material_scores.items()}
    return float(np.mean(list(means.values()))), float(np.mean(losses)), means


def binary_metrics(reference: np.ndarray, prediction: np.ndarray, tolerance_px: int = 2) -> dict[str, float]:
    reference, prediction = reference.astype(bool), prediction.astype(bool)
    intersection = np.logical_and(reference, prediction).sum()
    union = np.logical_or(reference, prediction).sum()
    dice = 2 * intersection / max(reference.sum() + prediction.sum(), 1)
    iou = intersection / max(union, 1)
    ref_boundary = np.logical_xor(reference, morphology.erosion(reference))
    pred_boundary = np.logical_xor(prediction, morphology.erosion(prediction))
    footprint = morphology.disk(tolerance_px)
    precision = np.logical_and(pred_boundary, morphology.dilation(ref_boundary, footprint)).sum() / max(pred_boundary.sum(), 1)
    recall = np.logical_and(ref_boundary, morphology.dilation(pred_boundary, footprint)).sum() / max(ref_boundary.sum(), 1)
    boundary_f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return {
        "dice": float(dice), "iou": float(iou), "boundary_f1": float(boundary_f1),
        "reference_area_fraction": float(reference.mean()),
        "predicted_area_fraction": float(prediction.mean()),
        "area_fraction_error": float(abs(reference.mean() - prediction.mean())),
    }


def frozen_otsu(image: np.ndarray) -> np.ndarray:
    threshold = filters.threshold_otsu(filters.gaussian(image, sigma=1.0))
    prediction = image < threshold
    prediction = morphology.remove_small_objects(prediction, max_size=max(8, int(prediction.size * 1e-5)))
    return ndi.binary_fill_holes(prediction)


def summarize_metrics(metrics: pd.DataFrame, method: str) -> list[dict[str, object]]:
    selected = metrics[metrics["method"] == method]
    groups = [("ALL", selected), *list(selected.groupby("material", sort=True))]
    rows: list[dict[str, object]] = []
    for stratum, group in groups:
        row: dict[str, object] = {"method": method, "stratum": stratum, "n": len(group)}
        for metric in ["dice", "iou", "boundary_f1", "area_fraction_error"]:
            values = group[metric]
            row[f"{metric}_median"] = values.median()
            row[f"{metric}_q1"] = values.quantile(0.25)
            row[f"{metric}_q3"] = values.quantile(0.75)
        rows.append(row)
    return rows


def evaluate_test(model: nn.Module, dataset: FibsemDataset, device: torch.device, output_root: Path) -> pd.DataFrame:
    model.eval()
    prediction_dir = output_root / "fibsem_unet_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with torch.no_grad():
        for index, stem in enumerate(dataset.stems):
            image = dataset.images[index]
            reference = dataset.masks[index].astype(bool)
            tensor = torch.from_numpy(image)[None, None].to(device)
            unet_prediction = (torch.sigmoid(model(tensor))[0, 0].cpu().numpy() >= 0.5)
            Image.fromarray((unet_prediction * 255).astype(np.uint8)).save(prediction_dir / f"{stem}.png")
            for method, prediction in [("unet", unet_prediction), ("otsu", frozen_otsu(image))]:
                rows.append({
                    "pair_id": stem, "material": dataset.materials[index], "method": method,
                    **binary_metrics(reference, prediction),
                })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=PROJECT / "external_data" / "fibsem_4317170" / "supervised_dataset")
    parser.add_argument("--output-root", type=Path, default=PROJECT / "outputs")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    model_dir = args.output_root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = model_dir / "fibsem_unet_best.pt"

    seed_everything()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    training = FibsemDataset(args.data_root, "train", augment=True)
    validation = FibsemDataset(args.data_root, "validation", augment=False)
    if len(training) != 180 or len(validation) != 60:
        raise ValueError(f"Expected 180/60 train/validation squares, found {len(training)}/{len(validation)}")
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(training, batch_size=args.batch_size, shuffle=True, num_workers=0, generator=generator)
    validation_loader = DataLoader(validation, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = build_unet(base=16).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    history: list[dict[str, object]] = []
    best_score, best_epoch, stale = -np.inf, 0, 0
    start = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_losses: list[float] = []
        for image, mask, _, _ in train_loader:
            image, mask = image.to(device), mask.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(image), mask)
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.detach()))
        val_macro_dice, val_loss, val_material = validation_score(model, validation_loader, device)
        history.append({
            "epoch": epoch, "train_loss": float(np.mean(train_losses)), "validation_loss": val_loss,
            "validation_macro_dice": val_macro_dice,
            **{f"validation_dice_{key}": value for key, value in val_material.items()},
            "elapsed_seconds": time.time() - start,
        })
        print(
            f"epoch={epoch:03d} train_loss={history[-1]['train_loss']:.4f} "
            f"val_loss={val_loss:.4f} val_macro_dice={val_macro_dice:.4f}", flush=True
        )
        if val_macro_dice > best_score + 1e-8:
            best_score, best_epoch, stale = val_macro_dice, epoch, 0
            torch.save({
                "model_state": model.state_dict(), "epoch": epoch, "validation_macro_dice": best_score,
                "seed": SEED, "protocol": "FIBSEM_UNET_LOCKED_PROTOCOL.md",
            }, checkpoint_path)
        else:
            stale += 1
            if stale >= args.patience:
                break

    pd.DataFrame(history).to_csv(args.output_root / "fibsem_unet_training_history.csv", index=False)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state"])

    # The test split is instantiated only after validation-based model selection is complete.
    test = FibsemDataset(args.data_root, "test", augment=False)
    if len(test) != 60:
        raise ValueError(f"Expected 60 official test squares, found {len(test)}")
    metrics = evaluate_test(model, test, device, args.output_root)
    metrics.to_csv(args.output_root / "fibsem_unet_test_metrics.csv", index=False)
    summary_rows = summarize_metrics(metrics, "unet") + summarize_metrics(metrics, "otsu")
    pd.DataFrame(summary_rows).to_csv(args.output_root / "fibsem_unet_test_summary.csv", index=False)
    paired = metrics.pivot(index=["pair_id", "material"], columns="method", values="dice").reset_index()
    paired["dice_gain_unet_minus_otsu"] = paired["unet"] - paired["otsu"]
    paired.to_csv(args.output_root / "fibsem_unet_paired_dice.csv", index=False)
    run = {
        "seed": SEED, "device": str(device), "torch_version": torch.__version__,
        "best_epoch": best_epoch, "best_validation_macro_dice": best_score,
        "epochs_completed": len(history), "elapsed_seconds": time.time() - start,
        "test_evaluations": 1,
    }
    (args.output_root / "fibsem_unet_run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    print(json.dumps(run, indent=2), flush=True)


if __name__ == "__main__":
    main()
