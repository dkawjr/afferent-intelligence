"""scoping.py — generate a downloadable *scoping pack* for a feasible study.

This is the paid step. After a question is judged FEASIBLE and the researcher
specifies scoping parameters (cohort filters, exposure/outcome operationalization,
covariates), this module assembles a pack that does the grounded grunt-work:

  * analysis_plan.md   — a statistical analysis plan (design, cohort, models,
                         covariates, missing-data handling, power notes,
                         limitations grounded in the inventory's missingness).
  * data_dictionary.csv — every variable, its real VitalDB track/column, units,
                         confidence, and the documented missingness caveat.
  * extract_vitaldb.py — a ready-to-run extraction script (real track names,
                         cohort filters) that pulls a tidy per-case CSV from the
                         open VitalDB API.
  * make_plots.py      — plotting code for the suggested figures, reading the
                         extracted CSV.
  * plots/*.png        — ILLUSTRATIVE (synthetic) renderings so you preview the
                         intended figures before running the extraction.
  * README.md          — what's inside, how to run, and the disclaimer.

IT DOES NOT WRITE THE PAPER. It scopes the analysis and hands you the data
plumbing and figure templates. Everything that asserts what VitalDB contains is
grounded in the verified inventory — the model only adds the analysis prose and
figure rationale, clearly labelled as such.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

DISCLAIMER = (
    "This scoping pack does NOT write your paper. It produces an analysis plan, a "
    "data-extraction script, a data dictionary, and illustrative figure templates. "
    "The plots here are SYNTHETIC (structure only) — run extract_vitaldb.py then "
    "make_plots.py to produce figures from real VitalDB data. Statistical and figure "
    "suggestions are AI-generated and must be reviewed by a qualified statistician; "
    "variable availability is grounded in the verified VitalDB inventory."
)


# ---------------------------------------------------------------------------
# Classify concepts and map each to its real VitalDB data source.
# ---------------------------------------------------------------------------
def _source_of(entry: dict) -> tuple[str, str]:
    """Return (kind, key): clinical | lab | track | derived | unknown."""
    if not entry:
        return ("unknown", "")
    track = (entry.get("track") or "").strip()
    low = track.lower()
    if "name='" in track:  # e.g. lab_data name='cr'
        name = track.split("name='", 1)[1].split("'", 1)[0]
        return ("lab", name)
    if track.startswith("clinical_info"):
        col = track.split(".", 1)[1].split(",")[0].split(" ")[0].strip() if "." in track else ""
        return ("clinical", col)
    if "derived from" in low:
        return ("derived", track)
    if low.startswith("lab_data") or entry.get("category") == "laboratory":
        return ("lab", entry.get("id", ""))
    if track:
        return ("track", track.split()[0])  # e.g. Solar8000/ART_MBP
    return ("unknown", "")


def classify(concepts: list[dict]) -> dict:
    """Split resolved concepts into exposures / outcomes / covariates with sources."""
    exposures, outcomes, covariates = [], [], []
    for c in concepts:
        entry = c.get("entry") or {}
        if not entry or c.get("status") != "CONFIRMED":
            continue
        kind, key = _source_of(entry)
        item = {
            "label": c.get("label") or entry.get("name"),
            "role": c.get("role", ""),
            "entry": entry,
            "source": kind,
            "key": key,
        }
        is_outcome = c.get("role") == "outcome" or entry.get("category") == "outcome"
        if is_outcome:
            outcomes.append(item)
        elif c.get("role") == "covariate":
            covariates.append(item)
        else:
            exposures.append(item)
    return {"exposures": exposures, "outcomes": outcomes, "covariates": covariates}


def _binary_outcome(item: dict) -> bool:
    eid = (item.get("entry") or {}).get("id", "")
    name = (item.get("entry") or {}).get("name", "").lower()
    return (
        eid in {"in_hospital_mortality", "postoperative_creatinine", "readmission"}
        or "mortality" in name or "aki" in name or "delirium" in name
        or "kidney" in name or "death" in name
    )


# ---------------------------------------------------------------------------
# Synthetic, clearly-labelled illustrative figures.
# ---------------------------------------------------------------------------
_ILLUS = "ILLUSTRATIVE · synthetic structure — run make_plots.py on extracted data"


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)


def _watermark(fig):
    fig.text(0.5, 0.5, "ILLUSTRATIVE", fontsize=44, color="#0f766e", alpha=0.07,
             ha="center", va="center", rotation=18, zorder=0)
    fig.text(0.01, 0.01, _ILLUS, fontsize=7, color="#94a3b8")


def _render(kind: str, exp_label: str, out_label: str, rng, path: Path):
    fig, ax = plt.subplots(figsize=(6.2, 3.9), dpi=120)
    teal = "#0f766e"
    if kind == "event_rate_by_exposure":
        x = np.arange(10)
        rate = 1 / (1 + np.exp(-(x - 5) * 0.6)) * 0.4 + rng.normal(0, 0.01, 10)
        ax.bar(x, np.clip(rate, 0, 1), color=teal, width=0.8)
        ax.set_xlabel(f"{exp_label} (deciles, low → high)")
        ax.set_ylabel(f"{out_label} rate")
        ax.set_title(f"{out_label} rate across {exp_label}")
    elif kind == "scatter_trend":
        xv = rng.normal(70, 12, 300)
        yv = 2 + np.clip((85 - xv), 0, None) * 0.18 + rng.normal(0, 1.2, 300)
        ax.scatter(xv, yv, s=10, color=teal, alpha=0.35, edgecolors="none")
        b = np.polyfit(xv, yv, 1)
        xs = np.linspace(xv.min(), xv.max(), 50)
        ax.plot(xs, np.polyval(b, xs), color="#b45309", linewidth=2)
        ax.set_xlabel(exp_label)
        ax.set_ylabel(out_label)
        ax.set_title(f"{out_label} vs {exp_label} (trend overlaid)")
    elif kind == "box_by_subgroup":
        data = [rng.normal(m, 9, 120) for m in (78, 72, 66)]
        bp = ax.boxplot(data, patch_artist=True, labels=["ASA I", "ASA II", "ASA III"])
        for b in bp["boxes"]:
            b.set(facecolor="#ccfbf1", edgecolor=teal)
        for w in bp["medians"]:
            w.set(color=teal)
        ax.set_ylabel(exp_label)
        ax.set_title(f"{exp_label} by ASA physical status")
    elif kind == "grouped_bar":
        groups = ["ASA I", "ASA II", "ASA III"]
        vals = np.clip(np.array([0.04, 0.09, 0.18]) + rng.normal(0, 0.01, 3), 0, 1)
        ax.bar(groups, vals, color=teal, width=0.6)
        ax.set_ylabel(f"{out_label} rate")
        ax.set_title(f"{out_label} rate by ASA physical status")
    else:  # histogram
        xv = rng.normal(70, 13, 600)
        ax.hist(xv, bins=24, color=teal, alpha=0.85)
        ax.set_xlabel(exp_label)
        ax.set_ylabel("cases")
        ax.set_title(f"Distribution of {exp_label}")
    _style(ax)
    _watermark(fig)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def _plot_specs(cls: dict, ai_plots: Optional[list[dict]]) -> list[dict]:
    exp = cls["exposures"][0]["label"] if cls["exposures"] else "exposure"
    out = cls["outcomes"][0]["label"] if cls["outcomes"] else "outcome"
    if ai_plots:
        specs = []
        for p in ai_plots[:3]:
            specs.append({"title": p.get("title", "Figure"), "kind": p.get("kind", "histogram"),
                          "rationale": p.get("rationale", "")})
        return specs
    binary = _binary_outcome(cls["outcomes"][0]) if cls["outcomes"] else False
    second = "event_rate_by_exposure" if binary else "scatter_trend"
    return [
        {"title": f"Distribution of {exp}", "kind": "histogram",
         "rationale": "Inspect the exposure distribution and pick clinically sensible cut-points."},
        {"title": f"{out} across {exp}", "kind": second,
         "rationale": "Show the exposure–outcome relationship before modelling."},
        {"title": f"{exp} by ASA", "kind": "box_by_subgroup",
         "rationale": "Check confounding by baseline risk (ASA) across the cohort."},
    ]


# ---------------------------------------------------------------------------
# File generators.
# ---------------------------------------------------------------------------
def _cohort_lines(params: dict) -> list[str]:
    out = []
    amin, amax = params.get("age_min"), params.get("age_max")
    if amin or amax:
        out.append(f"- Age: {amin or 'any'}–{amax or 'any'} years")
    if params.get("asa"):
        out.append(f"- ASA physical status: {', '.join(params['asa'])}")
    if params.get("surgery_type"):
        out.append(f"- Surgery type / department contains: \"{params['surgery_type']}\"")
    if params.get("anesthesia_type") and params["anesthesia_type"] != "any":
        out.append(f"- Anesthesia type: {params['anesthesia_type']}")
    if params.get("emergency") and params["emergency"] != "any":
        out.append(f"- Emergency surgery: {params['emergency']}")
    if not out:
        out.append("- No cohort restrictions specified (all eligible cases).")
    return out


def _analysis_plan_md(question, cls, params, ai) -> str:
    exp = ", ".join(e["label"] for e in cls["exposures"]) or "—"
    out = ", ".join(o["label"] for o in cls["outcomes"]) or "—"
    cov = params.get("covariates") or [c["label"] for c in cls["covariates"]]
    L = []
    L.append("# Scoping pack — analysis plan\n")
    L.append(f"**Question:** {question}\n")
    L.append(f"> {DISCLAIMER}\n")
    L.append("## Design")
    L.append((ai.get("design") if ai else "") or
             "Retrospective single-center observational cohort study using VitalDB "
             "(Seoul National University Hospital). Exposure and outcome are both ascertained "
             "within the index hospitalization (intraoperative window plus the ±90-day lab series).")
    L.append("\n## Cohort (inclusion / exclusion)")
    L += _cohort_lines(params)
    L.append("\n## Variables")
    L.append(f"- **Exposure(s):** {exp}")
    if params.get("exposure_def"):
        L.append(f"  - Operationalization: {params['exposure_def']}")
    if params.get("exposure_threshold"):
        L.append(f"  - Threshold: {params['exposure_threshold']}")
    L.append(f"- **Outcome(s):** {out}")
    if params.get("outcome_def"):
        L.append(f"  - Operationalization: {params['outcome_def']}")
    L.append(f"- **Covariates:** {', '.join(cov) if cov else 'none specified'}")
    if params.get("time_window"):
        L.append(f"- **Time window:** {params['time_window']}")
    L.append("\n## Primary analysis")
    L.append((ai.get("primary_analysis") if ai else "") or
             "Estimate the association between the exposure and the outcome, adjusting for the "
             "covariates above. Choose the model family by outcome type (logistic regression for "
             "binary in-hospital outcomes; linear or quantile regression / time-to-event for "
             "length-of-stay and continuous outcomes).")
    if ai and ai.get("statistical_models"):
        L.append("\n## Candidate statistical models")
        L += [f"- {m}" for m in ai["statistical_models"]]
    L.append("\n## Missing data")
    L.append((ai.get("missing_data") if ai else "") or
             "Lab and device-dependent tracks are recorded only when ordered/used, so missingness "
             "is informative (sicker patients are sampled more). Report per-variable completeness, "
             "pre-specify a missing-data approach (complete-case vs multiple imputation), and run a "
             "sensitivity analysis on the device-monitored subset.")
    L.append("\n## Power & feasibility")
    L.append((ai.get("power_considerations") if ai else "") or
             "VitalDB has ~6,388 cases, but device-subset tracks (BIS, arterial line, advanced "
             "hemodynamics) and rare events (in-hospital mortality) sharply limit effective sample "
             "size. Estimate the analyzable N on the relevant track subset before committing.")
    L.append("\n## Limitations (grounded in the inventory)")
    grounded = []
    for it in cls["exposures"] + cls["outcomes"]:
        e = it["entry"]
        if e.get("missingness"):
            grounded.append(f"- **{e.get('name')}:** {e['missingness']}")
    L += grounded or ["- Single-center, retrospective; residual confounding likely."]
    if ai and ai.get("limitations"):
        L += [f"- {x}" for x in ai["limitations"]]
    if ai and ai.get("extra_recommendations"):
        L.append("\n## Other recommendations")
        L += [f"- {x}" for x in ai["extra_recommendations"]]
    L.append("\n## What this pack is NOT")
    L.append("- It does not write the manuscript, interpret results, or make causal claims.")
    L.append("- The bundled figures are synthetic illustrations of structure, not results.")
    return "\n".join(L) + "\n"


def _data_dictionary_rows(cls: dict) -> list[dict]:
    rows = []
    for role, items in (("exposure", cls["exposures"]), ("outcome", cls["outcomes"]),
                        ("covariate", cls["covariates"])):
        for it in items:
            e = it["entry"]
            rows.append({
                "concept": it["label"],
                "role": it.get("role") or role,
                "inventory_id": e.get("id", ""),
                "vitaldb_source": e.get("track", ""),
                "source_kind": it["source"],
                "extract_key": it["key"],
                "units": e.get("units") or "",
                "confidence": e.get("confidence", ""),
                "missingness": e.get("missingness", ""),
                "common_mistake": e.get("common_mistakes", ""),
            })
    return rows


def _extract_script(cls, params) -> str:
    clinical_cols, lab_names, tracks = [], [], []
    for it in cls["exposures"] + cls["outcomes"] + cls["covariates"]:
        if it["source"] == "clinical" and it["key"]:
            clinical_cols.append(it["key"])
        elif it["source"] == "lab" and it["key"]:
            lab_names.append(it["key"])
        elif it["source"] == "track" and it["key"]:
            tracks.append(it["key"])
    # always keep core clinical columns for filtering/merge
    base_cols = ["caseid", "age", "sex", "asa", "optype", "department", "emop", "ane_type", "death_inhosp", "icu_days"]
    clinical_cols = sorted(set(base_cols + clinical_cols))
    lab_names = sorted(set(lab_names))
    tracks = sorted(set(tracks))

    filters = []
    if params.get("age_min"):
        filters.append(f"clin = clin[clin['age'] >= {int(params['age_min'])}]")
    if params.get("age_max"):
        filters.append(f"clin = clin[clin['age'] <= {int(params['age_max'])}]")
    if params.get("asa"):
        nums = [s.split()[-1] if " " in s else s for s in params["asa"]]
        nums = [n for n in nums if n.isdigit()]
        if nums:
            filters.append(f"clin = clin[clin['asa'].isin({[int(n) for n in nums]})]")
    if params.get("anesthesia_type") and params["anesthesia_type"] != "any":
        filters.append(f"clin = clin[clin['ane_type'].astype(str).str.contains({params['anesthesia_type']!r}, case=False, na=False)]")
    if params.get("emergency") == "yes":
        filters.append("clin = clin[clin['emop'] == 1]")
    elif params.get("emergency") == "no":
        filters.append("clin = clin[clin['emop'] == 0]")
    if params.get("surgery_type"):
        filters.append(f"clin = clin[clin['optype'].astype(str).str.contains({params['surgery_type']!r}, case=False, na=False)]")
    filt_block = "\n".join(filters) if filters else "# (no cohort filters specified)"

    return f'''"""extract_vitaldb.py — auto-generated by Afferent Intelligence.

