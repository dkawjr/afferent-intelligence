"""app.py — Afferent Intelligence backend.

Serves the frontend and a /api/feasibility endpoint that runs the real
three-step pipeline:

  (1) DECOMPOSE  — Claude turns the plain-English question into PECO and proposes,
      for each required clinical concept, the single best-matching inventory
      concept_id (or null). This is the INFERENCE step.
  (2) RESOLVE    — every proposed concept_id is re-resolved through lookup.py
      against the verified inventory. Status (CONFIRMED / CONFIRMED_ABSENT /
      NOT_IN_INVENTORY) comes ONLY from the inventory — never from the model.
      This is the FACTS step, and it is where the no-guessing rule is enforced.
  (3) VERDICT    — derived deterministically from the resolved statuses.

The model is given the verified inventory so it can MAP concepts and craft a
grounded reframe, but it cannot fabricate availability: a concept_id it returns
is only ever as available as the inventory says it is, and an unmatched concept
resolves to NOT_IN_INVENTORY.

Run:
    pip install -r requirements.txt
    set ANTHROPIC_API_KEY=...        (PowerShell: $env:ANTHROPIC_API_KEY="...")
    py -m uvicorn app:app --reload   (or: py app.py)

If ANTHROPIC_API_KEY is not set, /api/feasibility reports ai_enabled=false and
the frontend falls back to its built-in keyword matcher, so the page still works.
"""

from __future__ import annotations

import os
import zlib
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import lookup
import scoping
from models import FeasibilityVerdict, ResolutionStatus

ROOT = Path(__file__).parent
INDEX_HTML = ROOT / "index.html"
SCOPE_DIR = ROOT / "scoping_runs"
MODEL = os.environ.get("AFFERENT_MODEL", "claude-opus-4-8")
SOURCE_URL = "https://www.nature.com/articles/s41597-022-01411-5"

# À la carte pricing for scoping deliverables (standard demo amounts, USD).
PRICING = {
    "plan":       {"label": "Statistical analysis plan",            "price": 15},
    "extraction": {"label": "VitalDB data-extraction script",       "price": 10},
    "dictionary": {"label": "Data dictionary & variable manifest",  "price": 5},
    "figures":    {"label": "Suggested figures (templates + code)", "price": 12},
    "power":      {"label": "Power / sample-size estimate",          "price": 12},
    "github":     {"label": "Private GitHub repo (clone-ready)",     "price": 8},
}
BUNDLE = {"label": "Full scoping pack (everything)", "price": 49}
NOVELTY_PRICE = 9


def _create_github_repo(name: str) -> Optional[str]:
    """If a GITHUB_TOKEN is configured, create an empty private repo and return its URL."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    import json as _json
    import urllib.request

    try:
        req = urllib.request.Request(
            "https://api.github.com/user/repos",
            data=_json.dumps({"name": name, "private": True,
                              "description": "Afferent Intelligence scoping pack"}).encode(),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                     "User-Agent": "afferent-intelligence"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            return _json.loads(r.read()).get("html_url")
    except Exception:  # noqa: BLE001
        return None

# ---------------------------------------------------------------------------
# Load the verified inventory once at startup (stable -> cacheable in the prompt).
# ---------------------------------------------------------------------------
INV = lookup.load_inventory()
INDEX = lookup._build_index(INV)

CONFIRMED_OUTCOMES = [
    {"id": e.id, "name": e.name}
    for e in INV.variables
    if e.category == "outcome" and e.status.value == "CONFIRMED"
]

# Compact, verified inventory passed to the model: id | name | STATUS | category.
INVENTORY_LINES = "\n".join(
    f"{e.id} | {e.name} | {e.status.value} | {e.category}" for e in INV.variables
)

SYSTEM_PROMPT = f"""You are the DECOMPOSE step of Afferent Intelligence, a research-feasibility \
triage engine for the VitalDB dataset. VitalDB is a single-center (Seoul National University \
Hospital) surgical dataset: intraoperative high-resolution waveforms/numerics, a per-case \
clinical-information table, in-hospital outcomes, and a perioperative lab time-series spanning \
90 days before to 90 days after surgery.

