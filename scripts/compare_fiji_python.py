"""Compare the frozen Fiji/ImageJ review run against Python morphometry."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SEED = 20260830
METRICS = {
    "pore_area_fraction": ("python_pore_area_fraction", "Pore-area fraction"),
    "eq_diameter_median_um": ("python_eq_diameter_median_um", "Equivalent diameter (µm)"),
    "circularity_median": ("python_circularity_median", "Circularity"),
    "object_count": ("python_object_count", "Object count"),
}


def bootstrap_ci(values: np.ndarray, statistic, rng: np.random.Generator, draws: int = 4000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    samples = np.asarray([statistic(rng.choice(values, size=len(values), replace=True)) for _ in range(draws)])
    return tuple(np.quantile(samples, [0.025, 0.975]).tolist())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-root", type=Path, default=ROOT / "data/processed/fiji_review")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()

    manifest = pd.read_csv(args.review_root / "fiji_review_manifest.csv")
    fiji = pd.read_csv(args.review_root / "fiji_results.csv")
    merged = manifest.merge(fiji, on=["image_id", "input_filename"], validate="one_to_one")
    if len(merged) != 12:
        raise ValueError(f"Expected 12 frozen review images, got {len(merged)}")

    result = merged[["image_id", "relative_path", "image_role", "condition_key", "selection_seed"]].copy()
    summary_rows = []
    rng = np.random.default_rng(SEED)
    for metric, (python_col, label) in METRICS.items():
        fiji_values = merged[metric].to_numpy(dtype=float)
        python_values = merged[python_col].to_numpy(dtype=float)
        difference = fiji_values - python_values
        abs_difference = np.abs(difference)
        result[f"python_{metric}"] = python_values
        result[f"fiji_{metric}"] = fiji_values
        result[f"difference_{metric}"] = difference
        result[f"absolute_difference_{metric}"] = abs_difference
        rho, pvalue = spearmanr(python_values, fiji_values)
        median_abs = float(np.median(abs_difference))
        lo, hi = bootstrap_ci(abs_difference, np.median, rng)
        summary_rows.append({
            "metric": metric,
            "label": label,
            "n_images": len(merged),
            "median_python": float(np.median(python_values)),
            "median_fiji": float(np.median(fiji_values)),
            "median_signed_difference_fiji_minus_python": float(np.median(difference)),
            "median_absolute_difference": median_abs,
            "median_absolute_difference_bootstrap_ci_low": lo,
            "median_absolute_difference_bootstrap_ci_high": hi,
            "spearman_rho": float(rho),
            "spearman_p_value": float(pvalue),
        })

    args.output_root.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output_root / "fiji_review_comparison.csv", index=False)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(args.output_root / "fiji_review_summary.csv", index=False)

    fig, axes = plt.subplots(2, 2, figsize=(8.4, 7.1), constrained_layout=True)
    for axis, (metric, (python_col, label)) in zip(axes.ravel(), METRICS.items()):
        x = merged[python_col].to_numpy(dtype=float)
        y = merged[metric].to_numpy(dtype=float)
        axis.scatter(x, y, color="#1f5a7a", edgecolor="white", linewidth=0.65, s=42, zorder=3)
        lower, upper = min(x.min(), y.min()), max(x.max(), y.max())
        padding = 0.05 * max(upper - lower, 1e-9)
        axis.plot([lower - padding, upper + padding], [lower - padding, upper + padding], "--", color="#7a7a7a", lw=1)
        axis.set_xlim(lower - padding, upper + padding)
        axis.set_ylim(lower - padding, upper + padding)
        item = summary.loc[summary.metric.eq(metric)].iloc[0]
        axis.set_title(label, fontsize=10, weight="bold")
        axis.set_xlabel("Python")
        axis.set_ylabel("Fiji/ImageJ")
        axis.text(0.04, 0.96, f"ρ={item.spearman_rho:.2f}\nmedian |Δ|={item.median_absolute_difference:.3g}",
                  transform=axis.transAxes, va="top", fontsize=8.5,
                  bbox={"facecolor": "white", "edgecolor": "#d0d0d0", "boxstyle": "round,pad=0.25"})
        axis.grid(alpha=0.18, zorder=0)
    figure_dir = args.output_root / "figures"
    figure_dir.mkdir(exist_ok=True)
    fig.savefig(figure_dir / "fiji_imagej_crosscheck.png", dpi=220)
    plt.close(fig)
    print(f"Wrote Fiji/Python comparison for {len(merged)} images to {args.output_root}")


if __name__ == "__main__":
    main()