Pulls a tidy per-case CSV for this study from the OPEN VitalDB dataset.
Review and adjust before running. Requires:  pip install vitaldb pandas numpy

The open VitalDB subset is downloadable without credentialing via the public API.
Track names below come from the verified inventory.
"""
import numpy as np, pandas as pd

CASE_LIMIT = 100   # raise to None for the full cohort once you have verified the script

CLINICAL_COLS = {clinical_cols!r}
LAB_NAMES     = {lab_names!r}
TRACKS        = {tracks!r}

# --- 1. clinical information (one row per case) -----------------------------
clin = pd.read_csv("https://api.vitaldb.net/cases")
clin = clin[[c for c in CLINICAL_COLS if c in clin.columns]].copy()

# --- 2. cohort filters (from your scoping parameters) -----------------------
{filt_block}
clin["los_days"] = None  # derive from adm/dis if needed: (clin['dis']-clin['adm'])/86400

caseids = clin["caseid"].tolist()
if CASE_LIMIT:
    caseids = caseids[:CASE_LIMIT]
clin = clin[clin["caseid"].isin(caseids)]

# --- 3. perioperative labs (long -> wide summary; e.g. baseline & peak) ------
if LAB_NAMES:
    labs = pd.read_csv("https://api.vitaldb.net/labs")
    labs = labs[labs["name"].isin(LAB_NAMES) & labs["caseid"].isin(caseids)]
    # baseline (closest pre-op) and postoperative peak per case/test:
    labs_pre  = labs[labs["dt"] <= 0].sort_values("dt").groupby(["caseid", "name"]).last()["result"].unstack()
    labs_post = labs[labs["dt"] >  0].groupby(["caseid", "name"])["result"].max().unstack()
    labs_pre.columns  = [f"{{c}}_baseline" for c in labs_pre.columns]
    labs_post.columns = [f"{{c}}_postop_peak" for c in labs_post.columns]
    clin = clin.merge(labs_pre, on="caseid", how="left").merge(labs_post, on="caseid", how="left")

# --- 4. intraoperative tracks (summarise each waveform/numeric per case) -----
if TRACKS:
    import vitaldb
    rows = []
    for cid in caseids:
        feat = {{"caseid": cid}}
        try:
            vf = vitaldb.VitalFile(cid, TRACKS)
            df = vf.to_pandas(TRACKS, 1)        # 1-second resolution over the case
            for t in TRACKS:
                if t in df:
                    s = pd.to_numeric(df[t], errors="coerce")
                    feat[f"{{t}}_mean"] = np.nanmean(s)
                    feat[f"{{t}}_min"]  = np.nanmin(s)
                    feat[f"{{t}}_max"]  = np.nanmax(s)
        except Exception as e:
            print("skip", cid, e)
        rows.append(feat)
    clin = clin.merge(pd.DataFrame(rows), on="caseid", how="left")

# TODO: operationalize the exposure/outcome from your scoping parameters here,
#       e.g. hypotension_minutes = time with Solar8000/ART_MBP_mean < 65.

clin.to_csv("extracted_cohort.csv", index=False)
print("wrote extracted_cohort.csv:", clin.shape)
'''


def _make_plots_script(specs, cls) -> str:
    exp = cls["exposures"][0]["label"] if cls["exposures"] else "exposure"
    out = cls["outcomes"][0]["label"] if cls["outcomes"] else "outcome"
    return f'''"""make_plots.py — auto-generated. Produces the suggested figures from
