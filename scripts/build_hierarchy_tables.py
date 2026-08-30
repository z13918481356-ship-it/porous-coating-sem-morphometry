from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

import pandas as pd

from morphometry.pipeline import FEATURES, TARGETS


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:10]}"


def main() -> None:
    outputs = PROJECT / "outputs"
    destination = outputs / "data_model"
    destination.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(outputs / "image_manifest.csv")
    morphometry = pd.read_csv(outputs / "morphometry_features.csv")
    properties = pd.read_csv(outputs / "properties_clean.csv")
    all_conditions = sorted(set(manifest["condition_key"]) | set(properties["condition_key"]))
    condition_ids = {key: stable_id("COND", key) for key in all_conditions}

    metadata_columns = ["primer", "material", "sieving", "coating_method", "test_type", "cycle", "spray_cycle"]
    condition_rows = []
    for key in all_conditions:
        candidates = pd.concat([
            manifest.loc[manifest["condition_key"] == key, metadata_columns],
            properties.loc[properties["condition_key"] == key, metadata_columns],
        ], ignore_index=True)
        first = candidates.iloc[0].to_dict() if len(candidates) else {}
        condition_rows.append({"condition_id": condition_ids[key], "condition_key": key, **first})
    conditions = pd.DataFrame(condition_rows)
    conditions.to_csv(destination / "conditions.csv", index=False)

    field_columns = [column for column in FEATURES if column in morphometry.columns]
    sem = morphometry.copy()
    sem.insert(0, "sem_field_id", [stable_id("FIELD", value) for value in sem["relative_path"]])
    sem.insert(1, "condition_id", sem["condition_key"].map(condition_ids))
    sem.insert(2, "coupon_id", pd.NA)
    sem.insert(3, "coupon_id_status", "not_provided_by_source")
    sem[
        ["sem_field_id", "condition_id", "coupon_id", "coupon_id_status", "condition_key", "relative_path",
         "figure_folder", "image_role", "view", "pixel_size_um", "field_width_um", "analysis_inclusion"] + field_columns
    ].to_csv(destination / "sem_fields.csv", index=False)

    prop = properties.copy()
    prop.insert(0, "property_measurement_id", [stable_id("PROP", value) for value in prop["relative_path"]])
    prop.insert(1, "condition_id", prop["condition_key"].map(condition_ids))
    prop.insert(2, "coupon_id", pd.NA)
    prop.insert(3, "coupon_id_status", "not_provided_by_source")
    property_columns = [
        "property_measurement_id", "condition_id", "coupon_id", "coupon_id_status", "condition_key",
        "relative_path", "contact_angle_deg", "contact_angle_sd_deg", "n_contact_angle",
        "contact_angle_value_source", "hysteresis_deg", "rolloff_angle_deg", "pinning_fraction",
    ]
    prop[property_columns].to_csv(destination / "property_measurements.csv", index=False)

    eligible_sem = sem[(sem["image_role"] == "coating") & (sem["view"] == "top") & sem["analysis_inclusion"]].copy()
    field_agg = eligible_sem.groupby("condition_id", as_index=False).agg(
        n_sem_fields=("sem_field_id", "nunique"), **{feature: (feature, "mean") for feature in field_columns}
    )
    prop_agg = prop.groupby("condition_id", as_index=False).agg(
        n_property_workbooks=("property_measurement_id", "nunique"),
        **{target: (target, "mean") for target in TARGETS},
    )
    analysis = conditions.merge(field_agg, on="condition_id", how="left").merge(prop_agg, on="condition_id", how="left")
    analysis["analysis_unit"] = "condition/test-state"
    analysis["coupon_level_inference_allowed"] = False
    analysis.to_csv(destination / "condition_level_analysis.csv", index=False)
    print(
        f"Wrote {len(conditions)} conditions, {len(sem)} SEM fields, {len(prop)} property workbooks, "
        f"and {analysis['n_sem_fields'].notna().sum()} condition-level SEM summaries."
    )


if __name__ == "__main__":
    main()
