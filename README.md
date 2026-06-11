# Afferent Intelligence — VitalDB research feasibility engine

A triage machine for perioperative research questions. Describe a study in plain
English; it tells you whether VitalDB can actually support it **before** you spend
months on it. The most valuable output is a **trustworthy "no."**

## The pipeline (and the no-guessing rule)

1. **Decompose** (inference) — the question becomes PECO and a list of required
   clinical concepts.
2. **Resolve** (verified facts) — each concept is checked against the verified
   inventory (`inventory/vitaldb.json`): `CONFIRMED` / `CONFIRMED_ABSENT` /
   `NOT_IN_INVENTORY`. **Status comes only from the inventory, never from the model.**
3. **Verdict** — any confirmed-absent concept → `NOT_FEASIBLE`; anything unverified
   → `INSUFFICIENT_INFO`; otherwise `FEASIBLE` / `FEASIBLE_WITH_CAVEATS`.

Inference and verified facts are kept in separate UI sections on purpose — the
engine's trust comes from never blurring the two.

## Run the web app

```powershell
py -m pip install -r requirements.txt

# AI mode (recommended) — the decompose step uses Claude, so it handles free-form phrasing:
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # your Anthropic API key
py -m uvicorn app:app --host 127.0.0.1 --port 8000
# then open http://127.0.0.1:8000
```

Without `ANTHROPIC_API_KEY`, the app still runs — it falls back to a built-in
**keyword matcher** for the decompose step (the resolver, inventory, and verdict
logic are identical; only concept *detection* differs). The mode badge in the
header shows which is active.

- Model is `claude-opus-4-8` by default; override with `AFFERENT_MODEL`.
- Opening `index.html` directly as a file also works (offline keyword mode only).

## Command-line tools

```powershell
py lookup.py burst_suppression postoperative_delirium --verdict   # resolve concepts
py benchmark_cases.py                                             # regression suite
py build_frontend.py                                             # regenerate index.html from the inventory
```

## How the no-guessing rule is enforced in AI mode

The model is given the verified inventory so it can **map** each concept to the
best inventory id and craft a grounded reframe — but it is structurally forbidden
from asserting availability. Every concept id it returns is re-resolved through
`lookup.py`; the status is read from the inventory, not the model. A concept the
model can't map (returns `null`) resolves to `NOT_IN_INVENTORY`, never a guessed
yes/no.

## Files

| File | Role |
|------|------|
| `CLAUDE.md` | Pipeline + no-guessing rule (context for the model). |
| `app.py` | FastAPI backend: `/api/feasibility` (decompose → resolve → verdict), `/api/health`, serves the UI. |
| `lookup.py` | Concept resolver + `ALIAS_TABLE` + verdict logic. |
| `models.py` | Pydantic models; `can_assert_existence()` / `is_confirmed_absent()` enforce the rule. |
| `inventory/vitaldb.json` | The verified inventory — the single source of truth. |
| `benchmark_cases.py` | Feasible + impossible regression cases. |
| `build_frontend.py` | Generates `index.html` from the inventory. |
| `index.html` | The generated single-page app (self-contained). |

Inventory provenance: VitalDB data descriptor (Lee et al., *Scientific Data* 2022)
and PhysioNet vitaldb 1.0.0.