Your job is INFERENCE ONLY. You do NOT decide feasibility and you do NOT claim any variable \
exists. Availability is determined downstream by resolving your proposed concept_ids against \
the verified inventory. Your tasks:

1. Decompose the user's question into PECO: Population, Exposure, Comparator, Outcome (one short \
phrase each; use "—" if a comparator is implicit).
2. List every required clinical concept (exposures, outcomes, key covariates). For EACH concept, \
set concept_id to the single best-matching inventory id from the list below — but ONLY if it is \
genuinely the SAME clinical concept. If nothing in the inventory is truly the same concept, set \
concept_id to null (do not force a loose match — a wrong match is worse than null).
3. reframe: If — and only if — a required concept maps to an inventory entry whose STATUS is \
CONFIRMED_ABSENT, propose ONE sentence describing an alternative study that keeps the clinical \
spirit but uses only CONFIRMED inventory concepts (name them). Otherwise set reframe to null.
4. rewrites: If the question is vague, missing a clear exposure or outcome, or phrased so loosely \
that the concepts can't be pinned down, propose 1-3 well-formed reformulations that ARE answerable \
in VitalDB — each must name a concrete exposure and outcome using only CONFIRMED inventory concepts, \
and stay as close as possible to the user's apparent intent. Give a one-line 'why' for each. If the \
question is already specific and well-formed, set rewrites to null.

VERIFIED INVENTORY (id | name | STATUS | category) — this is ground truth, do not contradict it:
{INVENTORY_LINES}

Map to these ids exactly. Never invent an id. Never assert a concept is available — that is the \
inventory's job, not yours."""


# ---------------------------------------------------------------------------
# Structured output schema for the decompose step.
# ---------------------------------------------------------------------------
class ConceptCandidate(BaseModel):
    label: str = Field(..., description="The clinical concept as expressed in the question.")
    role: Literal["population", "exposure", "comparator", "outcome", "covariate"]
    concept_id: Optional[str] = Field(
        default=None, description="Best-matching inventory id, or null if no genuine match."
    )


class RewriteSuggestion(BaseModel):
    question: str = Field(..., description="A well-formed, VitalDB-answerable reformulation.")
    why: str = Field(..., description="One line on what it fixes / why it's answerable.")


class Decomposition(BaseModel):
    population: str
    exposure: str
    comparator: str
    outcome: str
    concepts: list[ConceptCandidate]
    reframe: Optional[str] = None
    rewrites: Optional[list[RewriteSuggestion]] = None


# ---------------------------------------------------------------------------
app = FastAPI(title="Afferent Intelligence")


def _ai_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _entry_payload(entry) -> Optional[dict]:
    if entry is None:
        return None
    return {
        "id": entry.id,
        "name": entry.name,
        "category": entry.category,
        "confidence": entry.confidence_level.value,
        "track": entry.vitaldb_track,
        "units": entry.units,
        "missingness": entry.missingness,
        "common_mistakes": entry.common_mistakes,
    }


def _resolve_candidate(label: str, concept_id: Optional[str]):
    """Resolve a model-proposed concept through the verified inventory (FACTS step)."""
    target = concept_id or label
    res = lookup.resolve(target, INV, INDEX)
    res.query = label or res.query  # keep the human-readable label for display
    return res


@app.get("/api/health")
def health() -> dict:
    return {
        "ai_enabled": _ai_enabled(),
        "model": MODEL if _ai_enabled() else None,
        "dataset": INV.dataset,
        "n_concepts": len(INV.variables),
        "source_url": SOURCE_URL,
        "scope": INV.scope,
        "pricing": PRICING,
        "bundle": BUNDLE,
        "novelty_price": NOVELTY_PRICE,
    }


