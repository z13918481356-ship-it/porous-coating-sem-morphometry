from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLBACKEND", "Agg")
RUNTIME_DEPS = PROJECT / "runtime_deps"
if RUNTIME_DEPS.exists():
    sys.path.insert(0, str(RUNTIME_DEPS))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from skimage import exposure, filters, morphology


SEED = 20260830
DATA_ROOT = PROJECT / "external_data" / "fibsem_4317170" / "supervised_dataset" / "test"
OUTPUT_ROOT = PROJECT / "outputs"
FIGURE_ROOT = OUTPUT_ROOT / "external_validation"


def normalize(path: Path) -> np.ndarray:
    image = np.asarray(Image.open(path), dtype=np.float32)
    lo, hi = np.percentile(image, [1, 99])
    return exposure.rescale_intensity(image, in_range=(lo, hi), out_range=(0, 1)).astype(np.float32)


def otsu(image: np.ndarray) -> np.ndarray:
    threshold = filters.threshold_otsu(filters.gaussian(image, sigma=1.0))
    prediction = image < threshold
    prediction = morphology.remove_small_objects(prediction, max_size=max(8, int(prediction.size * 1e-5)))
    return ndi.binary_fill_holes(prediction)


def main() -> None:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    metrics = pd.read_csv(OUTPUT_ROOT / "fibsem_unet_test_metrics.csv")
    unet_metrics = metrics[metrics["method"] == "unet"].sort_values("dice").reset_index(drop=True)
    history = pd.read_csv(OUTPUT_ROOT / "fibsem_unet_training_history.csv")
    paired = pd.read_csv(OUTPUT_ROOT / "fibsem_unet_paired_dice.csv")

    rng = np.random.default_rng(SEED)
    gains = paired["dice_gain_unet_minus_otsu"].to_numpy()
    samples = rng.choice(gains, size=(10000, len(gains)), replace=True)
    bootstrap = pd.DataFrame([{
        "n": len(gains), "bootstrap_replicates": 10000,
        "median_dice_gain": float(np.median(gains)),
        "median_dice_gain_ci_low": float(np.quantile(np.median(samples, axis=1), 0.025)),
        "median_dice_gain_ci_high": float(np.quantile(np.median(samples, axis=1), 0.975)),
        "mean_dice_gain": float(np.mean(gains)),
        "mean_dice_gain_ci_low": float(np.quantile(np.mean(samples, axis=1), 0.025)),
        "mean_dice_gain_ci_high": float(np.quantile(np.mean(samples, axis=1), 0.975)),
        "unet_wins": int((gains > 0).sum()), "unet_losses": int((gains < 0).sum()),
    }])
    bootstrap.to_csv(OUTPUT_ROOT / "fibsem_unet_paired_bootstrap.csv", index=False)

    best_epoch = int(history.loc[history["validation_macro_dice"].idxmax(), "epoch"])
    figure, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    axes[0].plot(history["epoch"], history["train_loss"], label="train")
    axes[0].plot(history["epoch"], history["validation_loss"], label="validation")
    axes[0].axvline(best_epoch, color="#b22222", linestyle="--", linewidth=1)
    axes[0].set(xlabel="Epoch", ylabel="BCE + soft Dice loss", title="Optimization")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    for material, group in history.melt(
        id_vars="epoch", value_vars=[f"validation_dice_{m}" for m in ["HPC22", "HPC30", "HPC45"]],
        var_name="material", value_name="dice"
    ).groupby("material"):
        axes[1].plot(group["epoch"], group["dice"], label=material.rsplit("_", 1)[-1])
    axes[1].plot(history["epoch"], history["validation_macro_dice"], color="black", linewidth=2, label="macro")
    axes[1].axvline(best_epoch, color="#b22222", linestyle="--", linewidth=1, label=f"best epoch {best_epoch}")
    axes[1].set(xlabel="Epoch", ylabel="Validation Dice", title="Validation-only model selection")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.25)

    colors = {"HPC22": "#4c78a8", "HPC30": "#f58518", "HPC45": "#54a24b"}
    for material, group in paired.groupby("material"):
        axes[2].scatter(group["otsu"], group["unet"], label=material, color=colors[material], alpha=0.8)
    axes[2].plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1)
    axes[2].set(xlim=(0, 1), ylim=(0, 1), xlabel="Frozen Otsu Dice", ylabel="U-Net Dice",
                title=f"Paired official test squares\nU-Net wins {(gains > 0).sum()}/{len(gains)}")
    axes[2].legend(fontsize=8)
    axes[2].grid(alpha=0.25)
    figure.savefig(FIGURE_ROOT / "fibsem_unet_training_and_comparison.png", dpi=220)
    plt.close(figure)

    cases = [("Worst", unet_metrics.iloc[0]), ("Median", unet_metrics.iloc[len(unet_metrics) // 2 - 1]),
             ("Best", unet_metrics.iloc[-1])]
    figure, axes = plt.subplots(3, 5, figsize=(14, 8.7), constrained_layout=True)
    for row_index, (case_name, row) in enumerate(cases):
        stem = row["pair_id"]
        image = normalize(DATA_ROOT / "images" / f"{stem}.tif")
        reference = np.asarray(Image.open(DATA_ROOT / "masks" / f"{stem}.png").convert("L")) > 127
        otsu_prediction = otsu(image)
        unet_prediction = np.asarray(Image.open(OUTPUT_ROOT / "fibsem_unet_predictions" / f"{stem}.png").convert("L")) > 127
        overlay = np.zeros((*reference.shape, 3), dtype=float)
        overlay[..., 0] = np.logical_and(unet_prediction, ~reference)
        overlay[..., 1] = np.logical_and(unet_prediction, reference)
        overlay[..., 2] = np.logical_and(reference, ~unet_prediction)
        panels = [(image, "gray", "SEM"), (reference, "gray", "Reference pore"),
                  (otsu_prediction, "gray", "Frozen Otsu"), (unet_prediction, "gray", "U-Net"),
                  (overlay, None, "U-Net: TP green / FP red / FN blue")]
        for column, (panel, cmap, title) in enumerate(panels):
            axes[row_index, column].imshow(panel, cmap=cmap, vmin=0 if cmap else None, vmax=1 if cmap else None)
            axes[row_index, column].set_title(title if row_index == 0 else "")
            axes[row_index, column].axis("off")
        axes[row_index, 0].set_ylabel(
            f"{case_name}: {row['material']}\nU-Net Dice={row['dice']:.3f}", fontsize=10
        )
    figure.suptitle("Frozen U-Net test diagnostics: all cases selected by U-Net Dice rank")
    figure.savefig(FIGURE_ROOT / "fibsem_unet_test_diagnostics.png", dpi=220)
    plt.close(figure)


if __name__ == "__main__":
    main()