extracted_cohort.csv (run extract_vitaldb.py first). Edit the column names to
match your extracted features. Requires: pip install pandas matplotlib
"""
import pandas as pd, matplotlib.pyplot as plt

df = pd.read_csv("extracted_cohort.csv")

# Map these to your actual extracted columns:
EXPOSURE_COL = "EXPOSURE_COLUMN"   # e.g. "Solar8000/ART_MBP_min" for {exp}
OUTCOME_COL  = "OUTCOME_COLUMN"    # e.g. "death_inhosp" for {out}
SUBGROUP_COL = "asa"

# 1. distribution of exposure
ax = df[EXPOSURE_COL].plot(kind="hist", bins=24, color="#0f766e", alpha=.85)
ax.set_title("Distribution of {exp}"); plt.tight_layout(); plt.savefig("fig1_distribution.png"); plt.close()

# 2. outcome across exposure (binary -> event rate by decile; continuous -> scatter)
d = df.dropna(subset=[EXPOSURE_COL, OUTCOME_COL]).copy()
if d[OUTCOME_COL].dropna().isin([0, 1]).all():
    d["bin"] = pd.qcut(d[EXPOSURE_COL], 10, labels=False, duplicates="drop")
    d.groupby("bin")[OUTCOME_COL].mean().plot(kind="bar", color="#0f766e")
    plt.ylabel("{out} rate")
else:
    plt.scatter(d[EXPOSURE_COL], d[OUTCOME_COL], s=10, alpha=.35, color="#0f766e")
    plt.ylabel("{out}")
plt.title("{out} across {exp}"); plt.tight_layout(); plt.savefig("fig2_association.png"); plt.close()

# 3. exposure by subgroup
if SUBGROUP_COL in df:
    df.boxplot(column=EXPOSURE_COL, by=SUBGROUP_COL)
    plt.title("{exp} by " + SUBGROUP_COL); plt.suptitle(""); plt.tight_layout()
    plt.savefig("fig3_subgroup.png"); plt.close()
print("wrote figures")
'''


def _readme(question, files) -> str:
    lines = ["# Afferent Intelligence — scoping pack\n", f"**Question:** {question}\n",
             f"> {DISCLAIMER}\n", "## Contents"]
    lines += [f"- `{f}`" for f in files]
    lines += ["\n## How to use",
              "1. Read `analysis_plan.md`.",
              "2. `pip install vitaldb pandas numpy matplotlib`",
              "3. Run `python extract_vitaldb.py` (pulls the open VitalDB subset → `extracted_cohort.csv`).",
              "4. Edit the column names at the top of `make_plots.py`, then run it.",
              "5. The `plots/` PNGs are synthetic previews of structure — your real figures come from step 4.\n"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
def _power_md(question, cls, params, ai) -> str:
    out = ["# Power & sample-size scoping\n", f"**Question:** {question}\n",
           "> Rough scoping guidance — not a substitute for a formal power analysis. "
           "Plug your event rate and effect size into G*Power or `statsmodels` once you have them.\n",
           "## Starting points",
           "- VitalDB has ~6,388 cases total; your analyzable N is the intersection of your cohort "
           "filters and the cases that actually have the required tracks."]
    for it in cls["exposures"] + cls["outcomes"]:
        m = (it["entry"].get("missingness") or "").lower()
        if any(k in m for k in ("subset", "device", "only when", "arterial line", "bis module", "advanced")):
            out.append(f"- **{it['entry'].get('name')}** is device/subset-dependent — effective N is a "
                       "fraction of the cohort; confirm track availability before powering.")
    out.append("- Binary outcome: target ≥10 events per predictor (EPV). Rare in-hospital events "
               "(e.g. mortality) sharply cap the number of adjustable covariates.")
    out.append("- Continuous / length-of-stay outcome: plan for skew (log / quantile / robust methods); "
               "required N for a given effect is far smaller than for rare binary events.")
    if ai and ai.get("power_considerations"):
        out += ["\n## Model-specific notes", ai["power_considerations"]]
    out += ["\n## How to compute it",
            "1. Estimate the outcome base rate from `extracted_cohort.csv`.",
            "2. Choose a minimal clinically important effect size.",
            "3. Run the calculation (logistic: `statsmodels`; means: G*Power)."]
    return "\n".join(out) + "\n"


def _github_files(run_dir: Path, question: str, repo_url: Optional[str]) -> list[str]:
    (run_dir / ".gitignore").write_text(
        "extracted_cohort.csv\ndata/\n__pycache__/\n.venv/\n*.pyc\n.DS_Store\n", encoding="utf-8")
    (run_dir / "requirements.txt").write_text(
        "vitaldb\npandas\nnumpy\nmatplotlib\nstatsmodels\n", encoding="utf-8")
    remote = (f"\nA private repo has already been created for you:\n\n    {repo_url}\n\n"
              "Push this pack to it:\n\n"
              "    git init && git add . && git commit -m \"Afferent scoping pack\"\n"
              f"    git remote add origin {repo_url}.git\n"
              "    git branch -M main && git push -u origin main\n") if repo_url else (
              "Create a private repo and push (GitHub CLI):\n\n"
              "    git init && git add . && git commit -m \"Afferent scoping pack\"\n"
              "    gh repo create afferent-study --private --source=. --push\n\n"
              "…or create an empty private repo on github.com, then add it as `origin` and push.\n")
    (run_dir / "GITHUB_SETUP.md").write_text(
        f"# Private GitHub repo — {question}\n\nThis scoping pack is laid out as a clone-ready repository "
        "(code, analysis plan, data dictionary, figure templates). It does **not** contain patient data — "
        "`extract_vitaldb.py` pulls the open VitalDB subset on your machine.\n\n## Push it\n" + remote +
        "\n## Run it\n    pip install -r requirements.txt\n    python extract_vitaldb.py\n    python make_plots.py\n",
        encoding="utf-8")
    return [".gitignore", "requirements.txt", "GITHUB_SETUP.md"]


def build_pack(run_dir: Path, question: str, concepts: list[dict],
               params: dict, ai: Optional[dict], seed: int,
               include: Optional[list[str]] = None,
               repo_url: Optional[str] = None) -> dict:
    include = set(include or ["plan", "extraction", "dictionary", "figures", "power"])
    run_dir.mkdir(parents=True, exist_ok=True)
    cls = classify(concepts)
    rng = np.random.default_rng(seed)
    files: list[str] = []

    if "plan" in include:
        (run_dir / "analysis_plan.md").write_text(_analysis_plan_md(question, cls, params, ai or {}), encoding="utf-8")
        files.append("analysis_plan.md")

    if "dictionary" in include:
        dd_rows = _data_dictionary_rows(cls)
        with (run_dir / "data_dictionary.csv").open("w", newline="", encoding="utf-8") as fh:
            if dd_rows:
                w = csv.DictWriter(fh, fieldnames=list(dd_rows[0].keys()))
                w.writeheader()
                w.writerows(dd_rows)
        files.append("data_dictionary.csv")

    if "extraction" in include:
        (run_dir / "extract_vitaldb.py").write_text(_extract_script(cls, params), encoding="utf-8")
        files.append("extract_vitaldb.py")

    if "power" in include:
        (run_dir / "power_estimate.md").write_text(_power_md(question, cls, params, ai or {}), encoding="utf-8")
        files.append("power_estimate.md")

    plot_meta = []
    if "figures" in include:
        (run_dir / "plots").mkdir(exist_ok=True)
        specs = _plot_specs(cls, (ai or {}).get("plots"))
        exp_label = cls["exposures"][0]["label"] if cls["exposures"] else "exposure"
        out_label = cls["outcomes"][0]["label"] if cls["outcomes"] else "outcome"
        for i, spec in enumerate(specs, 1):
            fname = f"plots/fig{i}_{spec['kind']}.png"
            _render(spec["kind"], exp_label, out_label, rng, run_dir / fname)
            plot_meta.append({"title": spec["title"], "rationale": spec.get("rationale", ""), "file": fname})
        (run_dir / "make_plots.py").write_text(_make_plots_script(specs, cls), encoding="utf-8")
        files += ["make_plots.py"] + [p["file"] for p in plot_meta]

    if "github" in include:
        files += _github_files(run_dir, question, repo_url)

    (run_dir / "README.md").write_text(_readme(question, files), encoding="utf-8")

    # zip only what was purchased
    zip_path = run_dir / "scoping_pack.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ["README.md"] + files:
            z.write(run_dir / f, f)

    return {
        "design": (ai or {}).get("design") or "Retrospective single-center observational cohort (VitalDB).",
        "primary_analysis": (ai or {}).get("primary_analysis")
        or "Adjusted association between exposure and outcome; model family chosen by outcome type.",
        "models": (ai or {}).get("statistical_models") or [],
        "covariates": params.get("covariates") or [c["label"] for c in cls["covariates"]],
        "limitations": [f"{it['entry'].get('name')}: {it['entry'].get('missingness')}"
                        for it in cls["exposures"] + cls["outcomes"] if it["entry"].get("missingness")][:4],
        "plots": plot_meta,
        "files": [{"name": f, "ai": False} for f in files],
        "n_exposures": len(cls["exposures"]),
        "n_outcomes": len(cls["outcomes"]),
    }
