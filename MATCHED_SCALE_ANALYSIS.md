# Cross-magnification consistency at matched physical scale

Full-frame features confound magnification with both field size and pixel sampling. The matched-scale analysis applies two controls within each condition that has multiple calibrated magnifications:

1. Crop the same physical window size (80% of the smallest available image dimension) from each image center.
2. Downsample every crop to the coarsest native pixel size in that condition before segmentation and feature extraction.

`outputs/matched_scale_features.csv` contains the recomputed image features. `outputs/matched_scale_consistency.csv` reports within-condition coefficient of variation and relative range, alongside the earlier full-frame relative difference.

These are not registered repeat images of the identical surface coordinates, so residual disagreement combines field heterogeneity, acquisition differences, and segmentation error. The analysis tests scale robustness; it cannot establish pixelwise repeatability.
