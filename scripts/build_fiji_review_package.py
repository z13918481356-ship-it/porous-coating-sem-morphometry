"""Create a frozen, scale-calibrated SEM subset for Fiji/ImageJ cross-checking.

The exported TIFFs are the same cropped and contrast-normalized ROIs consumed by
the Python workflow.  They are deliberately kept out of Git because they derive
from the Zenodo raw archive; the manifest, macro and resulting numeric tables are
small and versioned.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morphometry.pipeline import _manual_calibration, load_sem  # noqa: E402


SEED = 20260830
ROLE_QUOTAS = {"coating": 7, "particle": 4, "reference": 1}


def select_rows(manifest: pd.DataFrame) -> pd.DataFrame:
    """Return a seeded stratified sample of twelve calibrated SEM images."""
    rng = random.Random(SEED)
    selected: list[dict[str, object]] = []
    for role, quota in ROLE_QUOTAS.items():
        group = manifest.loc[manifest["image_role"].eq(role)].sort_values("relative_path")
        if len(group) < quota:
            raise ValueError(f"Only {len(group)} {role} images available for quota {quota}.")
        picks = rng.sample(group.to_dict("records"), quota)
        selected.extend(sorted(picks, key=lambda row: str(row["relative_path"])))
    result = pd.DataFrame(selected).sort_values(["image_role", "relative_path"]).reset_index(drop=True)
    result.insert(0, "image_id", [f"sem_{i:02d}" for i in range(1, len(result) + 1)])
    result.insert(1, "selection_seed", SEED)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/raw/zenodo_16054027")
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/processed/fiji_review")
    parser.add_argument("--manifest", type=Path, default=ROOT / "outputs/image_manifest.csv")
    parser.add_argument("--features", type=Path, default=ROOT / "outputs/morphometry_features.csv")
    parser.add_argument("--calibration", type=Path, default=ROOT / "configs/manual_calibration.csv")
    parser.add_argument("--frozen-manifest", type=Path, default=ROOT / "outputs/fiji_review_manifest.csv")
    args = parser.parse_args()

    manifest = pd.read_csv(args.manifest)
    features = pd.read_csv(args.features).set_index("relative_path")
    manual_calibration = _manual_calibration(args.calibration)
    sample = select_rows(manifest)
    inputs = args.output_root / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    rows = []
    for row in sample.to_dict("records"):
        relative_path = str(row["relative_path"])
        source = args.data_root / relative_path
        roi, pixel_size_um, _, crop_y_px = load_sem(source, manual_calibration.get(relative_path))
        if pixel_size_um is None or pixel_size_um <= 0:
            raise ValueError(f"No usable calibration for {relative_path}")
        output_name = f"{row['image_id']}.tif"
        Image.fromarray(np.round(np.clip(roi, 0, 1) * 255).astype(np.uint8)).save(inputs / output_name)
        min_size_px = max(12, int(roi.size * 1.5e-5))
        feature = features.loc[relative_path]
        rows.append({
            "image_id": row["image_id"],
            "input_filename": output_name,
            "relative_path": relative_path,
            "image_role": row["image_role"],
            "condition_key": row["condition_key"],
            "selection_seed": SEED,
            "width_px": roi.shape[1],
            "height_px": roi.shape[0],
            "crop_y_px": crop_y_px,
            "pixel_size_um": pixel_size_um,
            "pixels_per_um": 1 / pixel_size_um,
            "min_particle_size_px": min_size_px,
            "min_particle_area_um2": min_size_px * pixel_size_um**2,
            "python_pore_area_fraction": feature["pore_area_fraction"],
            "python_eq_diameter_median_um": feature["eq_diameter_median_um"],
            "python_circularity_median": feature["circularity_median"],
            "python_object_count": feature["object_count"],
        })
    output = pd.DataFrame(rows)
    output.to_csv(args.output_root / "fiji_review_manifest.csv", index=False)
    args.frozen_manifest.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.frozen_manifest, index=False)
    print(f"Wrote {len(output)} frozen review inputs to {args.output_root}")


if __name__ == "__main__":
    main()
