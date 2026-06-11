# VitalDB Research Feasibility Engine

This project is a **triage machine for perioperative research questions**. Given a
plain-English study idea, it tells a researcher whether the study can actually be
done in **VitalDB** *before* they spend months on it. The most valuable output this
engine produces is a **trustworthy "no."**

A confident, well-justified NOT_FEASIBLE that saves someone from a doomed protocol
is worth more than ten optimistic maybes. Optimize for that.

---

## What VitalDB is (and is not)

- **Single center**: Seoul National University Hospital, Seoul, South Korea. ~6,388 cases.
- **Three data layers**:
  1. **Intraoperative tracks** — high-resolution waveforms + numerics (~196 parameters,
     11 devices: Solar8000, SNUADC, Primus, BIS, Orchestra pumps, EV1000/Vigileo, INVOS,
     CardioQ).
  2. **Clinical-information table** (~74 per-case parameters) — demographics, surgery/
     anesthesia, intraoperative drugs/fluids/transfusion, and a few **in-hospital
     outcomes**: `death_inhosp` (in-hospital mortality), `icu_days` (ICU LOS), and
     `adm`/`dis` (→ hospital LOS).
  3. **Perioperative lab time-series** — 34 blood tests spanning **90 days before to 90
     days after** anesthesia start. So *some* postoperative labs (e.g. creatinine → a
     **derivable** AKI endpoint) exist, but only when clinically ordered (sparse,
     informative-missing).

- **What is genuinely absent**: structured **ward** assessments (delirium, POCD, pain,
  PONV), **post-discharge** vital status / **30-day** mortality (only in-hospital death
  is recorded), **readmission** tracking, registry linkage, and any biospecimens/genetics.

The boundary is not "leaves the OR" — it is "leaves the **index hospitalization**", plus
a ±90-day lab window. The engine's core job is to locate that boundary precisely for each
question: an **in-hospital** or **lab-derivable** outcome may be feasible; a **ward-assessed**
or **post-discharge** outcome is the trustworthy "no". Do not over-reject (in-hospital
mortality / AKI are reachable) and do not over-accept (delirium / 30-day / readmission are not).

---

## The three-step pipeline

**Step 1 — Decompose (you, the model).**
Turn the plain-English question into **PECO** (Population, Exposure, Comparator,
Outcome) and list the **required clinical concepts** as snake_case names
(e.g. `burst_suppression`, `postoperative_delirium`, `mean_arterial_pressure`).
Be exhaustive about the *outcome* — that is where feasibility usually breaks.

**Step 2 — Resolve (the script).**
Run the concepts through the inventory resolver. Never resolve from memory.

```
py lookup.py <concept> [<concept> ...] --verdict
```

Each concept comes back as exactly one of:
- `CONFIRMED` — verified present in VitalDB (truth table lists the track/column).
- `CONFIRMED_ABSENT` — verified **not** collected. This is a hard stop.
- `NOT_IN_INVENTORY` — we have **not** verified it. Not a yes, not a no.

**Step 3 — Verdict (you, the model).**
Write the feasibility verdict **citing the lookup output**. The verdict is one of
`FEASIBLE`, `FEASIBLE_WITH_CAVEATS`, `NOT_FEASIBLE`, `INSUFFICIENT_INFO`. Quote the
status of each required concept. If any required concept is `CONFIRMED_ABSENT`, the
verdict is `NOT_FEASIBLE` and you name the missing variable as the reason.

---

## THE NO-GUESSING RULE (non-negotiable)

> **Never assert that a variable exists in VitalDB unless the inventory confirms it.**

Concretely:
- You may state "X is available" **only** when `lookup.py` returns `CONFIRMED` for X.
- A `CONFIRMED_ABSENT` result means X is verified missing — say so plainly and stop.
- A `NOT_IN_INVENTORY` result means **you do not know**. Do **not** guess either way.
  Report `INSUFFICIENT_INFO`, and say the concept must be verified against VitalDB
  documentation and added to the inventory before the question can be answered.
- Plausibility is not evidence. "A vital-signs database probably has lactate" is
  exactly the reasoning this engine exists to stop. If it is not in the inventory,
  you have not verified it.

The rule is enforced in code by `models.VariableEntry.can_assert_existence()` — it
returns `True` only for `CONFIRMED` entries. Route every existence claim through the
lookup; do not narrate around it.

---

## Files

| File | Role |
|------|------|
| `CLAUDE.md` | This context — the pipeline and the no-guessing rule. |
| `lookup.py` | Step 2 resolver. Concepts → CONFIRMED / CONFIRMED_ABSENT / NOT_IN_INVENTORY, with an `ALIAS_TABLE` mapping snake_case names to inventory IDs. `--verdict` derives the feasibility signal; `--json` for machine output. |
| `models.py` | Pydantic models. `can_assert_existence()` and `is_confirmed_absent()` enforce the no-guessing rule. |
| `inventory/vitaldb.json` | The verified inventory. Each entry carries `confidence_level`, `missingness`, and `common_mistakes`. **The only source of truth.** |
| `benchmark_cases.py` | Feasible cases (from published VitalDB work) + constructed-impossible cases. Run it as a regression suite. |

---

## How to answer a feasibility question (worked recipe)

1. Restate the question as PECO; enumerate required concepts in snake_case.
2. `py lookup.py <concepts...> --verdict` — do not skip this even if you "know."
3. Read the truth table. For each concept, note CONFIRMED / CONFIRMED_ABSENT /
   NOT_IN_INVENTORY and the `missingness` / `common_mistakes` notes.
4. Derive the verdict:
   - any `CONFIRMED_ABSENT` → **NOT_FEASIBLE** (name the missing variable).
   - any `NOT_IN_INVENTORY` → **INSUFFICIENT_INFO** (say what must be verified).
   - all `CONFIRMED`, some medium/low confidence or notable missingness →
     **FEASIBLE_WITH_CAVEATS** (state the caveats).
   - all `CONFIRMED` at high confidence → **FEASIBLE**.
5. Write the verdict citing the lookup output. Lead with the verdict, then the
   one-sentence reason, then the per-concept evidence.

## Extending the inventory

Add a concept only after verifying it against VitalDB documentation (track list /
clinical-info schema / published data descriptor). Set an honest `confidence_level`,
fill `missingness` and `common_mistakes`, and add snake_case aliases to
`ALIAS_TABLE` in `lookup.py`. Prefer `CONFIRMED_ABSENT` (a verified no) over leaving
a commonly-requested-but-missing concept as `NOT_IN_INVENTORY` — verified absences
are what make the engine fast and trustworthy.
