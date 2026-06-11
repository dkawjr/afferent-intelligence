# Power & sample-size scoping

**Question:** Is intraoperative hypotension associated with postoperative acute kidney injury?

> Rough scoping guidance — not a substitute for a formal power analysis. Plug your event rate and effect size into G*Power or `statsmodels` once you have them.

## Starting points
- VitalDB has ~6,388 cases total; your analyzable N is the intersection of your cohort filters and the cases that actually have the required tracks.
- **Mean Arterial Pressure (MAP)** is device/subset-dependent — effective N is a fraction of the cohort; confirm track availability before powering.
- **Postoperative creatinine (for AKI)** is device/subset-dependent — effective N is a fraction of the cohort; confirm track availability before powering.
- Binary outcome: target ≥10 events per predictor (EPV). Rare in-hospital events (e.g. mortality) sharply cap the number of adjustable covariates.
- Continuous / length-of-stay outcome: plan for skew (log / quantile / robust methods); required N for a given effect is far smaller than for rare binary events.

## How to compute it
1. Estimate the outcome base rate from `extracted_cohort.csv`.
2. Choose a minimal clinically important effect size.
3. Run the calculation (logistic: `statsmodels`; means: G*Power).
