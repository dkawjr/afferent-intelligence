"""Pydantic models for the VitalDB research-feasibility engine.

These models encode the *no-guessing rule*: the engine may never assert that a
clinical variable exists in VitalDB unless the verified inventory explicitly
confirms it. The two gate methods below — `can_assert_existence()` and
`is_confirmed_absent()` — are the only sanctioned way to answer "is this
variable available?" Everything downstream (lookup.py, the feasibility verdict)
routes its existence claims through them.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InventoryStatus(str, Enum):
    """The two states a *catalogued* concept can have in the inventory.

    A concept that is simply not in the inventory is NOT represented here — that
    is the third resolution state (NOT_IN_INVENTORY) produced at lookup time,
    precisely because we have made no verified claim about it either way.
    """

    CONFIRMED = "CONFIRMED"               # verified present in VitalDB
    CONFIRMED_ABSENT = "CONFIRMED_ABSENT"  # verified NOT collected by VitalDB


class ConfidenceLevel(str, Enum):
    """How strong the evidence is for the inventory entry's status."""

    HIGH = "high"      # documented in the official VitalDB schema / track list
    MEDIUM = "medium"  # present but with caveats (derived, sparse, partial)
    LOW = "low"        # plausible but under-verified — treat with suspicion


class ResolutionStatus(str, Enum):
    """The verdict for a single concept after a lookup against the inventory."""

    CONFIRMED = "CONFIRMED"
    CONFIRMED_ABSENT = "CONFIRMED_ABSENT"
    NOT_IN_INVENTORY = "NOT_IN_INVENTORY"


class VariableEntry(BaseModel):
    """One catalogued clinical concept and what we have verified about it.

    An entry exists for a concept ONLY when we have done the verification work to
    say either "this is present" (CONFIRMED) or "this is genuinely not collected"
    (CONFIRMED_ABSENT). Absence of an entry is itself meaningful — it means we
    have not verified the concept, so the engine must refuse to assert anything.
    """

    id: str = Field(..., description="Stable inventory ID, e.g. 'bis_suppression_ratio'.")
    name: str = Field(..., description="Human-readable concept name.")
    aliases: list[str] = Field(default_factory=list, description="Other names callers may use.")
    status: InventoryStatus
    category: str = Field(..., description="signal | hemodynamic | respiratory | demographic | outcome | other")
    confidence_level: ConfidenceLevel
    vitaldb_track: Optional[str] = Field(
        default=None,
        description="Vital Recorder track or clinical-info column, e.g. 'BIS/SR'. None for absent concepts.",
    )
    units: Optional[str] = None
    missingness: str = Field(..., description="What is missing/sparse and how often — the honest caveat.")
    common_mistakes: str = Field(..., description="The wrong assumption researchers make about this concept.")
    notes: str = ""

    def is_confirmed_absent(self) -> bool:
        """True iff we have VERIFIED this concept is not collected by VitalDB.

        This is the trustworthy 'no'. A True here should hard-stop any study
        design that depends on this concept as an outcome or exposure.
        """
        return self.status == InventoryStatus.CONFIRMED_ABSENT

    def can_assert_existence(self) -> bool:
        """True iff the engine is allowed to claim this variable EXISTS.

        The no-guessing rule lives here: existence may be asserted only for a
        CONFIRMED entry. CONFIRMED_ABSENT entries return False (they exist in the
        catalogue, but the *variable* does not). There is deliberately no path to
        True for an un-catalogued concept — callers never construct an entry for
        one; the lookup reports NOT_IN_INVENTORY instead.
        """
        return self.status == InventoryStatus.CONFIRMED

    @classmethod
    def from_inventory(cls, raw: dict) -> "VariableEntry":
        """Validate one raw JSON record from inventory/vitaldb.json."""
        return cls.model_validate(raw)


class ConceptResolution(BaseModel):
    """The result of resolving one queried concept against the inventory."""

    query: str = Field(..., description="The concept name as the caller typed it.")
    resolved_id: Optional[str] = Field(default=None, description="Inventory ID it mapped to, if any.")
    status: ResolutionStatus
    entry: Optional[VariableEntry] = None

    def can_assert_existence(self) -> bool:
        return self.entry is not None and self.entry.can_assert_existence()

    def is_confirmed_absent(self) -> bool:
        return self.entry is not None and self.entry.is_confirmed_absent()


class FeasibilityVerdict(str, Enum):
    FEASIBLE = "FEASIBLE"
    FEASIBLE_WITH_CAVEATS = "FEASIBLE_WITH_CAVEATS"
    NOT_FEASIBLE = "NOT_FEASIBLE"
    INSUFFICIENT_INFO = "INSUFFICIENT_INFO"


class Inventory(BaseModel):
    """Top-level inventory document."""

    dataset: str
    description: str = ""
    scope: dict = Field(default_factory=dict)
    variables: list[VariableEntry] = Field(default_factory=list)
