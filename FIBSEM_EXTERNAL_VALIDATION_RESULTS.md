# Locked FIB-SEM external validation result

## Decision

The unchanged global dark-pore Otsu pipeline **does not transfer reliably** to the independent porous-polymer FIB-SEM masks. Across the 24 locked official-test squares, median Dice is **0.584**, below the preregistered 0.70 partial-transfer boundary. This is a useful negative control and a defensible motivation for supervised or material-adaptive segmentation; it is not a license to retune the held-out test set.

## Data integrity and locked design

- Source: Zenodo record [4317170](https://doi.org/10.5281/zenodo.4317170), CC BY 4.0.
- Archive: `fib_sem_cnn.zip`, 9,216,974,498 bytes.
- Published and verified MD5: `a2884d289ed08f450692bd4fe8aa80b0`.
- Partition: authors' official test indices only.
- Sample: eight depth-targeted 256 x 256 squares from each of HPC22, HPC30, and HPC45; 24 total, with no replacements and no visual-quality exclusions.
- Reference semantics: author code computes porosity from `~M`; therefore `M=0` is pore.
- Frozen prediction: Gaussian sigma 1 px, global Otsu, dark class as pore, connected-component cleanup below `max(8, pixels x 1e-5)`, then hole filling.

The selection rule, polarity, cleanup, metrics, and acceptance thresholds were written in `FIBSEM_LOCKED_PROTOCOL.md` before the first reference score was inspected.

## Results

| Stratum | n | Dice median (IQR) | IoU median (IQR) | Boundary F1 median (IQR) | Absolute pore-fraction error median (IQR) |
|---|---:|---:|---:|---:|---:|
| All | 24 | 0.584 (0.476-0.762) | 0.413 (0.312-0.615) | 0.167 (0.113-0.239) | 0.142 (0.079-0.188) |
| HPC22 | 8 | 0.458 (0.363-0.489) | 0.297 (0.223-0.323) | 0.143 (0.087-0.162) | 0.187 (0.173-0.283) |
| HPC30 | 8 | 0.764 (0.717-0.798) | 0.618 (0.561-0.663) | 0.287 (0.220-0.349) | 0.082 (0.053-0.117) |
| HPC45 | 8 | 0.584 (0.509-0.754) | 0.413 (0.342-0.605) | 0.139 (0.112-0.216) | 0.119 (0.083-0.214) |

The best square is `FIBSEM-HPC30-SQ034-Z182` (Dice 0.830); the worst is `FIBSEM-HPC22-SQ082-Z063` (Dice 0.153). Retaining both is required by the locked protocol.

## Failure analysis

The overlays show that the expert masks trace comparatively large dark voids, whereas the global threshold also converts fine granular background texture and imaging noise into pore pixels. That produces extensive false-positive pore area, especially in HPC22. Even where area fraction is close, the low boundary F1 shows that geometrical contours remain inaccurate. The sharp HPC22/HPC30 contrast also demonstrates material-domain dependence rather than a universal threshold rule.

No evidence suggests an accidental mask-polarity inversion: the released author code fixes the semantics independently of score, and the diagnostic images place reference pores on visible dark voids.

## Consequence for the coating project

This benchmark validates the project's caution about contrast-sensitive classical segmentation. It does **not** validate coating morphometry numerically, because FIB-SEM porous polymers differ from the top-view coating SEM domain and contain no wetting or durability outcomes. The FIB-SEM rows must remain outside the morphology-property model.

The planned supervised comparison has now been completed using the released training/validation masks and a single frozen evaluation on all official test masks; see `FIBSEM_UNET_RESULTS.md`. Test-guided Otsu-factor searches or per-material threshold selection remain invalid external-validation procedures.
