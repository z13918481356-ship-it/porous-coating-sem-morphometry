# Reproducibility checklist

This checklist separates deterministic pipeline checks from results that depend on public source archives. Raw data, extracted TIFFs, trained weights, partial downloads, and local dependency bundles are excluded from Git.

## Environment

- Python: 3.11 or newer; the completed supervised run used Python 3.12.
- Core packages: `requirements.txt`.
- Optional supervised benchmark: PyTorch 2.4 or newer.
- Fixed supervised seed: `20260830`.
- Primary source: Zenodo 16054027, CC BY 4.0.
- PAAO stress test: Zenodo 5905496.
- FIB-SEM independent masks: Zenodo 4317170, CC BY 4.0.

## Fast repository checks

```powershell
pip install -r requirements.txt pytest
pytest -q
python -m py_compile scripts/*.py src/morphometry/*.py
```

GitHub Actions runs the unit-test command without downloading research data.

## Primary coating workflow

Place the extracted main archive under `data/raw/zenodo_16054027/`, then run:

```powershell
python scripts/run_pipeline.py --data-root data/raw/zenodo_16054027 --output-root outputs
python scripts/build_pairing_audit.py
python scripts/build_annotation_set.py
python scripts/build_hierarchy_tables.py
python scripts/build_durability_metrics.py
python scripts/evaluate_small_data_models.py --permutations 200
python scripts/build_matched_scale_consistency.py
python scripts/build_report.py --output-root outputs --report-root report
```

Expected audit anchors:

- 28 inventoried SEM/SEM-like images, including 18 coating images.
- 88 unique valid property workbooks after cleaning.
- 11 matched SEM images across 8 independent preparation conditions.
- One segmentation failure excluded from modeling.
- Contact-angle Random Forest leave-one-condition-out MAE 2.62°, mean-baseline MAE 2.91°, permutation p=0.224.

Small floating-point differences across library versions are acceptable; sample counts, exclusions, condition grouping, and qualitative conclusions must remain unchanged.

## FIB-SEM archive integrity

Download record 4317170 with the provided resumable downloader:

```powershell
python scripts/fetch_zenodo_large_file.py 4317170 fib_sem_cnn.zip external_data/fibsem_4317170 --workers 4
```

Required final checks:

- Filename: `fib_sem_cnn.zip`.
- Size: 9,216,974,498 bytes.
- MD5: `a2884d289ed08f450692bd4fe8aa80b0`.

Do not train from the locked 24-square convenience subset. The supervised extractor must reconstruct all official partitions directly from the verified archive.

## Supervised FIB-SEM workflow

```powershell
pip install torch
python scripts/extract_fibsem_supervised_dataset.py
python scripts/train_fibsem_unet.py
python scripts/build_fibsem_unet_diagnostics.py
```

Partition assertions:

- Train: 180 squares, 60 per material.
- Validation: 60 squares, 20 per material.
- Test: 60 squares, 20 per material.
- The three partitions must contain 300 unique official square indices in total.

Expected frozen run anchors:

- Best epoch: 26.
- Best validation macro Dice: approximately 0.815.
- Early stop: epoch 41 under patience 15.
- Official test evaluations: one.
- U-Net overall median Dice: approximately 0.805.
- Frozen Otsu overall median Dice on the same 60 squares: approximately 0.604.
- Paired median Dice gain: approximately 0.182; 10,000-replicate bootstrap 95% CI 0.148-0.201.
- U-Net wins 58 of 60 paired squares.
- Strict acceptance result: fail, because overall median Dice is below 0.85 and HPC22 median Dice is below 0.80.

CPU/GPU kernels and newer library versions can introduce small numeric differences. Any run that changes sample selection, the 0.5 threshold, loss, architecture, early-stopping rule, or model-selection metric is a new experiment and must not be presented as a direct reproduction.

## Leakage checks

- Multiple magnifications from one preparation condition stay in the same modeling fold.
- Technical droplet readings do not become independent material samples.
- U-Net test images and masks are unavailable to fitting and validation-based checkpoint selection.
- PAAO and FIB-SEM features never enter coating wetting or durability tables.
- The official FIB-SEM test split must not be reused for further architecture or threshold development.
