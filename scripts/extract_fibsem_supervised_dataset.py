from __future__ import annotations

import csv
import io
import os
import sys
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
RUNTIME_DEPS = PROJECT / "runtime_deps"
if RUNTIME_DEPS.exists():
    sys.path.insert(0, str(RUNTIME_DEPS))
elif DEPS.exists():
    sys.path.insert(0, str(DEPS))

import numpy as np
from PIL import Image


DATASETS = ["HPC22", "HPC30", "HPC45"]
SPLITS = {"train": "train", "validation": "val", "test": "test"}


def load_npy(archive: ZipFile, name: str) -> np.ndarray:
    return np.load(io.BytesIO(archive.read(name)), allow_pickle=False)


def main() -> None:
    archive_path = PROJECT / "external_data" / "fibsem_4317170" / "fib_sem_cnn.zip"
    destination = PROJECT / "external_data" / "fibsem_4317170" / "supervised_dataset"
    rows: list[dict[str, object]] = []

    with ZipFile(archive_path) as archive:
        for material in DATASETS:
            regions = load_npy(archive, f"data/manual_segmentation/segmentation_regions_{material}.npy")
            manual = load_npy(archive, f"data/manual_segmentation/manual_segmentation_{material}.npy")
            assignments: list[dict[str, object]] = []
            all_indices: list[int] = []
            for split, archive_split in SPLITS.items():
                indices = load_npy(
                    archive, f"data/regions/ind_squares_{archive_split}_{material}.npy"
                ).reshape(-1).astype(int)
                all_indices.extend(indices.tolist())
                for square_index in indices:
                    x, y, z = (int(value) for value in regions[:, square_index])
                    assignments.append({
                        "split": split, "square_index": int(square_index),
                        "x": x, "y": y, "z": z,
                    })
            if len(all_indices) != 100 or len(set(all_indices)) != 100:
                raise ValueError(f"Official partitions for {material} do not form 100 disjoint squares")

            by_z: dict[int, list[dict[str, object]]] = defaultdict(list)
            for assignment in assignments:
                by_z[int(assignment["z"])].append(assignment)
            for z, z_assignments in sorted(by_z.items()):
                source_name = f"data/raw/{material}/{material}_{z + 1:04d}.tif"
                with Image.open(io.BytesIO(archive.read(source_name))) as source:
                    raw = np.asarray(source)
                for assignment in z_assignments:
                    split = str(assignment["split"])
                    square_index = int(assignment["square_index"])
                    x, y = int(assignment["x"]), int(assignment["y"])
                    crop = raw[x:x + 256, y:y + 256]
                    if crop.shape != (256, 256):
                        raise ValueError(f"Unexpected crop shape for {material} square {square_index}: {crop.shape}")
                    pore_mask = ~manual[square_index].astype(bool)
                    stem = f"FIBSEM-{material}-SQ{square_index:03d}-Z{z:03d}"
                    image_dir = destination / split / "images"
                    mask_dir = destination / split / "masks"
                    image_dir.mkdir(parents=True, exist_ok=True)
                    mask_dir.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(crop).save(image_dir / f"{stem}.tif")
                    Image.fromarray((pore_mask * 255).astype(np.uint8)).save(mask_dir / f"{stem}.png")
                    rows.append({
                        "pair_id": stem, "material": material, "split": split,
                        "square_index": square_index, "x_start": x, "y_start": y,
                        "z_index_zero_based": z, "source_zip_path": source_name,
                        "reference_semantics": "255=pore; derived from manual M=0",
                    })

    rows.sort(key=lambda row: (str(row["split"]), str(row["material"]), int(row["square_index"])))
    with (destination / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["split"])] += 1
    print(f"Extracted {len(rows)} official squares: {dict(counts)}")


if __name__ == "__main__":
    main()
