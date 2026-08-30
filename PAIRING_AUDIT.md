# SEM–property pairing audit

## Decision

The current joins are defensible only as **condition-level exploratory associations**. They are not specimen- or coupon-level supervised labels because the archive contains no unique coupon identifier shared by SEM images and wetting workbooks.

## Audited inventory

- Audited SEM rows: **11**
- Unique condition/test-state groups: **8**
- Property workbooks used: **8**
- Exact coupon links verified: **0**
- Condition-level links supported by folder, filename, and manuscript figure context: **11**
- Unmatched eligible SEM images: **6**

Each accepted row is documented in `outputs/pairing_audit.csv`; exclusions are documented in `outputs/unmatched_sem_audit.csv`.

## Endpoint semantics

- Contact angle is the workbook's reported `CA/Stabw` mean. Static replicate count is derived only from the T-1 rows above that summary; later T-1 rows are dynamic traces and must not be counted as independent replicates.
- Contact-angle hysteresis is reported from advancing/receding measurements.
- Roll-off angle is an angle in degrees; the paper reports one test per case using three droplets.
- Pinning fraction is the number pinned among ten 10 µL droplets placed on a surface held at 5°. Therefore **0 is best and 1 is worst**.

## Leakage and inference rule

All images from the same `condition_key` must remain in the same cross-validation fold. Statistical summaries should aggregate images to the condition/test-state level or use a hierarchical model; image rows must not be presented as independent experimental replicates.

## Known exclusion

The Figure 6 binder/PUR SEM images after tape cycle 25 are excluded: the archive includes a binder wetting workbook, but it is not resolved to the cycle-25 test state. Joining that baseline/general workbook to the failure-state SEM would be an unsupported label assignment.

## Evidence sources

- Zenodo record 16054027 and its folder/file organization.
- Sultan et al., *Small* (2025), manuscript figure captions and methods (PMCID: PMC12548018; PMID: 40911764).
