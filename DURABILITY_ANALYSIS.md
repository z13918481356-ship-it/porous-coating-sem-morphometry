# Durability trajectory analysis

Durability is represented as a sequence of wetting observations over tape or abrasion cycles, not as a single static class. The unit of a trajectory is the combination of primer, material, sieving state, coating method, and test type.

## Outputs

- `outputs/durability_trajectories.csv`: one aggregated observation per series and cycle.
- `outputs/durability_summary.csv`: baseline, final value, absolute change, linear slope, time-averaged endpoint, contact-angle retention, and observed/censored failure cycle.
- `outputs/durability_threshold_sensitivity.csv`: first contact-angle failure under 145°, 150°, and 155° definitions.

## Operational failure definition

The primary descriptive composite flag is triggered by any available endpoint meeting: contact angle <150°, hysteresis >10°, roll-off angle >10°, or pinning fraction >0.5. These are transparent operational thresholds, not claimed universal physical constants. Missing endpoints do not trigger failure. A series with no observed failure is right-censored at its last measured cycle.

## Interpretation limits

Linear slopes summarize sparse, irregularly spaced trajectories and should not be extrapolated beyond observed cycles. The source does not expose coupon identifiers or repeated independent coupons, so the trajectory files support descriptive condition comparisons, not population-level survival inference.