@app.post("/api/feasibility")
def feasibility(payload: dict) -> JSONResponse:
    question = (payload or {}).get("question", "").strip()
    if not question:
        return JSONResponse({"mode": "error", "message": "Empty question."}, status_code=400)

    if not _ai_enabled():
        # No key — tell the frontend to use its built-in keyword matcher.
        return JSONResponse({"mode": "no_ai", "message": "ANTHROPIC_API_KEY not set."})

    try:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=MODEL,
            max_tokens=2000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": question}],
            output_format=Decomposition,
        )
        dec: Decomposition = resp.parsed_output
    except Exception as exc:  # noqa: BLE001 — surface as graceful fallback
        return JSONResponse(
            {"mode": "error", "message": f"{type(exc).__name__}: {exc}"}, status_code=200
        )

    # FACTS step: resolve every proposed concept through the inventory.
    resolutions = [_resolve_candidate(c.label, c.concept_id) for c in dec.concepts]
    verdict = lookup.feasibility_from_resolutions(resolutions)

    concepts_out = []
    for cand, res in zip(dec.concepts, resolutions):
        concepts_out.append(
            {
                "label": res.query,
                "role": cand.role,
                "status": res.status.value,
                "resolved_id": res.resolved_id,
                "entry": _entry_payload(res.entry),
            }
        )

    blocked = [r.query for r in resolutions if r.status == ResolutionStatus.CONFIRMED_ABSENT]
    unverified = [r.query for r in resolutions if r.status == ResolutionStatus.NOT_IN_INVENTORY]

    suggestion = None
    if verdict == FeasibilityVerdict.NOT_FEASIBLE:
        suggestion = {
            "reframe": dec.reframe,  # AI inference (grounded in confirmed concepts), clearly labeled
            "alternatives": CONFIRMED_OUTCOMES,
        }

    return JSONResponse(
        {
            "mode": "ai",
            "model": MODEL,
            "question": question,
            "peco": {
                "population": dec.population,
                "exposure": dec.exposure,
                "comparator": dec.comparator,
                "outcome": dec.outcome,
            },
            "concepts": concepts_out,
            "verdict": verdict.value,
            "blocked": blocked,
            "unverified": unverified,
            "suggestion": suggestion,
            "rewrites": [r.model_dump() for r in dec.rewrites] if dec.rewrites else None,
            "source_url": SOURCE_URL,
        }
    )


# ---------------------------------------------------------------------------
# Scoping pack (the paid step). Inference is grounded: only CONFIRMED concepts
# (re-resolved server-side from the inventory) are scoped; the model adds the
# analysis prose and figure rationale, never variable availability.
# ---------------------------------------------------------------------------
class PlotSuggestion(BaseModel):
    title: str
    kind: Literal["histogram", "event_rate_by_exposure", "scatter_trend", "box_by_subgroup", "grouped_bar"]
    rationale: str


class ScopingPlan(BaseModel):
    design: str
    primary_analysis: str
    statistical_models: list[str]
    covariates: list[str]
    missing_data: str
    power_considerations: str
    limitations: list[str]
    plots: list[PlotSuggestion]
    extra_recommendations: list[str]


