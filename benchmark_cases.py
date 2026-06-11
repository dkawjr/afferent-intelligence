"""benchmark_cases.py — regression suite for the VitalDB feasibility engine.

Each case carries a plain-English question, its PECO decomposition, the required
clinical concepts (snake_case, as the decomposition step would emit), and the
EXPECTED feasibility verdict. Running this file resolves every case's concepts
through lookup.py and asserts the derived verdict matches expectation.

Two families:
  * FEASIBLE cases  — drawn from published VitalDB work (intraoperative-only,
    using confirmed signals/numerics).
  * IMPOSSIBLE cases — constructed to require a CONFIRMED_ABSENT outcome. These
    must return NOT_FEASIBLE. The flagship is "burst suppression predicting
    postoperative delirium": the exposure exists, the outcome does not.

Run:
    py benchmark_cases.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lookup import feasibility_from_resolutions, resolve_all
from models import FeasibilityVerdict


@dataclass
class BenchmarkCase:
    name: str
    question: str
    population: str
    exposure: str
    comparator: str
    outcome: str
    required_concepts: list[str]
    expected: FeasibilityVerdict
    rationale: str
    source: str = "constructed"
    tags: list[str] = field(default_factory=list)


CASES: list[BenchmarkCase] = [
    # ---------------------------------------------------------------- FEASIBLE
    BenchmarkCase(
        name="hypotension_prediction_from_arterial_waveform",
        question="Can the arterial pressure waveform predict intraoperative hypotension (MAP < 65 mmHg)?",
        population="Surgical patients with an arterial line",
        exposure="Arterial pressure waveform features",
        comparator="Subsequent non-hypotensive periods",
        outcome="Intraoperative hypotension (MAP < 65 mmHg)",
        required_concepts=["arterial_waveform", "mean_arterial_pressure"],
        expected=FeasibilityVerdict.FEASIBLE,
        rationale="Both exposure (ART waveform) and outcome (intraoperative MAP) are confirmed intraoperative signals. This mirrors hypotension-prediction work built on VitalDB.",
        source="Lee et al., VitalDB hypotension-prediction literature",
        tags=["feasible", "hemodynamic"],
    ),
    BenchmarkCase(
        name="burst_suppression_vs_age",
        question="Does intraoperative burst suppression (suppression ratio) vary with patient age?",
        population="Cases monitored with BIS",
        exposure="Patient age",
        comparator="Across the age distribution",
        outcome="Burst suppression ratio (intraoperative)",
        required_concepts=["suppression_ratio", "age"],
        expected=FeasibilityVerdict.FEASIBLE,
        rationale="Suppression ratio is a confirmed intraoperative EEG-derived signal and age is a confirmed clinical-info column. Outcome is measured within the operative window.",
        source="VitalDB BIS/SR + clinical-info",
        tags=["feasible", "signal"],
    ),
    BenchmarkCase(
        name="asa_vs_intraoperative_desaturation",
        question="Is ASA physical status associated with intraoperative SpO2 desaturation?",
        population="Adult surgical patients",
        exposure="ASA physical status",
        comparator="Across ASA classes",
        outcome="Intraoperative SpO2 desaturation events",
        required_concepts=["asa_class", "spo2"],
        expected=FeasibilityVerdict.FEASIBLE,
        rationale="ASA and SpO2 are both confirmed; the outcome is an intraoperative event observable in VitalDB.",
        source="VitalDB clinical-info + Solar8000/PLETH_SPO2",
        tags=["feasible", "respiratory"],
    ),

    # --------------------------------------------- FEASIBLE WITH CAVEATS (derived/subset)
    BenchmarkCase(
        name="intraoperative_hypotension_and_postoperative_aki",
        question="Is intraoperative hypotension associated with postoperative acute kidney injury?",
        population="Surgical patients with pre- and postoperative creatinine",
        exposure="Intraoperative hypotension (MAP < 65 mmHg)",
        comparator="Patients without sustained hypotension",
        outcome="Postoperative AKI (derived from creatinine)",
        required_concepts=["mean_arterial_pressure", "postoperative_aki"],
        expected=FeasibilityVerdict.FEASIBLE_WITH_CAVEATS,
        rationale="MAP is confirmed; AKI has NO pre-labeled field, but postoperative creatinine exists in the +/-90-day lab series, so the endpoint is DERIVABLE. Caveats: postop draws are sparse/informative-missing, so the AKI cohort is a selected subset and the KDIGO urine-output criterion is unavailable.",
        source="VitalDB lab_data cr + Solar8000/ART_MBP",
        tags=["caveats", "derived_outcome"],
    ),
    BenchmarkCase(
        name="cardiac_output_and_in_hospital_mortality",
        question="Does low intraoperative cardiac output predict in-hospital mortality?",
        population="Cases monitored with an advanced hemodynamic monitor",
        exposure="Low intraoperative cardiac output",
        comparator="Normal cardiac output",
        outcome="In-hospital mortality",
        required_concepts=["cardiac_output", "in_hospital_mortality"],
        expected=FeasibilityVerdict.FEASIBLE_WITH_CAVEATS,
        rationale="Both confirmed, but cardiac output is a device-subset signal (few cases) and in-hospital mortality is a rare event -> power-limited. The outcome IS present (death_inhosp), so this is reachable, unlike a 30-day endpoint.",
        source="VitalDB EV1000/Vigileo CO + clinical_info.death_inhosp",
        tags=["caveats", "in_hospital_outcome"],
    ),
    BenchmarkCase(
        name="transfusion_and_icu_length_of_stay",
        question="Is intraoperative transfusion associated with ICU length of stay?",
        population="Surgical patients",
        exposure="Intraoperative RBC/FFP transfusion",
        comparator="No transfusion",
        outcome="ICU length of stay",
        required_concepts=["transfusion", "icu_length_of_stay"],
        expected=FeasibilityVerdict.FEASIBLE,
        rationale="Transfusion totals (intraop_rbc/ffp) and ICU days (icu_days) are both confirmed clinical-info columns at high confidence — a fully in-hospital exposure/outcome pair.",
        source="VitalDB clinical_info.intraop_rbc/ffp + icu_days",
        tags=["feasible", "in_hospital_outcome"],
    ),

    # -------------------------------------------------------------- IMPOSSIBLE
    BenchmarkCase(
        name="burst_suppression_predicting_postoperative_delirium",
        question="Can burst suppression predict postoperative delirium?",
        population="Surgical patients monitored with BIS",
        exposure="Intraoperative burst suppression (suppression ratio)",
        comparator="Patients without burst suppression",
        outcome="Postoperative delirium (CAM-assessed, POD 1-5)",
        required_concepts=["burst_suppression", "postoperative_delirium"],
        expected=FeasibilityVerdict.NOT_FEASIBLE,
        rationale="THE FLAGSHIP NO. Exposure (burst suppression / BIS SR) is confirmed present, but the outcome (postoperative delirium) is CONFIRMED_ABSENT: VitalDB is intraoperative-only, single-center, with no ward delirium screening or post-discharge follow-up. The study cannot be done in VitalDB alone regardless of how good the EEG signal is.",
        source="constructed (canonical impossible case)",
        tags=["impossible", "outcome_absent", "flagship"],
    ),
    BenchmarkCase(
        name="map_predicting_30day_mortality",
        question="Does intraoperative mean arterial pressure predict 30-day mortality?",
        population="Surgical patients",
        exposure="Intraoperative MAP / hypotension exposure",
        comparator="Patients without hypotension",
        outcome="30-day mortality",
        required_concepts=["mean_arterial_pressure", "mortality_30day"],
        expected=FeasibilityVerdict.NOT_FEASIBLE,
        rationale="Exposure confirmed, but 30-day mortality is CONFIRMED_ABSENT — no post-discharge vital-status follow-up or registry linkage exists.",
        source="constructed",
        tags=["impossible", "outcome_absent"],
    ),
    BenchmarkCase(
        name="tidal_volume_reducing_readmission",
        question="Does intraoperative low tidal volume ventilation reduce 30-day hospital readmission?",
        population="Mechanically ventilated surgical patients",
        exposure="Low tidal volume ventilation",
        comparator="Conventional tidal volume",
        outcome="30-day hospital readmission",
        required_concepts=["tidal_volume", "readmission"],
        expected=FeasibilityVerdict.NOT_FEASIBLE,
        rationale="Exposure confirmed, but readmission is CONFIRMED_ABSENT — the dataset ends at the operative episode with no longitudinal encounter history.",
        source="constructed",
        tags=["impossible", "outcome_absent"],
    ),
    BenchmarkCase(
        name="genetic_modifiers_of_anesthetic_depth",
        question="Do genetic markers modify the relationship between anesthetic dose and BIS-measured depth?",
        population="Surgical patients monitored with BIS",
        exposure="Genetic markers / pharmacogenomic variants",
        comparator="Across genotypes",
        outcome="BIS-measured anesthetic depth",
        required_concepts=["genetic_markers", "bis_index"],
        expected=FeasibilityVerdict.NOT_FEASIBLE,
        rationale="Outcome (BIS) confirmed, but the exposure (genetic data) is CONFIRMED_ABSENT — VitalDB contains no biospecimens or genotyping of any kind.",
        source="constructed",
        tags=["impossible", "exposure_absent"],
    ),
    BenchmarkCase(
        name="pocd_from_intraoperative_signals",
        question="Can intraoperative EEG features predict postoperative cognitive dysfunction (POCD)?",
        population="Surgical patients monitored with BIS",
        exposure="Intraoperative EEG / suppression features",
        comparator="Patients without suppression",
        outcome="Postoperative cognitive dysfunction",
        required_concepts=["suppression_ratio", "pocd"],
        expected=FeasibilityVerdict.NOT_FEASIBLE,
        rationale="Exposure confirmed, but POCD is CONFIRMED_ABSENT — requires baseline/follow-up neuropsychological testing absent from VitalDB.",
        source="constructed",
        tags=["impossible", "outcome_absent"],
    ),

    # --------------------------------------------------- INSUFFICIENT (no-guess)
    BenchmarkCase(
        name="neuromuscular_block_depth_unverified",
        question="Does train-of-four monitored neuromuscular block depth affect emergence time?",
        population="Surgical patients",
        exposure="Train-of-four / neuromuscular block depth",
        comparator="Across block depths",
        outcome="Emergence time",
        required_concepts=["train_of_four", "emergence_time"],
        expected=FeasibilityVerdict.INSUFFICIENT_INFO,
        rationale="Neither concept is in the verified inventory. The honest answer is NOT 'no' and NOT 'yes' — it is 'unverified'. The no-guessing rule forbids asserting these exist or are absent until checked against VitalDB documentation.",
        source="constructed (tests no-guessing path)",
        tags=["insufficient", "no_guess"],
    ),
]


def run() -> int:
    print("\nVitalDB feasibility-engine benchmark")
    print("=" * 72)
    passed = 0
    failed = 0
    for case in CASES:
        resolutions = resolve_all(case.required_concepts)
        got = feasibility_from_resolutions(resolutions)
        ok = got == case.expected
        passed += ok
        failed += not ok
        mark = "PASS" if ok else "FAIL"
        print(f"\n[{mark}] {case.name}")
        print(f"       Q: {case.question}")
        detail = "  ".join(f"{r.query}={r.status.value}" for r in resolutions)
        print(f"       concepts: {detail}")
        print(f"       expected={case.expected.value}  got={got.value}")
        if not ok:
            print(f"       !!! MISMATCH — {case.rationale}")

    print("\n" + "=" * 72)
    print(f"Result: {passed} passed, {failed} failed, {len(CASES)} total")

    # Hard guard on the flagship case — the whole point of the engine.
    flagship = next(c for c in CASES if "flagship" in c.tags)
    flag_verdict = feasibility_from_resolutions(resolve_all(flagship.required_concepts))
    assert flag_verdict == FeasibilityVerdict.NOT_FEASIBLE, (
        f"FLAGSHIP REGRESSION: '{flagship.question}' returned {flag_verdict.value}, "
        f"expected NOT_FEASIBLE."
    )
    print("Flagship guard OK: burst suppression -> postoperative delirium == NOT_FEASIBLE")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
