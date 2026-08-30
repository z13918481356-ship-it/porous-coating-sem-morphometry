# PAAO external validation results

## Execution status

- Source: Zenodo record 5905496, CC BY 4.0.
- Files: 15 TIFFs, 174,177,938 bytes total.
- Integrity: 15/15 files match the MD5 values published by Zenodo.
- Structure: five samples (AJ-1 to AJ-5), each at nominal 50,000x, 100,000x, and 200,000x.
- Preprocessing correction: every TIFF contains a dark 118-pixel FEI information footer. It is detected and removed before Otsu/morphology segmentation.
- Physical calibration: unavailable in TIFF metadata, so no micrometre-scale pore diameter is reported.

## Findings

The adapter executes successfully on all images and visually identifies the regular dark-pore arrays. However, absolute segmentation measurements are magnification-sensitive:

| Sample | Pore-fraction range | Relative range | Monotonic with magnification |
|---|---:|---:|---|
| AJ-1 | 0.067 | 24.0% | No |
| AJ-2 | 0.061 | 19.8% | No |
| AJ-3 | 0.036 | 14.1% | No |
| AJ-4 | 0.075 | 33.4% | Yes |
| AJ-5 | 0.061 | 24.4% | Yes |

All five samples trigger the high-magnification fragmentation flag: median connected-component diameter at 200,000x is only 0.45-0.51 times its 50,000x pixel value. This is incompatible with interpreting the component statistic as a transferable physical pore diameter.

Relative sample ordering is much more stable. Across the five samples, pore-area-fraction ranks have Spearman rho = 0.90 for 50,000x versus 100,000x, rho = 0.90 for 50,000x versus 200,000x, and rho = 1.00 for 100,000x versus 200,000x.

## Decision

PAAO supports an **ordinal transfer claim**: the pipeline largely preserves which samples have higher or lower segmented pore fraction. It does not support an **absolute transfer claim** for pore fraction or connected-component size.

Use the PAAO output as a domain-shift stress test and failure-case demonstration. Do not pool it with the coating dataset, tune thresholds separately at each magnification, or report Dice/IoU without new expert masks.

## Next gate

Before claiming external segmentation accuracy, annotate at least two PAAO fields per magnification independently and adjudicate them, or extract a locked same-stem image/mask subset from Zenodo 4317170. Thresholds and polarity must be frozen before viewing those reference-mask scores.

## Generated artifacts

- `external_data/paao_5905496/download_manifest.csv`
- `outputs/external_paao_features.csv`
- `outputs/external_paao_scale_consistency.csv`
- `outputs/external_paao_rank_consistency.csv`
- `outputs/external_paao_failure_cases.csv`
- `outputs/external_validation/paao_segmentation_diagnostics.png`
