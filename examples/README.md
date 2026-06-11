# Afferent Intelligence — scoping pack

**Question:** Is intraoperative hypotension associated with postoperative acute kidney injury?

> This scoping pack does NOT write your paper. It produces an analysis plan, a data-extraction script, a data dictionary, and illustrative figure templates. The plots here are SYNTHETIC (structure only) — run extract_vitaldb.py then make_plots.py to produce figures from real VitalDB data. Statistical and figure suggestions are AI-generated and must be reviewed by a qualified statistician; variable availability is grounded in the verified VitalDB inventory.

## Contents
- `analysis_plan.md`
- `data_dictionary.csv`
- `extract_vitaldb.py`
- `power_estimate.md`
- `make_plots.py`
- `plots/fig1_histogram.png`
- `plots/fig2_event_rate_by_exposure.png`
- `plots/fig3_box_by_subgroup.png`
- `.gitignore`
- `requirements.txt`
- `GITHUB_SETUP.md`

## How to use
1. Read `analysis_plan.md`.
2. `pip install vitaldb pandas numpy matplotlib`
3. Run `python extract_vitaldb.py` (pulls the open VitalDB subset → `extracted_cohort.csv`).
4. Edit the column names at the top of `make_plots.py`, then run it.
5. The `plots/` PNGs are synthetic previews of structure — your real figures come from step 4.

