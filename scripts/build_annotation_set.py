from __future__ import annotations

import argparse
import hashlib
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
from PIL import Image

from morphometry.pipeline import load_sem


def _split_by_condition(conditions: list[str], seed: int) -> dict[str, str]:
    ordered = sorted(conditions, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())
    n = len(ordered)
    n_train = max(1, round(0.6 * n))
    n_val = max(1, round(0.2 * n))
    if n_train + n_val >= n:
        n_train, n_val = max(1, n - 2), 1
    return {
        condition: ("train" if index < n_train else "validation" if index < n_train + n_val else "test")
        for index, condition in enumerate(ordered)
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-size", type=int, default=512)
    parser.add_argument("--patch-count", type=int, default=24)
    parser.add_argument("--seed", type=int, default=20260829)
    args = parser.parse_args()

    data_root = PROJECT / "data" / "raw" / "zenodo_16054027"
    manifest = pd.read_csv(PROJECT / "outputs" / "image_manifest.csv")
    sources = manifest[(manifest["image_role"] == "coating") & (manifest["view"] == "top")].copy()
    sources = sources.sort_values(["condition_key", "field_width_um", "relative_path"]).reset_index(drop=True)
    split_map = _split_by_condition(sources["condition_key"].drop_duplicates().tolist(), args.seed)

    root = PROJECT / "annotations"
    image_dir = root / "images"
    for directory in [image_dir, root / "masks_annotator_a", root / "masks_annotator_b", root / "masks_adjudicated"]:
        directory.mkdir(parents=True, exist_ok=True)

    # Every eligible source contributes a central patch. Additional patches are
    # allocated across physical scales, while the split remains condition-level.
    requests: list[tuple[dict, int]] = [(row, 0) for row in sources.to_dict("records")]
    scale_order = sources.sort_values("field_width_um").iloc[
        np.linspace(0, len(sources) - 1, max(0, args.patch_count - len(requests)), dtype=int)
    ]
    requests.extend((row, 1) for row in scale_order.to_dict("records"))
    requests = requests[: args.patch_count]

    rows = []
    for index, (record, variant) in enumerate(requests, 1):
        roi, detected_pixel_size, _, _ = load_sem(data_root / record["relative_path"])
        pixel_size = detected_pixel_size if detected_pixel_size is not None else float(record["pixel_size_um"])
        patch_size = min(args.patch_size, roi.shape[0], roi.shape[1])
        if variant == 0:
            y0, x0 = (roi.shape[0] - patch_size) // 2, (roi.shape[1] - patch_size) // 2
        else:
            y0 = max(0, int(0.16 * roi.shape[0]) - patch_size // 2)
            x0 = max(0, int(0.78 * roi.shape[1]) - patch_size // 2)
            y0, x0 = min(y0, roi.shape[0] - patch_size), min(x0, roi.shape[1] - patch_size)
        patch = roi[y0:y0 + patch_size, x0:x0 + patch_size]
        patch_id = f"SEMANN-{index:03d}"
        Image.fromarray(np.round(np.clip(patch, 0, 1) * 255).astype(np.uint8)).save(image_dir / f"{patch_id}.png")
        rows.append({
            "patch_id": patch_id,
            "source_relative_path": record["relative_path"],
            "condition_key": record["condition_key"],
            "split": split_map[record["condition_key"]],
            "x0_px": x0,
            "y0_px": y0,
            "width_px": patch_size,
            "height_px": patch_size,
            "pixel_size_um": pixel_size,
            "patch_width_um": patch_size * pixel_size,
            "field_width_um": record["field_width_um"],
            "annotator_a_status": "pending",
            "annotator_b_status": "pending",
            "adjudication_status": "pending",
        })
    annotation = pd.DataFrame(rows)
    # Rank-based binning stays balanced even when several images share an
    # identical calibrated field width.
    annotation["magnification_stratum"] = pd.qcut(
        annotation["field_width_um"].rank(method="first"), 2, labels=["fine", "coarse"]
    ).astype(str)
    annotation.to_csv(root / "annotation_manifest.csv", index=False)
    print(f"Created {len(rows)} annotation patches from {len(sources)} SEM sources and {sources['condition_key'].nunique()} conditions.")


if __name__ == "__main__":
    main()
