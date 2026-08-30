from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DEPS = PROJECT / ".deps"
if DEPS.exists() and os.environ.get("SEM_USE_WORKSPACE_RUNTIME") != "1":
    sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(PROJECT / "src"))

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from morphometry.pipeline import FEATURES, TARGETS


def _models(seed: int) -> dict[str, object]:
    return {
        "Ridge": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=100.0)),
        ]),
        "Random Forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestRegressor(
                n_estimators=200, min_samples_leaf=2, max_features=0.7, random_state=seed, n_jobs=1
            )),
        ]),
    }


def _loocv_predictions(X: pd.DataFrame, y: np.ndarray, model: object | None) -> np.ndarray:
    prediction = np.full(len(y), np.nan)
    for train, test in LeaveOneOut().split(X):
        if model is None:
            prediction[test] = np.mean(y[train])
        else:
            model.fit(X.iloc[train], y[train])
            prediction[test] = model.predict(X.iloc[test])
    return prediction


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--permutations", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260829)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)

    data = pd.read_csv(PROJECT / "outputs" / "data_model" / "condition_level_analysis.csv")
    data = data[data["n_sem_fields"].notna()].copy()
    summaries, predictions, permutation_rows = [], [], []
    for target in TARGETS:
        subset = data[data[target].notna()].copy()
        if len(subset) < 6:
            summaries.append({
                "target": target, "model": "not_fit", "n_conditions": len(subset),
                "status": "descriptive_only_fewer_than_6_conditions",
            })
            continue
        X = subset[FEATURES]
        y = subset[target].to_numpy(float)
        baseline_pred = _loocv_predictions(X, y, None)
        baseline_mae = mean_absolute_error(y, baseline_pred)
        for model_name, model in {"Training-mean baseline": None, **_models(args.seed)}.items():
            pred = baseline_pred if model is None else _loocv_predictions(X, y, model)
            mae = mean_absolute_error(y, pred)
            skill = baseline_mae - mae
            p_value = np.nan
            if model is not None:
                permuted_skills = []
                for _ in range(args.permutations):
                    perm_y = rng.permutation(y)
                    perm_baseline = _loocv_predictions(X, perm_y, None)
                    perm_pred = _loocv_predictions(X, perm_y, _models(args.seed)[model_name])
                    permuted_skills.append(
                        mean_absolute_error(perm_y, perm_baseline) - mean_absolute_error(perm_y, perm_pred)
                    )
                p_value = (1 + np.sum(np.asarray(permuted_skills) >= skill)) / (args.permutations + 1)
                permutation_rows.extend({
                    "target": target, "model": model_name, "permutation_index": i + 1,
                    "mae_skill_vs_mean_baseline": value,
                } for i, value in enumerate(permuted_skills))
            summaries.append({
                "target": target,
                "model": model_name,
                "n_conditions": len(subset),
                "status": "evaluated_condition_level_loocv",
                "mae": mae,
                "median_absolute_error": float(np.median(np.abs(y - pred))),
                "r2_oof": r2_score(y, pred),
                "mae_skill_vs_mean_baseline": skill,
                "permutation_p_one_sided": p_value,
                "n_permutations": args.permutations if model is not None else 0,
            })
            predictions.extend({
                "condition_id": subset.iloc[i]["condition_id"], "condition_key": subset.iloc[i]["condition_key"],
                "target": target, "model": model_name, "observed": y[i], "predicted": pred[i],
            } for i in range(len(subset)))

    pd.DataFrame(summaries).to_csv(PROJECT / "outputs" / "small_data_model_results.csv", index=False)
    pd.DataFrame(predictions).to_csv(PROJECT / "outputs" / "small_data_oof_predictions.csv", index=False)
    pd.DataFrame(permutation_rows).to_csv(PROJECT / "outputs" / "small_data_permutation_null.csv", index=False)
    print(f"Evaluated {len(predictions)} condition-level out-of-fold predictions with {args.permutations} permutations/model.")


if __name__ == "__main__":
    main()
