"""lookup.py — resolve clinical concepts against the verified VitalDB inventory.

Usage:
    py lookup.py burst_suppression postoperative_delirium map heart_rate
    py lookup.py --json suppression_ratio mortality_30day

For each concept name supplied, it prints a truth-table row with one of:
    CONFIRMED          — the inventory verifies this variable EXISTS in VitalDB
    CONFIRMED_ABSENT   — the inventory verifies this variable is NOT collected
    NOT_IN_INVENTORY   — we have not verified this concept; assert NOTHING

This is step (2) of the feasibility pipeline. It makes no judgement about study
feasibility on its own — it only reports verified ground truth so that step (3)
can build a verdict without guessing. The no-guessing rule is enforced upstream
in models.py (`VariableEntry.can_assert_existence`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from models import (
    ConceptResolution,
    FeasibilityVerdict,
    Inventory,
    ResolutionStatus,
    VariableEntry,
)

INVENTORY_PATH = Path(__file__).parent / "inventory" / "vitaldb.json"

# ---------------------------------------------------------------------------
# Concept alias table: snake_case concept names -> inventory IDs.
#
# This is the curated front door. The decomposition step (1) emits snake_case
# concept names; this table maps the common phrasings to a stable inventory ID.
# Per-entry `aliases` in the JSON provide a second, data-driven layer, but this
# explicit table is the authoritative mapping and is intentionally easy to read
# and extend. A name NOT found here AND not matched by any entry alias resolves
# to NOT_IN_INVENTORY — which is the correct, honest answer.
# ---------------------------------------------------------------------------
ALIAS_TABLE: dict[str, str] = {
    # --- signals ---
    "bis": "bis_index",
    "bis_index": "bis_index",
    "bispectral_index": "bis_index",
    "depth_of_anesthesia": "bis_index",
    "anesthetic_depth": "bis_index",
    "suppression_ratio": "bis_suppression_ratio",
    "sr": "bis_suppression_ratio",
    "burst_suppression": "bis_suppression_ratio",
    "burst_suppression_ratio": "bis_suppression_ratio",
    "eeg_suppression": "bis_suppression_ratio",
    "arterial_waveform": "arterial_waveform",
    "art_waveform": "arterial_waveform",
    "arterial_line": "arterial_waveform",
    "abp_waveform": "arterial_waveform",
    "invasive_bp_waveform": "arterial_waveform",
    # --- hemodynamic ---
    "map": "mean_arterial_pressure",
    "mean_arterial_pressure": "mean_arterial_pressure",
    "mean_bp": "mean_arterial_pressure",
    "mbp": "mean_arterial_pressure",
    "intraoperative_hypotension": "mean_arterial_pressure",
    "hypotension": "mean_arterial_pressure",
    "hr": "heart_rate",
    "heart_rate": "heart_rate",
    "pulse_rate": "heart_rate",
    "ecg": "ecg_waveform",
    "ekg": "ecg_waveform",
    "ppg": "plethysmograph",
    "pleth": "plethysmograph",
    "blood_pressure": "blood_pressure",
    "systolic_bp": "blood_pressure",
    "diastolic_bp": "blood_pressure",
    "raw_eeg": "raw_eeg",
    "eeg": "raw_eeg",
    "cardiac_output": "cardiac_output",
    "cardiac_index": "cardiac_output",
    "low_cardiac_output": "cardiac_output",
    "stroke_volume_variation": "stroke_volume_variation",
    "svv": "stroke_volume_variation",
    "cerebral_oximetry": "cerebral_oximetry",
    "nirs": "cerebral_oximetry",
    "tci": "tci_concentration",
    "effect_site_concentration": "tci_concentration",
    "body_temperature": "body_temperature",
    "temperature": "body_temperature",
    "hypothermia": "body_temperature",
    # --- respiratory ---
    "spo2": "spo2",
    "oxygen_saturation": "spo2",
    "pulse_oximetry": "spo2",
    "o2_sat": "spo2",
    "desaturation": "spo2",
    "etco2": "etco2",
    "end_tidal_co2": "etco2",
    "capnography": "etco2",
    "respiratory_rate": "respiratory_rate",
    "tidal_volume": "tidal_volume",
    "tv": "tidal_volume",
    "vt": "tidal_volume",
    "ventilator_tidal_volume": "tidal_volume",
    "airway_pressure": "airway_pressure",
    "peak_pressure": "airway_pressure",
    "peep": "airway_pressure",
    "fio2": "fio2",
    "inspired_oxygen": "fio2",
    "sevoflurane": "anesthetic_agent_concentration",
    "desflurane": "anesthetic_agent_concentration",
    "mac": "anesthetic_agent_concentration",
    "volatile_concentration": "anesthetic_agent_concentration",
    # --- demographic / case ---
    "age": "age",
    "asa": "asa_class",
    "asa_class": "asa_class",
    "asa_physical_status": "asa_class",
    "sex": "sex",
    "gender": "sex",
    "height": "height",
    "weight": "weight",
    "bmi": "bmi",
    "obesity": "bmi",
    "emergency_surgery": "emergency_surgery",
    "emop": "emergency_surgery",
    "anesthesia_type": "anesthesia_type",
    "tiva": "anesthesia_type",
    "surgery_type": "surgery_type",
    "operation": "surgery_type",
    "procedure": "surgery_type",
    "optype": "surgery_type",
    "opname": "surgery_type",
    "department": "surgery_type",
    "diagnosis": "surgery_type",
    "surgical_approach": "surgical_approach_position",
    "position": "surgical_approach_position",
    # --- intraoperative interventions ---
    "estimated_blood_loss": "estimated_blood_loss",
    "ebl": "estimated_blood_loss",
    "blood_loss": "estimated_blood_loss",
    "urine_output": "urine_output",
    "transfusion": "transfusion",
    "rbc_transfusion": "transfusion",
    "ffp_transfusion": "transfusion",
    "blood_products": "transfusion",
    "fluid_administration": "fluid_administration",
    "crystalloid": "fluid_administration",
    "colloid": "fluid_administration",
    "vasopressor_dose": "vasopressor_dose",
    "phenylephrine": "vasopressor_dose",
    "ephedrine": "vasopressor_dose",
    "epinephrine": "vasopressor_dose",
    "propofol_dose": "anesthetic_drug_dose",
    "fentanyl": "anesthetic_drug_dose",
    "rocuronium": "anesthetic_drug_dose",
    # --- comorbidity / labs ---
    "preop_comorbidity": "preop_comorbidity",
    "hypertension_history": "preop_comorbidity",
    "diabetes_history": "preop_comorbidity",
    "preoperative_labs": "preoperative_labs",
    "preop_labs": "preoperative_labs",
    "baseline_creatinine": "preoperative_labs",
    "laboratory_results": "laboratory_timeseries",
    "labs": "laboratory_timeseries",
    "postoperative_labs": "laboratory_timeseries",
    "lactate": "laboratory_timeseries",
    "crp": "laboratory_timeseries",
    "hemoglobin": "laboratory_timeseries",
    "postoperative_creatinine": "postoperative_creatinine",
    "postop_creatinine": "postoperative_creatinine",
    "creatinine": "postoperative_creatinine",
    "postoperative_aki": "postoperative_creatinine",
    "aki": "postoperative_creatinine",
    "acute_kidney_injury": "postoperative_creatinine",
    # --- in-hospital outcomes (CONFIRMED) ---
    "in_hospital_mortality": "in_hospital_mortality",
    "death_inhosp": "in_hospital_mortality",
    "operative_mortality": "in_hospital_mortality",
    "icu_length_of_stay": "icu_length_of_stay",
    "icu_days": "icu_length_of_stay",
    "icu_los": "icu_length_of_stay",
    "hospital_length_of_stay": "hospital_length_of_stay",
    "hospital_los": "hospital_length_of_stay",
    "los": "hospital_length_of_stay",
    "length_of_stay": "hospital_length_of_stay",
    # --- confirmed-absent outcomes ---
    "postoperative_delirium": "postoperative_delirium",
    "delirium": "postoperative_delirium",
    "post_op_delirium": "postoperative_delirium",
    "pod": "postoperative_delirium",
    "pocd": "pocd",
    "postoperative_cognitive_dysfunction": "pocd",
    "cognitive_decline": "pocd",
    "cognitive_testing": "pocd",
    "mortality_30day": "mortality_30day",
    "30_day_mortality": "mortality_30day",
    "thirty_day_mortality": "mortality_30day",
    "postoperative_mortality": "mortality_30day",
    "90_day_mortality": "mortality_30day",
    "long_term_mortality": "mortality_30day",
    "readmission": "readmission",
    "30_day_readmission": "readmission",
    "hospital_readmission": "readmission",
    "postoperative_pain": "postoperative_pain",
    "pain_score": "postoperative_pain",
    "nrs_pain": "postoperative_pain",
    "ponv": "ponv",
    "postoperative_nausea": "ponv",
    "genetic_data": "genetic_data",
    "genomics": "genetic_data",
    "genotype": "genetic_data",
    "pharmacogenomics": "genetic_data",
    "genetic_markers": "genetic_data",
}


def normalize(concept: str) -> str:
    """Canonicalize a concept name to the snake_case key form."""
    return (
        concept.strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def load_inventory(path: Path = INVENTORY_PATH) -> Inventory:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Inventory.model_validate(raw)


def _build_index(inv: Inventory) -> dict[str, VariableEntry]:
    """Index entries by ID plus every per-entry alias (data-driven layer)."""
    index: dict[str, VariableEntry] = {}
    for entry in inv.variables:
        index[entry.id] = entry
        for alias in entry.aliases:
            index.setdefault(normalize(alias), entry)
    return index


def resolve(concept: str, inv: Inventory, index: dict[str, VariableEntry]) -> ConceptResolution:
    """Resolve a single concept against the inventory — no guessing."""
    key = normalize(concept)
    entry = None
    # 1) authoritative alias table -> inventory ID
    target_id = ALIAS_TABLE.get(key)
    if target_id is not None:
        entry = index.get(target_id)
    # 2) fall back to the data-driven alias/id index
    if entry is None:
        entry = index.get(key)

    if entry is None:
        return ConceptResolution(query=concept, status=ResolutionStatus.NOT_IN_INVENTORY)

    status = (
        ResolutionStatus.CONFIRMED
        if entry.can_assert_existence()
        else ResolutionStatus.CONFIRMED_ABSENT
    )
    return ConceptResolution(query=concept, resolved_id=entry.id, status=status, entry=entry)


def resolve_all(concepts: list[str]) -> list[ConceptResolution]:
    inv = load_inventory()
    index = _build_index(inv)
    return [resolve(c, inv, index) for c in concepts]


def feasibility_from_resolutions(resolutions: list[ConceptResolution]) -> FeasibilityVerdict:
    """Derive a coarse feasibility signal from resolved required concepts.

    Rules, in order of severity:
      * ANY required concept CONFIRMED_ABSENT  -> NOT_FEASIBLE (the trustworthy no)
      * ANY required concept NOT_IN_INVENTORY  -> INSUFFICIENT_INFO (must verify)
      * ALL required concepts CONFIRMED, some MEDIUM/LOW confidence -> FEASIBLE_WITH_CAVEATS
      * ALL required concepts CONFIRMED at HIGH confidence -> FEASIBLE
    """
    if not resolutions:
        return FeasibilityVerdict.INSUFFICIENT_INFO
    if any(r.status == ResolutionStatus.CONFIRMED_ABSENT for r in resolutions):
        return FeasibilityVerdict.NOT_FEASIBLE
    if any(r.status == ResolutionStatus.NOT_IN_INVENTORY for r in resolutions):
        return FeasibilityVerdict.INSUFFICIENT_INFO
    if any(r.entry is not None and r.entry.confidence_level.value != "high" for r in resolutions):
        return FeasibilityVerdict.FEASIBLE_WITH_CAVEATS
    return FeasibilityVerdict.FEASIBLE


# ---------------------------------------------------------------------------
# CLI rendering
# ---------------------------------------------------------------------------
_SYMBOL = {
    ResolutionStatus.CONFIRMED: "[+]",
    ResolutionStatus.CONFIRMED_ABSENT: "[-]",
    ResolutionStatus.NOT_IN_INVENTORY: "[?]",
}


def render_table(resolutions: list[ConceptResolution]) -> str:
    qw = max((len(r.query) for r in resolutions), default=7)
    qw = max(qw, len("CONCEPT"))
    iw = max((len(r.resolved_id or "-") for r in resolutions), default=11)
    iw = max(iw, len("RESOLVED_ID"))
    sw = len("CONFIRMED_ABSENT")

    lines = []
    header = f"    {'CONCEPT'.ljust(qw)}  {'RESOLVED_ID'.ljust(iw)}  {'STATUS'.ljust(sw)}  TRACK"
    lines.append(header)
    lines.append("    " + "-" * (len(header) - 4))
    for r in resolutions:
        track = (r.entry.vitaldb_track if r.entry and r.entry.vitaldb_track else "")
        if r.status == ResolutionStatus.CONFIRMED_ABSENT:
            track = "(not collected)"
        elif r.status == ResolutionStatus.NOT_IN_INVENTORY:
            track = "(unverified)"
        sym = _SYMBOL[r.status]
        lines.append(
            f"{sym} {r.query.ljust(qw)}  {(r.resolved_id or '-').ljust(iw)}  "
            f"{r.status.value.ljust(sw)}  {track}"
        )
    return "\n".join(lines)


def render_notes(resolutions: list[ConceptResolution]) -> str:
    out = []
    for r in resolutions:
        if r.entry is None:
            out.append(
                f"\n[?] {r.query}: NOT_IN_INVENTORY. No verified entry exists. "
                f"Per the no-guessing rule, do NOT assert this variable is present "
                f"or absent — it must be verified against VitalDB documentation first."
            )
            continue
        e = r.entry
        out.append(f"\n{_SYMBOL[r.status]} {r.query} -> {e.id} ({e.status.value}, confidence={e.confidence_level.value})")
        out.append(f"      missingness: {e.missingness}")
        out.append(f"      common mistake: {e.common_mistakes}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve clinical concepts against the verified VitalDB inventory.")
    parser.add_argument("concepts", nargs="+", help="Concept names (snake_case or natural).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of a table.")
    parser.add_argument("--verdict", action="store_true", help="Also print the derived feasibility signal.")
    args = parser.parse_args(argv)

    resolutions = resolve_all(args.concepts)

    if args.json:
        payload = {
            "resolutions": [
                {
                    "query": r.query,
                    "resolved_id": r.resolved_id,
                    "status": r.status.value,
                    "confidence": (r.entry.confidence_level.value if r.entry else None),
                    "vitaldb_track": (r.entry.vitaldb_track if r.entry else None),
                }
                for r in resolutions
            ],
            "feasibility_signal": feasibility_from_resolutions(resolutions).value,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print("\nVitalDB inventory truth table")
    print("=" * 60)
    print(render_table(resolutions))
    print(render_notes(resolutions))

    if args.verdict:
        verdict = feasibility_from_resolutions(resolutions)
        print("\n" + "=" * 60)
        print(f"Derived feasibility signal: {verdict.value}")
        absent = [r.query for r in resolutions if r.status == ResolutionStatus.CONFIRMED_ABSENT]
        if absent:
            print(f"  Blocked by confirmed-absent concept(s): {', '.join(absent)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
