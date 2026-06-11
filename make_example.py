"""make_example.py — generate a sample scoping pack + manifest for the static demo.

Produces examples/ (analysis plan, extraction script, data dictionary, figures,
power estimate, GitHub scaffold, zip) and examples/manifest.json, which the
frontend bakes in so the demo (e.g. on GitHub Pages, with no backend) can show a
real example of what the scoping pack looks like.
"""

from __future__ import annotations

import json
from pathlib import Path

import lookup
import scoping

ROOT = Path(__file__).parent
INV = lookup.load_inventory()
IDX = lookup._build_index(INV)


def ent(cid: str) -> dict:
    e = IDX[cid]
    return {"id": e.id, "name": e.name, "category": e.category,
            "confidence": e.confidence_level.value, "track": e.vitaldb_track,
            "units": e.units, "missingness": e.missingness, "common_mistakes": e.common_mistakes}


QUESTION = "Is intraoperative hypotension associated with postoperative acute kidney injury?"
CONCEPTS = [
    {"label": "intraoperative hypotension", "role": "exposure", "status": "CONFIRMED", "entry": ent("mean_arterial_pressure")},
    {"label": "postoperative AKI", "role": "outcome", "status": "CONFIRMED", "entry": ent("postoperative_creatinine")},
    {"label": "age", "role": "covariate", "status": "CONFIRMED", "entry": ent("age")},
    {"label": "ASA physical status", "role": "covariate", "status": "CONFIRMED", "entry": ent("asa_class")},
]
PARAMS = {
    "age_min": "18", "age_max": "90", "asa": ["ASA 2", "ASA 3"], "surgery_type": "",
    "anesthesia_type": "General", "emergency": "any",
    "exposure_def": "intraoperative hypotension = cumulative minutes with MAP < 65 mmHg",
    "outcome_def": "AKI = KDIGO stage ≥1 from pre-op vs peak post-op creatinine within 7 days",
    "time_window": "induction → end of surgery", "primary_analysis": "multivariable logistic regression",
    "covariates": ["age", "ASA physical status"], "sample_note": "",
}


def main() -> int:
    ex = ROOT / "examples"
    summary = scoping.build_pack(
        ex, QUESTION, CONCEPTS, PARAMS, None, 20260610,
        include=["plan", "extraction", "dictionary", "figures", "power", "github"],
        repo_url=None,
    )
    manifest = {
        "question": QUESTION,
        "ai_enriched": False,
        "demo": True,
        "design": summary["design"],
        "primary_analysis": summary["primary_analysis"],
        "models": summary.get("models") or [
            "Multivariable logistic regression (binary AKI outcome)",
            "Sensitivity analysis restricted to the arterial-line subset",
        ],
        "covariates": summary.get("covariates") or ["age", "ASA physical status"],
        "limitations": summary.get("limitations") or [],
        "plots": [{"title": p["title"], "rationale": p["rationale"], "url": "examples/" + p["file"]}
                  for p in summary["plots"]],
        "files": summary.get("files") or [],
        "has_github": True,
        "github_repo_url": None,
        "download_url": "examples/scoping_pack.zip",
        "filebase": "examples/",
    }
    (ex / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote examples/ ({len(manifest['plots'])} plots, {len(manifest['files'])} files) + manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
