# Small-data modeling rules

- The modeling row is one `condition/test-state`, obtained by averaging valid SEM fields within that condition.
- A condition with multiple magnifications contributes one response, not multiple independent samples.
- Endpoints with fewer than six labeled conditions are marked descriptive-only.
- Ridge and Random Forest use fixed, conservative hyperparameters and leave-one-condition-out predictions.
- The required comparator is a training-fold mean baseline.
- Predictive skill is `baseline MAE − model MAE`; positive is better.
- A one-sided target-permutation test asks whether observed MAE skill is larger than expected when morphology and the endpoint are unrelated.

With only 6–8 eligible conditions, these results are feasibility estimates. A nonsignificant permutation result is evidence against a predictive claim, even if an isolated correlation is large.
