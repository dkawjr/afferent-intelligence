# Scoping pack — analysis plan

**Question:** Is intraoperative hypotension associated with postoperative acute kidney injury?

> This scoping pack does NOT write your paper. It produces an analysis plan, a data-extraction script, a data dictionary, and illustrative figure templates. The plots here are SYNTHETIC (structure only) — run extract_vitaldb.py then make_plots.py to produce figures from real VitalDB data. Statistical and figure suggestions are AI-generated and must be reviewed by a qualified statistician; variable availability is grounded in the verified VitalDB inventory.

## Design
Retrospective single-center observational cohort study using VitalDB (Seoul National University Hospital). Exposure and outcome are both ascertained within the index hospitalization (intraoperative window plus the ±90-day lab series).

## Cohort (inclusion / exclusion)
- Age: 18–90 years
- ASA physical status: ASA 2, ASA 3
- Anesthesia type: General

## Variables
- **Exposure(s):** intraoperative hypotension
  - Operationalization: intraoperative hypotension = cumulative minutes with MAP < 65 mmHg
- **Outcome(s):** postoperative AKI
  - Operationalization: AKI = KDIGO stage ≥1 from pre-op vs peak post-op creatinine within 7 days
- **Covariates:** age, ASA physical status
- **Time window:** induction → end of surgery

## Primary analysis
Estimate the association between the exposure and the outcome, adjusting for the covariates above. Choose the model family by outcome type (logistic regression for binary in-hospital outcomes; linear or quantile regression / time-to-event for length-of-stay and continuous outcomes).

## Missing data
Lab and device-dependent tracks are recorded only when ordered/used, so missingness is informative (sicker patients are sampled more). Report per-variable completeness, pre-specify a missing-data approach (complete-case vs multiple imputation), and run a sensitivity analysis on the device-monitored subset.

## Power & feasibility
VitalDB has ~6,388 cases, but device-subset tracks (BIS, arterial line, advanced hemodynamics) and rare events (in-hospital mortality) sharply limit effective sample size. Estimate the analyzable N on the relevant track subset before committing.

## Limitations (grounded in the inventory)
- **Mean Arterial Pressure (MAP):** Invasive MBP needs an arterial line (~1-2 s); non-invasive MBP is intermittent (every few min). Choose the source matching your hypotension definition.
- **Postoperative creatinine (for AKI):** Present within the +/-90-day lab window BUT only when creatinine was ordered postoperatively. Many cases lack postop draws, so an AKI cohort is a SELECTED subset, not all 6,388.

## What this pack is NOT
- It does not write the manuscript, interpret results, or make causal claims.
- The bundled figures are synthetic illustrations of structure, not results.
