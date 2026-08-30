from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import numpy as np
from PIL import Image


DATASETS = ["HPC22", "HPC30", "HPC45"]
QUANTILES = [0.10, 0.20, 0.30, 0.40, 0.60, 0.70, 0.80, 0.90]


def load_npy(archive: ZipFile, name: str) -> np.ndarray:
    return np.load(io.BytesIO(archive.read(name)), allow_pickle=False)


def main() -> None:
    archive_path = PROJECT / "external_data" / "fibsem_4317170" / "fib_sem_cnn.zip"
    destination = PROJECT / "external_data" / "fibsem_4317170" / "locked_subset"
    image_dir, mask_dir = destination / "images", destination / "masks"
    image_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    with ZipFile(archive_path) as archive:
        for dataset in DATASETS:
            regions = load_npy(archive, f"data/manual_segmentation/segmentation_regions_{dataset}.npy")
            manual = load_npy(archive, f"data/manual_segmentation/manual_segmentation_{dataset}.npy")
            test_indices = load_npy(archive, f"data/regions/ind_squares_test_{dataset}.npy").reshape(-1).astype(int)
            candidates = []
            for square_index in test_indices:
                x, y, z = (int(value) for value in regions[:, square_index])
                mask_solid = manual[square_index].astype(bool)
                candidates.append({
                    "square_index": int(square_index), "x": x, "y": y, "z": z,
                    "both_classes": bool(mask_solid.any() and (~mask_solid).any()),
                })
            z_min, z_max = min(item["z"] for item in candidates), max(item["z"] for item in candidates)
            selected: set[int] = set()
            for quantile in QUANTILES:
                target_z = z_min + quantile * (z_max - z_min)
                ranked = sorted(
                    candidates,
                    key=lambda item: (
                        not item["both_classes"], item["square_index"] in selected,
                        abs(item["z"] - target_z), item["z"], item["square_index"],
                    ),
                )
                chosen = next(item for item in ranked if item["both_classes"] and item["square_index"] not in selected)
                selected.add(chosen["square_index"])
                slice_number = chosen["z"] + 1
                source_name = f"data/raw/{dataset}/{dataset}_{slice_number:04d}.tif"
                with Image.open(io.BytesIO(archive.read(source_name))) as source:
                    raw = np.asarray(source)
                crop = raw[chosen["x"]:chosen["x"] + 256, chosen["y"]:chosen["y"] + 256]
                if crop.shape != (256, 256):
                    raise ValueError(f"Unexpected crop shape for {dataset} square {chosen['square_index']}: {crop.shape}")
                pore_mask = ~manual[chosen["square_index"]].astype(bool)
                stem = f"FIBSEM-{dataset}-SQ{chosen['square_index']:03d}-Z{chosen['z']:03d}"
                Image.fromarray(crop).save(image_dir / f"{stem}.tif")
                Image.fromarray((pore_mask * 255).astype(np.uint8)).save(mask_dir / f"{stem}.png")
                rows.append({
                    "pair_id": stem, "dataset": dataset, "official_partition": "test",
                    "target_depth_quantile": quantile, "square_index": chosen["square_index"],
                    "x_start": chosen["x"], "y_start": chosen["y"], "z_index_zero_based": chosen["z"],
                    "source_zip_path": source_name, "reference_semantics": "255=pore; derived from manual M=0",
                    "selection_replacement": "none",
                })

    with (destination / "locked_subset_manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    print(f"Extracted {len(rows)} locked image/mask pairs to {destination}")


if __name__ == "__main__":
    main()
