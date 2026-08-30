# External data staging

External archives are not committed to Git.

- `paao_5905496/`: TIFF files from DOI 10.5281/zenodo.5905496.
- `fibsem_4317170/locked_subset/`: the preregistered 24-square classical benchmark subset from DOI 10.5281/zenodo.4317170.
- `fibsem_4317170/supervised_dataset/`: all 300 official train/validation/test squares reconstructed from the verified archive for the supervised benchmark.

Record downloaded filenames, checksums, extraction rules, and any excluded slices before running validation.

The 9.2 GB FIB-SEM archive, extracted TIFF/PNG pairs, partial downloads, and trained predictions are ignored by Git. Only compact manifests and source README/license information are versioned.