def _scope_with_ai(question: str, concepts: list[dict], params: dict) -> Optional[dict]:
    if not _ai_enabled():
        return None
    try:
        import anthropic

        var_lines = "\n".join(
            f"- {c['label']} ({c['role'] or 'variable'}): {c['entry']['name']} "
            f"[{c['entry']['confidence']} confidence] — {c['entry']['missingness']}"
            for c in concepts
        )
        sys = (
            "You are the SCOPING step of Afferent Intelligence. The study below is already judged "
            "FEASIBLE in VitalDB (single-center SNUH; intraoperative + in-hospital + ±90-day labs). "
            "Produce a statistical scoping plan ONLY — you do NOT write the paper, interpret results, "
            "or make causal claims. Use only the verified variables provided; ground limitations in "
            "their stated missingness. Be specific and practical for a perioperative researcher.\n\n"
            f"VERIFIED VARIABLES:\n{var_lines}"
        )
        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=MODEL,
            max_tokens=3000,
            system=[{"type": "text", "text": sys, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Question: {question}\nScoping parameters: {params}"}],
            output_format=ScopingPlan,
        )
        return resp.parsed_output.model_dump()
    except Exception:  # noqa: BLE001 — fall back to the deterministic plan
        return None


@app.post("/api/scope")
def scope(payload: dict) -> JSONResponse:
    question = (payload or {}).get("question", "").strip()
    raw = (payload or {}).get("concepts", []) or []
    params = (payload or {}).get("params", {}) or {}

    # Re-resolve concepts against the inventory (no-guessing: only verified, CONFIRMED ones).
    concepts: list[dict] = []
    for c in raw:
        rid = c.get("resolved_id")
        entry = INDEX.get(rid) if rid else None
        if entry is None or entry.status.value != "CONFIRMED":
            continue
        concepts.append({
            "label": c.get("label") or entry.name,
            "role": c.get("role", ""),
            "status": "CONFIRMED",
            "entry": _entry_payload(entry),
        })

    if not concepts:
        return JSONResponse(
            {"error": "No confirmed variables to scope. Settle on a feasible question first."},
            status_code=400,
        )

    # Which deliverables were purchased.
    items = (payload or {}).get("items") or list(PRICING.keys())
    if "bundle" in items:
        include = list(PRICING.keys())
        order = {"items": [BUNDLE], "total": BUNDLE["price"]}
    else:
        include = [i for i in items if i in PRICING] or list(PRICING.keys())
        order = {
            "items": [{"label": PRICING[i]["label"], "price": PRICING[i]["price"]} for i in include],
            "total": sum(PRICING[i]["price"] for i in include),
        }

    ai = _scope_with_ai(question, concepts, params)
    seed = zlib.crc32(question.encode("utf-8")) & 0xFFFFFFFF
    run_id = f"{seed:08x}"
    repo_url = _create_github_repo(f"afferent-study-{run_id}") if "github" in include else None
    summary = scoping.build_pack(SCOPE_DIR / run_id, question, concepts, params, ai, seed, include, repo_url)
    summary.update({
        "run_id": run_id,
        "ai_enriched": ai is not None,
        "order": order,
        "github_repo_url": repo_url,
        "has_github": "github" in include,
        "download_url": f"/api/scope/file/{run_id}/scoping_pack.zip",
        "plots": [{**p, "url": f"/api/scope/file/{run_id}/{p['file']}"} for p in summary["plots"]],
    })
    return JSONResponse(summary)


# ---------------------------------------------------------------------------
# Novelty scan — real PubMed (NCBI E-utilities) related work + optional AI read.
# ---------------------------------------------------------------------------
def _pubmed_search(query: str, retmax: int = 8) -> list[dict]:
    import json as _json
    import urllib.parse
    import urllib.request

    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    common = "tool=afferent_intelligence&email=research@example.com"
    try:
        q = urllib.parse.quote(query)
        es = f"{base}/esearch.fcgi?db=pubmed&retmode=json&retmax={retmax}&sort=relevance&term={q}&{common}"
        with urllib.request.urlopen(es, timeout=12) as r:
            ids = _json.loads(r.read()).get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        su = f"{base}/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}&{common}"
        with urllib.request.urlopen(su, timeout=12) as r:
            res = _json.loads(r.read()).get("result", {})
        out = []
        for pid in ids:
            d = res.get(pid, {})
            if not d:
                continue
            out.append({
                "pmid": pid,
                "title": d.get("title", "").rstrip("."),
                "journal": d.get("fulljournalname") or d.get("source", ""),
                "year": (d.get("pubdate", "") or "")[:4],
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
            })
        return out
    except Exception:  # noqa: BLE001
        return []


def _novelty_query_and_read(question: str, concepts: list[dict], articles: list[dict]) -> dict:
    """Optionally use the model to assess overlap with the returned titles (grounded)."""
    if not _ai_enabled() or not articles:
        return {}
    try:
        import anthropic

        titles = "\n".join(f"- {a['title']} ({a['journal']}, {a['year']})" for a in articles)

        class NoveltyRead(BaseModel):
            level: Literal["likely_done", "partially_addressed", "appears_novel", "uncertain"]
            summary: str

        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=MODEL,
            max_tokens=900,
            system=[{"type": "text", "text":
                     "You assess novelty for a perioperative research question. Judge ONLY from the "
                     "provided PubMed titles — do not invent citations or claim knowledge of papers not "
                     "listed. Be calibrated: 'likely_done' only if a listed title clearly answers the "
                     "same question; 'appears_novel' if none do. Two sentences max."}],
            messages=[{"role": "user", "content": f"Question: {question}\n\nRelated PubMed results:\n{titles}"}],
            output_format=NoveltyRead,
        )
        return resp.parsed_output.model_dump()
    except Exception:  # noqa: BLE001
        return {}


