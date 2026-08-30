# Supervised FIB-SEM U-Net benchmark result

## Decision

The compact supervised U-Net produces a large, consistent improvement over frozen Otsu, but it **does not pass the preregistered reliability gate**. Overall official-test median Dice is 0.805 rather than the required 0.85, and HPC22 median Dice is 0.764 rather than the required 0.80. The correct claim is therefore “substantial supervised improvement with residual material-specific failures,” not “validated universal pore segmentation.”

## Frozen experiment

- Data: Zenodo record [4317170](https://doi.org/10.5281/zenodo.4317170), CC BY 4.0.
- Official partitions: 180 train, 60 validation, 60 test; 20 test squares per material.
- Architecture: repository compact two-level U-Net, base width 16, 117,393 parameters.
- Loss: 0.5 binary cross-entropy with logits + 0.5 soft Dice loss.
- Optimizer: AdamW, learning rate 0.001, weight decay 0.0001, batch size 8.
- Selection: fixed 0.5 probability threshold; highest validation macro Dice across HPC22/HPC30/HPC45.
- Training: seed 20260830; early stopping after 15 non-improving epochs.
- Selected checkpoint: epoch 26, validation macro Dice 0.815; training stopped at epoch 41.
- Test usage: one evaluation after checkpoint selection.

## Official-test results

| Method | Stratum | n | Dice median (IQR) | IoU median (IQR) | Boundary F1 median (IQR) | Absolute pore-fraction error median (IQR) |
|---|---|---:|---:|---:|---:|---:|
| U-Net | All | 60 | 0.805 (0.752-0.860) | 0.673 (0.603-0.754) | 0.293 (0.246-0.325) | 0.040 (0.023-0.071) |
| U-Net | HPC22 | 20 | 0.764 (0.746-0.795) | 0.618 (0.595-0.659) | 0.313 (0.293-0.340) | 0.025 (0.016-0.043) |
| U-Net | HPC30 | 20 | 0.850 (0.817-0.881) | 0.739 (0.691-0.788) | 0.280 (0.249-0.313) | 0.041 (0.029-0.070) |
| U-Net | HPC45 | 20 | 0.822 (0.731-0.880) | 0.698 (0.576-0.786) | 0.253 (0.181-0.301) | 0.063 (0.032-0.128) |
| Otsu | All | 60 | 0.604 (0.516-0.750) | 0.433 (0.347-0.600) | 0.212 (0.122-0.262) | 0.118 (0.078-0.182) |

The paired median Dice gain is **0.182**, with a 10,000-replicate paired bootstrap 95% interval of **0.148 to 0.201**. U-Net outperforms Otsu on 58 of 60 squares. Median absolute pore-fraction error falls from 0.118 to 0.040.

## Failure analysis

The most severe test failure is `FIBSEM-HPC30-SQ085-Z161`: U-Net predicts pore fraction 0.998 instead of the reference 0.250 (Dice 0.400). Frozen Otsu also predicts nearly all pore on this acquisition (pore fraction 0.966; Dice 0.410), indicating an extreme contrast/artifact case rather than an isolated neural-network error.

Boundary F1 remains low even when region Dice is acceptable. Visual overlays show smooth contour offsets wider than the strict two-pixel tolerance, plus missed or merged narrow voids. HPC22 has the weakest median region overlap, while high-porosity HPC45 cases contribute several lower-tail failures. These errors would bias connectivity, circularity, and spacing more strongly than they bias total area fraction.

## Scientific scope

The supervised result demonstrates that learned spatial context is substantially better than a global threshold on this FIB-SEM domain. It does not provide coating-domain U-Net accuracy because the primary top-view coating SEMs still lack expert masks. FIB-SEM predictions and features must not be joined to contact-angle or durability endpoints.

Any further architecture, loss, threshold, or material-specific adaptation now requires a new untouched evaluation set or nested validation design. The official test split must not become a development set.
