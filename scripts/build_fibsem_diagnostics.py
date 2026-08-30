from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLBACKEND", "Agg")
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    six_path = Path(sys.base_prefix) / "Lib" / "site-packages" / "six.py"
    if six_path.exists() and "six" not in sys.modules:
        spec = importlib.util.spec_from_file_location("six", six_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["six"] = module
            spec.loader.exec_module(module)
    sys.path.insert(0, str(DEPS))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from skimage import exposure, filters, morphology


DATA_ROOT = PROJECT / "external_data" / "fibsem_4317170" / "locked_subset"
OUTPUT_ROOT = PROJECT / "outputs"


def frozen_prediction(path: Path) -> tuple[np.ndarray, np.ndarray]:
    raw = np.asarray(Image.open(path))
    image = raw.astype(np.float32)
    lo, hi = np.percentile(image, [1, 99])
    image = exposure.rescale_intensity(image, in_range=(lo, hi), out_range=(0, 1)).astype(np.float32)
    threshold = filters.threshold_otsu(filters.gaussian(image, sigma=1.0))
    prediction = image < threshold
    prediction = morphology.remove_small_objects(prediction, max_size=max(8, int(prediction.size * 1e-5)))
    return image, ndi.binary_fill_holes(prediction)


def summarize(group: pd.DataFrame, label: str) -> dict[str, object]:
    row: dict[str, object] = {"stratum": label, "n": len(group)}
    for metric in ["dice", "iou", "boundary_f1", "area_fraction_error"]:
        values = group[metric].astype(float)
        row[f"{metric}_median"] = values.median()
        row[f"{metric}_q1"] = values.quantile(0.25)
        row[f"{metric}_q3"] = values.quantile(0.75)
        row[f"{metric}_min"] = values.min()
        row[f"{metric}_max"] = values.max()
    return row


def main() -> None:
    metrics = pd.read_csv(OUTPUT_ROOT / "external_fibsem_classical_metrics.csv")
    summaries = [summarize(metrics, "ALL")]
    summaries.extend(summarize(group, material) for material, group in metrics.groupby("material", sort=True))
    pd.DataFrame(summaries).to_csv(OUTPUT_ROOT / "external_fibsem_summary.csv", index=False)

    ordered = metrics.sort_values("dice").reset_index(drop=True)
    cases = [
        ("Worst", ordered.iloc[0]),
        ("Median", ordered.iloc[len(ordered) // 2 - 1]),
        ("Best", ordered.iloc[-1]),
    ]
    figure, axes = plt.subplots(3, 4, figsize=(12, 9), constrained_layout=True)
    for row_index, (case_name, row) in enumerate(cases):
        stem = row["pair_id"]
        image, prediction = frozen_prediction(DATA_ROOT / "images" / f"{stem}.tif")
        reference = np.asarray(Image.open(DATA_ROOT / "masks" / f"{stem}.png").convert("L")) > 127
        overlay = np.zeros((*reference.shape, 3), dtype=float)
        overlay[..., 0] = np.logical_and(prediction, ~reference)
        overlay[..., 1] = np.logical_and(prediction, reference)
        overlay[..., 2] = np.logical_and(reference, ~prediction)
        panels = [(image, "gray", "SEM"), (reference, "gray", "Reference pore"),
                  (prediction, "gray", "Frozen Otsu pore"), (overlay, None, "TP green / FP red / FN blue")]
        for col_index, (panel, cmap, title) in enumerate(panels):
            axes[row_index, col_index].imshow(panel, cmap=cmap, vmin=0 if cmap else None, vmax=1 if cmap else None)
            axes[row_index, col_index].set_title(title if row_index == 0 else "")
            axes[row_index, col_index].axis("off")
        axes[row_index, 0].set_ylabel(
            f"{case_name}: {row['material']}\nDice={row['dice']:.3f}, BF1={row['boundary_f1']:.3f}",
            fontsize=10,
        )
    figure.suptitle("Locked FIB-SEM external benchmark: unchanged dark-pore Otsu", fontsize=14)
    diagnostics_dir = OUTPUT_ROOT / "external_validation"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    figure.savefig(diagnostics_dir / "fibsem_locked_diagnostics.png", dpi=220)
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(11, 3.7), constrained_layout=True)
    for axis, metric, label in zip(
        axes,
        ["dice", "boundary_f1", "area_fraction_error"],
        ["Dice", "Boundary F1 (2 px)", "Absolute pore-fraction error"],
    ):
        groups = [group[metric].to_numpy() for _, group in metrics.groupby("material", sort=True)]
        labels = [name for name, _ in metrics.groupby("material", sort=True)]
        axis.boxplot(groups, tick_labels=labels, showfliers=True)
        axis.set_ylabel(label)
        axis.grid(axis="y", alpha=0.25)
        if metric == "dice":
            axis.axhline(0.70, color="#b22222", linestyle="--", linewidth=1, label="locked partial-transfer gate")
            axis.legend(fontsize=7, loc="lower right")
    figure.suptitle("Performance varies across porous-polymer strata (n=8 each)")
    figure.savefig(diagnostics_dir / "fibsem_metric_distributions.png", dpi=220)
    plt.close(figure)


if __name__ == "__main__":
    main()
