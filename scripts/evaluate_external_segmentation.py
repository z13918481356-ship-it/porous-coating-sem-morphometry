from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    # Some managed workspaces make a vendored six.py unreadable while the
    # interpreter's own compatible copy remains available. Preload that copy
    # before placing the scientific dependency bundle on sys.path.
    six_path = Path(sys.base_prefix) / "Lib" / "site-packages" / "six.py"
    if six_path.exists() and "six" not in sys.modules:
        spec = importlib.util.spec_from_file_location("six", six_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["six"] = module
            spec.loader.exec_module(module)
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from skimage import exposure, filters, measure, morphology

def binary_metrics(reference: np.ndarray, prediction: np.ndarray, tolerance_px: int = 2) -> dict[str, float]:
    reference = reference.astype(bool)
    prediction = prediction.astype(bool)
    intersection = np.logical_and(reference, prediction).sum()
    union = np.logical_or(reference, prediction).sum()
    dice = 2 * intersection / max(reference.sum() + prediction.sum(), 1)
    iou = intersection / max(union, 1)
    ref_boundary = np.logical_xor(reference, morphology.erosion(reference))
    pred_boundary = np.logical_xor(prediction, morphology.erosion(prediction))
    structure = morphology.disk(tolerance_px)
    precision = np.logical_and(pred_boundary, morphology.dilation(ref_boundary, structure)).sum() / max(pred_boundary.sum(), 1)
    recall = np.logical_and(ref_boundary, morphology.dilation(pred_boundary, structure)).sum() / max(ref_boundary.sum(), 1)
    boundary_f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return {
        "dice": float(dice), "iou": float(iou), "boundary_f1": float(boundary_f1),
        "reference_area_fraction": float(reference.mean()),
        "predicted_area_fraction": float(prediction.mean()),
        "area_fraction_error": float(abs(reference.mean() - prediction.mean())),
    }


def load_paao_image(path: Path) -> tuple[np.ndarray, int]:
    """Load a PAAO SEM and remove the dark FEI information footer."""
    gray = np.asarray(Image.open(path).convert("L"), dtype=np.float32) / 255.0
    height = gray.shape[0]
    row_dark_fraction = (gray < 0.10).mean(axis=1)
    row_mean = gray.mean(axis=1)
    candidates = np.where(
        (np.arange(height) > int(0.70 * height))
        & (row_dark_fraction > 0.60)
        & (row_mean < 0.35)
    )[0]
    crop_y = int(candidates[0]) if len(candidates) else height
    roi = gray[:crop_y]
    lo, hi = np.percentile(roi, [1, 99])
    return exposure.rescale_intensity(roi, in_range=(lo, hi), out_range=(0, 1)).astype(np.float32), crop_y


def evaluate_paao(data_root: Path, output_root: Path) -> None:
    from morphometry.pipeline import extract_pixel_size_um, segment_classical

    files = sorted(data_root.glob("*.tif")) + sorted(data_root.glob("*.tiff"))
    if not files:
        raise FileNotFoundError(f"No PAAO TIFF files found in {data_root}")
    rows = []
    for path in files:
        match = re.search(r"(AJ-\d+).*?-(50000|100000|200000)x", path.name, re.IGNORECASE)
        if not match:
            continue
        image, crop_y = load_paao_image(path)
        with Image.open(path) as source_image:
            pixel_size, calibration_source = extract_pixel_size_um(source_image)
            original_height = source_image.height
        solid, _, _ = segment_classical(image)
        pores = ~solid
        pores = morphology.remove_small_objects(pores, max_size=max(8, int(pores.size * 1e-5)))
        labels = measure.label(pores)
        equivalent_px = [region.equivalent_diameter_area for region in measure.regionprops(labels)]
        rows.append({
            "dataset_id": "paao_5905496", "sample_id": match.group(1).upper(),
            "magnification_x": int(match.group(2)), "relative_path": path.name,
            "pixel_size_um": pixel_size, "calibration_source": calibration_source,
            "crop_y_px": crop_y, "footer_removed_px": int(original_height - crop_y),
            "pore_area_fraction": float(pores.mean()), "pore_count": int(labels.max()),
            "pore_eq_diameter_median_px": float(np.median(equivalent_px)) if equivalent_px else np.nan,
            "validation_status": "domain_shift_descriptive_only_no_reference_masks",
        })
    result = pd.DataFrame(rows)
    result.to_csv(output_root / "external_paao_features.csv", index=False)
    consistency = result.groupby("sample_id", as_index=False).agg(
        n_magnifications=("magnification_x", "nunique"),
        pore_fraction_mean=("pore_area_fraction", "mean"),
        pore_fraction_sd=("pore_area_fraction", "std"),
        pore_fraction_range=("pore_area_fraction", lambda x: x.max() - x.min()),
    )
    consistency.to_csv(output_root / "external_paao_scale_consistency.csv", index=False)
    print(f"Evaluated {len(result)} PAAO images across {result['sample_id'].nunique()} samples; no accuracy claim made.")


def evaluate_fibsem(data_root: Path, output_root: Path, pore_is_dark: bool) -> None:
    image_dir, mask_dir = data_root / "images", data_root / "masks"
    image_paths = {path.stem: path for path in image_dir.glob("*") if path.suffix.lower() in {".png", ".tif", ".tiff"}}
    mask_paths = {path.stem: path for path in mask_dir.glob("*") if path.suffix.lower() in {".png", ".tif", ".tiff"}}
    stems = sorted(set(image_paths) & set(mask_paths))
    if not stems:
        raise FileNotFoundError("No same-stem image/mask pairs found; create images/ and masks/ under the FIB-SEM root.")
    rows = []
    for stem in stems:
        raw = np.asarray(Image.open(image_paths[stem]))
        if raw.ndim == 3:
            raw = raw[..., :3].mean(axis=2)
        image = raw.astype(np.float32)
        low, high = np.percentile(image, [1, 99])
        image = exposure.rescale_intensity(image, in_range=(low, high), out_range=(0, 1)).astype(np.float32)
        reference = np.asarray(Image.open(mask_paths[stem]).convert("L")) > 127
        threshold = filters.threshold_otsu(filters.gaussian(image, sigma=1.0))
        prediction = image < threshold if pore_is_dark else image > threshold
        prediction = morphology.remove_small_objects(prediction, max_size=max(8, int(prediction.size * 1e-5)))
        prediction = ndi.binary_fill_holes(prediction)
        material_match = re.search(r"FIBSEM-(HPC\d+)-", stem, re.IGNORECASE)
        rows.append({
            "dataset_id": "fibsem_4317170",
            "material": material_match.group(1).upper() if material_match else "unknown",
            "pair_id": stem,
            **binary_metrics(reference, prediction),
        })
    result = pd.DataFrame(rows)
    result.to_csv(output_root / "external_fibsem_classical_metrics.csv", index=False)
    print(f"Evaluated {len(result)} independent FIB-SEM image/mask pairs.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=["paao", "fibsem"])
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=PROJECT / "outputs")
    parser.add_argument("--pore-is-dark", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.dataset == "paao":
        evaluate_paao(args.data_root, args.output_root)
    else:
        evaluate_fibsem(args.data_root, args.output_root, args.pore_is_dark)


if __name__ == "__main__":
    main()
