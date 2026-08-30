from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from skimage import color, measure, morphology
from scipy.stats import spearmanr

from evaluate_external_segmentation import load_paao_image
from morphometry.pipeline import segment_classical


def main() -> None:
    data_root = PROJECT / "external_data" / "paao_5905496"
    output_root = PROJECT / "outputs"
    features = pd.read_csv(output_root / "external_paao_features.csv")
    consistency = pd.read_csv(output_root / "external_paao_scale_consistency.csv")

    diagnostics = []
    for sample, group in features.groupby("sample_id"):
        group = group.sort_values("magnification_x")
        fractions = group["pore_area_fraction"].to_numpy(float)
        diameters = group["pore_eq_diameter_median_px"].to_numpy(float)
        relative_range = (fractions.max() - fractions.min()) / max(abs(fractions.mean()), 1e-12)
        monotonic_fraction = bool(np.all(np.diff(fractions) <= 0))
        diameter_scale_failure = bool(diameters[-1] < diameters[0])
        flags = []
        if relative_range > 0.20:
            flags.append("pore_fraction_scale_sensitive")
        if not monotonic_fraction:
            flags.append("nonmonotonic_pore_fraction")
        if diameter_scale_failure:
            flags.append("high_magnification_fragmentation")
        diagnostics.append({
            "sample_id": sample,
            "relative_pore_fraction_range": relative_range,
            "pore_fraction_monotonic_decrease": monotonic_fraction,
            "diameter_200k_over_50k_px": diameters[-1] / max(diameters[0], 1e-12),
            "failure_flags": ";".join(flags),
        })
    pd.DataFrame(diagnostics).to_csv(output_root / "external_paao_failure_cases.csv", index=False)

    pivot = features.pivot(index="sample_id", columns="magnification_x", values="pore_area_fraction")
    rank_rows = []
    magnifications = sorted(pivot.columns)
    for left_index, left in enumerate(magnifications):
        for right in magnifications[left_index + 1:]:
            valid = pivot[[left, right]].dropna()
            rank_rows.append({
                "magnification_a": int(left), "magnification_b": int(right),
                "n_samples": len(valid),
                "spearman_rho_across_samples": float(spearmanr(valid[left], valid[right]).statistic),
            })
    pd.DataFrame(rank_rows).to_csv(output_root / "external_paao_rank_consistency.csv", index=False)

    sample = "AJ-4"
    group = features[features["sample_id"] == sample].sort_values("magnification_x")
    fig = plt.figure(figsize=(12, 8.3))
    grid = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.95], hspace=0.24, wspace=0.05)
    for column, record in enumerate(group.to_dict("records")):
        image, _ = load_paao_image(data_root / record["relative_path"])
        solid, _, _ = segment_classical(image)
        pores = morphology.remove_small_objects(~solid, max_size=max(8, int(solid.size * 1e-5)))
        ax = fig.add_subplot(grid[0, column])
        ax.imshow(image, cmap="gray")
        ax.set_title(f"{sample} · {int(record['magnification_x']/1000)}k raw", fontsize=10, fontweight="bold")
        ax.axis("off")
        ax = fig.add_subplot(grid[1, column])
        overlay = color.label2rgb(measure.label(pores), image=image, bg_label=0, alpha=0.45)
        ax.imshow(np.clip(overlay, 0, 1))
        ax.set_title(f"Pore fraction {record['pore_area_fraction']:.3f}", fontsize=9)
        ax.axis("off")

    ax = fig.add_subplot(grid[2, :2])
    for sample_id, sample_group in features.groupby("sample_id"):
        sample_group = sample_group.sort_values("magnification_x")
        ax.plot(sample_group["magnification_x"] / 1000, sample_group["pore_area_fraction"], marker="o", label=sample_id)
    ax.set_xlabel("Nominal magnification (k×)")
    ax.set_ylabel("Otsu pore area fraction")
    ax.set_title("A. Scale dependence across all samples", loc="left", fontweight="bold")
    ax.grid(alpha=0.2); ax.legend(frameon=False, ncol=3, fontsize=8)

    ax = fig.add_subplot(grid[2, 2])
    diag = pd.DataFrame(diagnostics).sort_values("relative_pore_fraction_range")
    ax.barh(diag["sample_id"], 100 * diag["relative_pore_fraction_range"], color="#B55245")
    ax.axvline(20, color="#16324F", linestyle="--", linewidth=1)
    ax.set_xlabel("Relative range (%)")
    ax.set_title("B. Magnification sensitivity", loc="left", fontweight="bold")
    ax.grid(axis="x", alpha=0.2)
    fig.suptitle("PAAO external validation: stable execution, scale-sensitive segmentation", fontsize=14, fontweight="bold")
    destination = output_root / "external_validation"
    destination.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination / "paao_segmentation_diagnostics.png", dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Wrote diagnostics for {len(diagnostics)} PAAO samples.")


if __name__ == "__main__":
    main()
