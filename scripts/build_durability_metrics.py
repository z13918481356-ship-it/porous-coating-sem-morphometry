from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))

import numpy as np
import pandas as pd


TARGETS = ["contact_angle_deg", "hysteresis_deg", "rolloff_angle_deg", "pinning_fraction"]
SERIES_FIELDS = ["primer", "material", "sieving", "coating_method", "test_type"]


def _slope(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 and np.unique(x).size >= 2 else np.nan


def _time_average(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or x[-1] == x[0]:
        return np.nan
    return float(np.trapezoid(y, x) / (x[-1] - x[0]))


def main() -> None:
    output_root = PROJECT / "outputs"
    properties = pd.read_csv(output_root / "properties_clean.csv")
    trajectory = properties[properties["cycle"].notna() & properties["test_type"].isin(["tape", "abrasion"])].copy()
    trajectory["cycle"] = trajectory["cycle"].astype(int)
    trajectory["durability_series_key"] = trajectory[SERIES_FIELDS].astype(str).agg("|".join, axis=1)
    trajectory = (
        trajectory.groupby(["durability_series_key", *SERIES_FIELDS, "cycle"], as_index=False)[TARGETS]
        .mean(numeric_only=True)
        .sort_values(["durability_series_key", "cycle"])
    )

    summaries = []
    threshold_rows = []
    for series_key, group in trajectory.groupby("durability_series_key"):
        group = group.sort_values("cycle")
        row = {"durability_series_key": series_key, **{field: group.iloc[0][field] for field in SERIES_FIELDS}}
        row["observed_cycles"] = int(group["cycle"].nunique())
        row["max_observed_cycle"] = int(group["cycle"].max())
        for target in TARGETS:
            observed = group[["cycle", target]].dropna().sort_values("cycle")
            prefix = target.replace("_deg", "").replace("_fraction", "")
            if observed.empty:
                for suffix in ["baseline", "final", "change", "slope_per_cycle", "time_average"]:
                    row[f"{prefix}_{suffix}"] = np.nan
                continue
            x, y = observed["cycle"].to_numpy(float), observed[target].to_numpy(float)
            row[f"{prefix}_baseline"] = y[0]
            row[f"{prefix}_final"] = y[-1]
            row[f"{prefix}_change"] = y[-1] - y[0]
            row[f"{prefix}_slope_per_cycle"] = _slope(x, y)
            row[f"{prefix}_time_average"] = _time_average(x, y)
        if np.isfinite(row.get("contact_angle_baseline", np.nan)) and row["contact_angle_baseline"] != 0:
            row["contact_angle_retention_fraction"] = row["contact_angle_final"] / row["contact_angle_baseline"]
        else:
            row["contact_angle_retention_fraction"] = np.nan

        # Operational failure is descriptive, not a universal material law.
        failure = (
            (group["contact_angle_deg"].notna() & (group["contact_angle_deg"] < 150))
            | (group["hysteresis_deg"].notna() & (group["hysteresis_deg"] > 10))
            | (group["rolloff_angle_deg"].notna() & (group["rolloff_angle_deg"] > 10))
            | (group["pinning_fraction"].notna() & (group["pinning_fraction"] > 0.5))
        )
        row["composite_failure_observed"] = bool(failure.any())
        row["first_composite_failure_cycle"] = int(group.loc[failure, "cycle"].min()) if failure.any() else np.nan
        row["right_censored_cycle"] = np.nan if failure.any() else int(group["cycle"].max())
        summaries.append(row)

        for ca_threshold in [145, 150, 155]:
            failed = group["contact_angle_deg"].notna() & (group["contact_angle_deg"] < ca_threshold)
            threshold_rows.append({
                "durability_series_key": series_key,
                "contact_angle_failure_threshold_deg": ca_threshold,
                "failure_observed": bool(failed.any()),
                "first_failure_cycle": int(group.loc[failed, "cycle"].min()) if failed.any() else np.nan,
                "right_censored_cycle": np.nan if failed.any() else int(group["cycle"].max()),
            })

    trajectory.to_csv(output_root / "durability_trajectories.csv", index=False)
    pd.DataFrame(summaries).to_csv(output_root / "durability_summary.csv", index=False)
    pd.DataFrame(threshold_rows).to_csv(output_root / "durability_threshold_sensitivity.csv", index=False)
    print(f"Wrote {len(trajectory)} cycle observations for {len(summaries)} durability series.")


if __name__ == "__main__":
    main()
