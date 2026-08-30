# Data card

## Source

- Record: Sultan, U.; Walter, T.; Wachter, C.; Swart, L.; Vogel, N. (2025), *Dataset of the manuscript: A supraparticle-based approach to robust biomimetic superhydrophobic coatings*.
- DOI: https://doi.org/10.5281/zenodo.16054027
- License: Creative Commons Attribution 4.0 International.
- Downloaded archive checksum published by Zenodo: `md5:a6725e4d1958e0d587226b32cd71003a`.

## Contents used

The archive is organised by manuscript figure. It contains multi-magnification top/side-view SEM images, supraparticle size distributions, wetting measurements (contact angle, contact-angle hysteresis, roll-off angle, pinning fraction), and durability measurements across tape/abrasion cycles. Preparation descriptors include primer family (PDMS/PUR), sintering state, binder, sieving, coating method, and spray-cycle count where encoded by the source filename/folder.

## Unit of analysis

- **Image level:** one calibrated SEM field of view.
- **Property level:** one workbook associated with a preparation/test/cycle; droplet readings within a workbook are technical/within-condition replicates.
- **Model level:** preparation-condition groups. Multiple magnifications from one condition remain in the same fold.

## Exclusions

- Files beginning `._` and `.DS_Store` are macOS metadata/resource forks.
- Photographs, videos, chemical drawings, and non-SEM images are excluded from morphometry.
- Particle-only and lotus-reference SEMs are retained in the manifest but excluded from coating property models.
- Ambiguous SEM/property matches are retained separately and never forced into the supervised table.
- No optical properties are present. The dataset cannot support emissivity, reflectance, or absorptance prediction.

## Known limitations

1. Only a small number of independent coating conditions have SEM images; confidence intervals are therefore wide and model scores are exploratory.
2. The dataset lacks pixel-level masks, so supervised U-Net performance cannot be estimated without new annotation.
3. Threshold-based segmentation is contrast-sensitive and does not uniquely distinguish open pore space from shadowing/topography.
4. Some properties and SEMs are condition-level rather than measurements of the identical physical coupon/field of view.
5. Different magnifications sample different morphological scales; physical calibration does not make all texture descriptors directly equivalent.
6. Durability is represented by repeated test cycles, not a universal scalar lifetime. Cycle-specific outcomes should be preferred over collapsing to one number.

## External validation data

Zenodo record [5905496](https://doi.org/10.5281/zenodo.5905496) is used only as a PAAO cross-material/cross-magnification segmentation stress test. Its 15 TIFFs cover five samples at 50,000x, 100,000x, and 200,000x. The record provides no expert masks or wetting/durability endpoints. All 15 published MD5 checksums were verified locally. A 118-pixel FEI footer is removed before segmentation.

The PAAO TIFFs do not expose usable physical pixel calibration. Nominal magnification is therefore treated as an acquisition stratum, not converted to micrometres. External results cannot be merged into the coating property model, and pixel-scale pore diameter cannot be compared as a physical size.

Zenodo record [4317170](https://doi.org/10.5281/zenodo.4317170) supplies an independent-mask FIB-SEM benchmark for three porous-polymer strata (HPC22, HPC30, and HPC45). The 9,216,974,498-byte archive was downloaded and verified against the published MD5, `a2884d289ed08f450692bd4fe8aa80b0`. The benchmark uses 24 preregistered squares from the authors' official test partitions (eight per stratum); neither training nor validation squares are scored.

The authors' MATLAB postprocessing defines porosity as `mean(~M)`, so the released manual mask `M=1` is solid and `M=0` is pore. This semantic rule—not whichever polarity scores better—determines the reference-mask inversion. FIB-SEM images have no wetting or durability labels and are excluded from all structure-property models.

For the supervised benchmark, all 300 published manual squares are retained under the authors' official partitions: 180 train, 60 validation, and 60 test. One shared U-Net is fitted across the three materials. Model selection uses validation macro Dice only; the official test split is evaluated once after selecting the checkpoint. The earlier locked Otsu study had already exposed 24 test masks, but those images, masks, and scores are not used in U-Net fitting or selection.

## Ethical and appropriate use

The data contain no human subjects or personal information. Appropriate use is exploratory materials research, method development, and reproducibility education. Do not use the small fitted models as manufacturing-control models without independent validation.
