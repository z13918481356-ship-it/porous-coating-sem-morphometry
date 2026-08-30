# Expert segmentation annotation protocol

## Purpose

Create independent pixel-level ground truth for comparing Otsu, watershed-derived objects, and U-Net segmentation. The supplied Zenodo archive contains no expert masks; automated masks must never be copied into the reference directories.

## Sampling and split

`annotations/annotation_manifest.csv` contains 24 preselected 512 × 512 patches spanning all eligible top-view coating SEM sources, preparation/test states, and both fine/coarse physical-scale strata. Train, validation, and test assignment is made by `condition_key`, so patches or magnifications from one condition cannot cross splits.

## Label definition

Produce a single-channel binary PNG with the same dimensions and filename as the image patch:

- 255: foreground solid/coating material.
- 0: pore/void/background.
- Do not label scale bars, text, charging artifacts, or detector overlays; these have already been cropped where identifiable.
- Use the visible material boundary. Do not infer hidden bridges across dark gaps.
- Isolated bright debris is foreground only when its boundary is materially consistent with the coating texture; flag uncertain cases in the manifest notes rather than silently guessing.

## Independent annotation

1. Annotator A writes masks to `annotations/masks_annotator_a/`.
2. Annotator B annotates the same patches independently and writes masks to `annotations/masks_annotator_b/`.
3. Neither annotator views Otsu/watershed/U-Net predictions before completing their first pass.
4. Compute pairwise Dice, IoU, boundary F1, and area-fraction difference. Review every patch with Dice < 0.85 or boundary F1 < 0.75.
5. Resolve disagreements jointly and save the final reference mask to `annotations/masks_adjudicated/`.

## Acceptance gates

- All 24 filenames must have two independent masks and one adjudicated mask.
- Masks must be binary, shape-matched, and nonempty unless both annotators document a genuinely empty field.
- Report agreement by physical-scale stratum and by held-out condition split, not only as a pooled mean.
- U-Net test metrics are reported only on the untouched condition-level test split.

## Rebuild

Run `python scripts/build_annotation_set.py`. Rebuilding the image patches is deterministic, but existing human masks should be backed up first because the script intentionally does not create or overwrite any mask.
