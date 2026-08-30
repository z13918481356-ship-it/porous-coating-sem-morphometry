# Experimental-unit hierarchy

The archive supports condition-level, not coupon-level, inference. The normalized tables make that limitation explicit instead of encoding every SEM image as an independent sample.

| Level | Identifier | Meaning | Source support |
|---|---|---|---|
| Preparation/test state | `condition_id` | Material, binder/primer, sieving, coating method, durability test and cycle | Supported by folders and filenames |
| Physical coupon | `coupon_id` | One independently prepared/tested coated specimen | Not provided; kept null |
| SEM field | `sem_field_id` | One acquired/cropped image field | Supported |
| Property measurement file | `property_measurement_id` | One unique wetting workbook after SHA-256 de-duplication | Supported |

## Tables

- `outputs/data_model/conditions.csv`: one row per encoded preparation/test state.
- `outputs/data_model/sem_fields.csv`: image fields and morphometry; `coupon_id_status` prevents accidental specimen claims.
- `outputs/data_model/property_measurements.csv`: unique workbook-level endpoints and repeat metadata.
- `outputs/data_model/condition_level_analysis.csv`: field-averaged morphology and workbook-averaged properties, with the analysis unit declared as `condition/test-state`.

## Statistical rule

Use `condition_id` for grouped resampling and cross-validation. Multiple fields can improve the estimate of a condition's morphology but do not increase the number of independent preparations. A future dataset can populate `coupon_id`; only then should coupon-level bootstrap or mixed-effects random intercepts be used.
