from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import pandas as pd
from skimage.transform import resize

from morphometry.pipeline import FEATURES, extract_features, load_sem, segment_classical


def main() -> None:
    output_root = PROJECT / "outputs"
    data_root = PROJECT / "data" / "raw" / "zenodo_16054027"
    manifest = pd.read_csv(output_root / "image_manifest.csv")
    coating = manifest[(manifest["image_role"] == "coating") & (manifest["view"] == "top")].copy()
    coating["field_height_um"] = coating["height_px"] * coating["pixel_size_um"]
    groups = [group for _, group in coating.groupby("condition_key") if len(group) >= 2 and group["field_width_um"].nunique() >= 2]

    rows = []
    for group in groups:
        common_window_um = 0.8 * min(group["field_width_um"].min(), group["field_height_um"].min())
        common_pixel_um = group["pixel_size_um"].max()
        output_pixels = max(128, int(np.floor(common_window_um / common_pixel_um)))
        common_window_um = output_pixels * common_pixel_um
        for record in group.to_dict("records"):
            image, detected_pixel, _, _ = load_sem(data_root / record["relative_path"])
            native_pixel = detected_pixel if detected_pixel is not None else float(record["pixel_size_um"])
            crop_pixels = min(int(round(common_window_um / native_pixel)), image.shape[0], image.shape[1])
            y0 = (image.shape[0] - crop_pixels) // 2
            x0 = (image.shape[1] - crop_pixels) // 2
            crop = image[y0:y0 + crop_pixels, x0:x0 + crop_pixels]
            matched = resize(crop, (output_pixels, output_pixels), preserve_range=True, anti_aliasing=True).astype(np.float32)
            mask, labels, _ = segment_classical(matched)
            features = extract_features(matched, mask, labels, common_pixel_um)
            rows.append({
                "condition_key": record["condition_key"],
                "relative_path": record["relative_path"],
                "native_pixel_size_um": native_pixel,
                "native_field_width_um": record["field_width_um"],
                "matched_window_um": common_window_um,
                "matched_pixel_size_um": common_pixel_um,
                "matched_size_px": output_pixels,
                **features,
            })
    matched = pd.DataFrame(rows)
    matched.to_csv(output_root / "matched_scale_features.csv", index=False)

    consistency_rows = []
    for condition_key, group in matched.groupby("condition_key"):
        for feature in FEATURES:
            values = group[feature].dropna().to_numpy(float)
            if len(values) < 2:
                continue
            mean = float(np.mean(values))
            consistency_rows.append({
                "condition_key": condition_key,
                "feature": feature,
                "n_fields": len(values),
                "matched_mean": mean,
                "matched_sd": float(np.std(values, ddof=1)),
                "matched_cv": float(np.std(values, ddof=1) / (abs(mean) + 1e-12)),
                "matched_relative_range": float((np.max(values) - np.min(values)) / (abs(mean) + 1e-12)),
            })
    consistency = pd.DataFrame(consistency_rows)
    full = pd.read_csv(output_root / "magnification_consistency.csv")
    full_summary = full.groupby(["condition_key", "feature"], as_index=False)["relative_difference"].mean()
    consistency = consistency.merge(full_summary, on=["condition_key", "feature"], how="left")
    consistency["relative_difference_reduction"] = consistency["relative_difference"] - consistency["matched_relative_range"]
    consistency.to_csv(output_root / "matched_scale_consistency.csv", index=False)
    print(f"Matched {len(matched)} fields across {matched['condition_key'].nunique()} multi-magnification conditions.")


if __name__ == "__main__":
    main()
