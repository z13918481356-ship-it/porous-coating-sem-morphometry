from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))

import pandas as pd


EVIDENCE = {
    "Figure 3": "Dataset Figure 3 folder; manuscript Figure 3 identifies the baseline SP coating SEM and wetting measurements.",
    "Figure 4": "Dataset Figure 4 folder; manuscript Figure 4 contrasts sieved and unsieved SP coatings and reports their wetting/pinning behavior.",
    "Figure 5": "Dataset Figure 5 folder; manuscript Figure 5 identifies unsintered failure after tape cycle 1 and 900 C failure after tape cycle 5.",
    "Figure 6": "Dataset Figure 6 folder; manuscript Figure 6 identifies 900 C/PUR failure after abrasion cycle 15.",
    "Supplementary Figure S4": "Dataset Supplementary Figure S4 folder; file names identify the dip-coated preparation and matching wetting workbook.",
    "Supplementary Figure S7": "Dataset Supplementary Figure S7 folder; file names identify sieved/unsieved PUR preparations and matching wetting workbooks.",
}


def _figure(relative_path: str) -> str:
    return relative_path.split("/", 1)[0]


def main() -> None:
    output_root = PROJECT / "outputs"
    modeling = pd.read_csv(output_root / "modeling_dataset.csv")
    properties = pd.read_csv(output_root / "properties_clean.csv")
    manifest = pd.read_csv(output_root / "image_manifest.csv")

    property_paths = (
        properties.groupby("condition_key")["relative_path"]
        .apply(lambda values: " | ".join(sorted(set(values))))
        .to_dict()
    )
    rows = []
    for audit_id, record in enumerate(modeling.to_dict("records"), 1):
        rel = record["relative_path"]
        figure = _figure(rel)
        test_type = str(record.get("test_type", "none"))
        cycle = record.get("cycle")
        state = "baseline" if test_type == "none" else f"post-{test_type}, cycle {int(cycle)}"
        confidence = "high_condition_match"
        if figure in {"Figure 3", "Supplementary Figure S4"}:
            confidence = "medium_condition_match"
        rows.append({
            "audit_id": f"PAIR-{audit_id:02d}",
            "image_relative_path": rel,
            "condition_key": record["condition_key"],
            "property_workbook_paths": property_paths.get(record["condition_key"], ""),
            "preparation_test_state": state,
            "image_property_scope": "condition-level",
            "same_coupon_verified": False,
            "pairing_confidence": confidence,
            "contact_angle_deg": record.get("contact_angle_deg"),
            "hysteresis_deg": record.get("hysteresis_deg"),
            "rolloff_angle_deg": record.get("rolloff_angle_deg"),
            "pinning_fraction": record.get("pinning_fraction"),
            "pinning_semantics": "fraction pinned at 5 deg; lower is better; denominator 10 droplets",
            "evidence": EVIDENCE.get(figure, "Dataset folder and filename metadata."),
            "manual_review_status": "reviewed",
            "audit_note": "No coupon/specimen identifier is supplied; do not interpret as an exact specimen-level pairing.",
        })
    audit = pd.DataFrame(rows)
    audit.to_csv(output_root / "pairing_audit.csv", index=False)

    eligible = manifest[(manifest["image_role"] == "coating") & (manifest["view"] == "top")].copy()
    unmatched = eligible[~eligible["relative_path"].isin(set(modeling["relative_path"]))].copy()
    unmatched["exclusion_reason"] = "no exact condition/test/cycle property row"
    binder_mask = unmatched["condition_key"].astype(str).str.contains(r"binder\|PUR.*\|tape\|25", regex=True)
    unmatched.loc[binder_mask, "exclusion_reason"] = (
        "post-tape cycle-25 SEM exists, but the available binder wetting workbook is not cycle-resolved"
    )
    unmatched[["relative_path", "condition_key", "exclusion_reason"]].to_csv(
        output_root / "unmatched_sem_audit.csv", index=False
    )

    n_conditions = audit["condition_key"].nunique()
    n_workbooks = len({p for joined in audit["property_workbook_paths"] for p in joined.split(" | ") if p})
    text = f"""# SEM–property pairing audit

## Decision

The current joins are defensible only as **condition-level exploratory associations**. They are not specimen- or coupon-level supervised labels because the archive contains no unique coupon identifier shared by SEM images and wetting workbooks.

## Audited inventory

- Audited SEM rows: **{len(audit)}**
- Unique condition/test-state groups: **{n_conditions}**
- Property workbooks used: **{n_workbooks}**
- Exact coupon links verified: **0**
- Condition-level links supported by folder, filename, and manuscript figure context: **{len(audit)}**
- Unmatched eligible SEM images: **{len(unmatched)}**

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
"""
    (PROJECT / "PAIRING_AUDIT.md").write_text(text, encoding="utf-8")
    print(f"Wrote {len(audit)} audited pairs and {len(unmatched)} unmatched eligible SEM rows.")


if __name__ == "__main__":
    main()
