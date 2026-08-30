# Locked FIB-SEM external benchmark protocol

Protocol frozen before downloading or inspecting `fib_sem_cnn.zip` from Zenodo record 4317170.

## Scope

This benchmark evaluates the unchanged classical dark-pore segmentation rule on an independent porous-polymer FIB-SEM domain. It does not tune Otsu factors, morphology parameters, polarity, slice selection, or postprocessing against reference scores.

## Data partition

- Use only the authors' official **test** partition from `data/split` or the exact test-region indices stored in `data/regions/ind_squares*.npy`.
- Do not use training or validation regions for the reported external score.
- Keep HPC22, HPC30, and HPC45 as three separate domain strata.

## Slice selection

Archive-layout clarification made before any segmentation score was computed: the official test partition consists of 20 manually segmented 256 x 256 squares per material, each with an `(x, y, z)` source coordinate. For each material, sort those official test squares by `z` and select the square nearest to eight normalized test-depth targets:

`0.10, 0.20, 0.30, 0.40, 0.60, 0.70, 0.80, 0.90`

Map each target to the nearest available test-square `z`. Require unique square indices; break distance ties toward lower `z`, then lower square index. If a selected reference mask contains only one class, move to the nearest unused test square containing both classes. Record every replacement. No visual-quality filtering is allowed.

Target benchmark size: 24 slices total, eight per material stratum.

## Frozen segmentation rule

- Pores are declared the dark class before reference scores are viewed.
- Gaussian smoothing sigma: 1 pixel.
- Global Otsu threshold.
- Remove connected pore components smaller than `max(8, image_pixels x 1e-5)`.
- Fill internal holes.
- No dataset- or magnification-specific threshold adjustment.

If the authors' mask coding uses solid=1 rather than pore=1, invert the reference according to the supplied code/readme semantics, not according to whichever orientation scores better.

The supplied `postprocessing.m` computes porosity as `mean(~M)`, confirming manual mask `M=1` is solid and the reference pore mask is `M=0`.

## Metrics

Report per-slice and per-material:

- Dice
- Intersection over Union
- boundary F1 at 2-pixel tolerance
- absolute area-fraction error

Primary summary: median and interquartile range across the 24 locked slices. Retain all selected slices, including failures.

## Acceptance interpretation

- Median Dice >= 0.85 and median boundary F1 >= 0.75: classical rule is a credible external baseline.
- Median Dice 0.70-0.85: partial transfer; report domain limitations.
- Median Dice < 0.70: transfer failure; use as motivation for expert-supervised adaptation, not threshold retuning on the test set.

The FIB-SEM data have no wetting labels and must never enter the coating structure-property model.
