# External segmentation validation

External data are used only to test segmentation transfer. They have no matching contact-angle or durability labels and are never appended to the morphology–wetting model.

## Channel A — PAAO multi-magnification domain shift

Zenodo 5905496 supplies 15 top-view PAAO SEM images: five anodization samples, each at 50,000×, 100,000×, and 200,000×. Dark regions are pores. Because no reference masks are supplied, this channel reports pore-fraction consistency across magnifications and visually reviewed failure cases; it does **not** report Dice/IoU or claim accuracy.

Place TIFFs in `external_data/paao_5905496/`, then run:

```powershell
python scripts/evaluate_external_segmentation.py --dataset paao --data-root external_data/paao_5905496
```

## Channel B — FIB-SEM independent mask benchmark

Zenodo 4317170 supplies a 9.2 GB research archive containing raw FIB-SEM volumes, manual segmentations, trained models, and results for porous EC/HPC polymer films. Extract a documented 2D subset without tuning on it, placing same-stem files in `external_data/fibsem_4317170/images/` and `external_data/fibsem_4317170/masks/`.

```powershell
python scripts/evaluate_external_segmentation.py --dataset fibsem --data-root external_data/fibsem_4317170 --pore-is-dark
```

The adapter reports Dice, IoU, boundary F1, and area-fraction error. Threshold polarity is declared before evaluation; it is not selected by whichever orientation scores better.

## Acceptance and interpretation

- Preserve a dataset-level holdout: no threshold tuning, model selection, or morphology-rule changes after viewing external mask scores.
- Report per-image distributions and failure cases, not only pooled means.
- PAAO tests cross-magnification stability; FIB-SEM tests pixelwise segmentation transfer.
- A drop in external performance is a domain-shift result, not a reason to relabel or silently exclude difficult images.