@app.post("/api/novelty")
def novelty(payload: dict) -> JSONResponse:
    question = (payload or {}).get("question", "").strip()
    concepts = (payload or {}).get("concepts", []) or []
    if not question:
        return JSONResponse({"error": "Empty question."}, status_code=400)
    # Build a query from the clinical concept labels (fall back to the raw question).
    terms = [c.get("label", "") for c in concepts if c.get("label")]
    query = " AND ".join(f'"{t}"' for t in terms[:3]) if terms else question
    articles = _pubmed_search(query)
    if not articles:  # broaden once
        articles = _pubmed_search(question)
    read = _novelty_query_and_read(question, concepts, articles)
    return JSONResponse({
        "query": query,
        "articles": articles,
        "assessment": read or None,
        "ai": _ai_enabled(),
        "price": NOVELTY_PRICE,
    })


# ---------------------------------------------------------------------------
# Idea discussion mode — a grounded brainstorming partner (AI only).
# ---------------------------------------------------------------------------
@app.post("/api/discuss")
def discuss(payload: dict) -> JSONResponse:
    msgs = (payload or {}).get("messages", []) or []
    if not _ai_enabled():
        return JSONResponse({"reply": None, "ai": False,
                             "message": "Discussion mode needs ANTHROPIC_API_KEY set on the server."})
    try:
        import anthropic

        sys = (
            "You are a perioperative-research brainstorming partner inside Afferent Intelligence, an "
            "engine that triages study feasibility against VitalDB (single-center SNUH: intraoperative "
            "waveforms/numerics, a clinical-info table, in-hospital outcomes, and a ±90-day lab series). "
            "Help the researcher shape a SPECIFIC, feasible PECO question. Be concise and Socratic — ask "
            "one sharp question at a time, propose concrete exposures/outcomes that VitalDB plausibly has, "
            "and steer away from ward-assessed or post-discharge outcomes it lacks (delirium, POCD, "
            "30-day mortality, readmission). When a question feels well-formed, tell them to run it "
            "through the feasibility check. Do NOT write the paper, the analysis, or make causal claims. "
            "Never assert a variable exists with certainty — say 'the feasibility check will verify it.'\n\n"
            f"VitalDB inventory (id | name | STATUS | category):\n{INVENTORY_LINES}"
        )
        clean = [{"role": m.get("role"), "content": m.get("content", "")}
                 for m in msgs if m.get("role") in ("user", "assistant") and m.get("content")]
        if not clean:
            return JSONResponse({"reply": None, "ai": True, "message": "No message."})
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1200,
            system=[{"type": "text", "text": sys, "cache_control": {"type": "ephemeral"}}],
            messages=clean,
        )
        reply = next((b.text for b in resp.content if b.type == "text"), "")
        return JSONResponse({"reply": reply, "ai": True})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"reply": None, "ai": True, "message": f"{type(exc).__name__}: {exc}"})


@app.get("/api/scope/file/{run_id}/{fname:path}")
def scope_file(run_id: str, fname: str):
    base = (SCOPE_DIR / run_id).resolve()
    target = (base / fname).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(target)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_HTML)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
