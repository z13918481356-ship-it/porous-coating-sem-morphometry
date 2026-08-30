# Model card: compact FIB-SEM pore U-Net

## Model details

- Task: binary pore/solid segmentation of 256 x 256 porous-polymer FIB-SEM squares.
- Architecture: compact two-level U-Net, one grayscale input channel, one pore logit, base width 16.
- Parameters: 117,393.
- Framework: PyTorch 2.13.0+cpu.
- Checkpoint: `outputs/models/fibsem_unet_best.pt`, 496,929 bytes.
- SHA-256: `2C4A0F5E8C58AD5FDCF3F846B6DAB354C6F9E10F3E9878EA2443B05D5FBB2785`.
- Selected epoch: 26 of 41 completed epochs.

## Intended use

Research benchmarking and error analysis on images sampled consistently with HPC22, HPC30, and HPC45 in Zenodo record 4317170. Predictions should be reviewed when used for object-level morphometry.

## Out-of-scope use

- Claiming validated segmentation of the supraparticle coating SEM dataset.
- Predicting wetting, durability, optical, biological, or manufacturing outcomes.
- Treating predicted masks as expert annotation.
- Fine-tuning or selecting thresholds on the published official test partition and continuing to call it held out.

## Training and evaluation

The authors' official 180/60/60 train/validation/test split is used without exclusions. Inputs are per-square percentile normalized. Training augmentation uses only rotations by multiples of 90 degrees and optional horizontal reflection. Checkpoint selection uses fixed-threshold validation macro Dice across three material strata. See `FIBSEM_UNET_LOCKED_PROTOCOL.md` for the complete frozen specification.

Official-test median Dice is 0.805 overall, 0.764 on HPC22, 0.850 on HPC30, and 0.822 on HPC45. The model fails the locked overall and HPC22 reliability gates. Its worst test prediction labels nearly the complete image as pore.

## Limitations and risk controls

- Only three related porous-polymer materials are represented.
- Manual masks are limited to 100 squares per material.
- Strong acquisition artifacts can cause near-total class collapse.
- Boundary F1 is substantially lower than region Dice, limiting precise shape descriptors.
- There is no independent coating-domain ground truth.

Use the published per-square metrics, stratified summaries, and diagnostic overlays rather than citing a single aggregate score.
