"""Data models for the wound care billing pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class RoutingDecision(str, Enum):
    AUTO_ACCEPT = "auto_accept"
    FLAG_FOR_REVIEW = "flag_for_review"
    REJECT = "reject"


class NoteFormat(str, Enum):
    STRUCTURED = "structured"
    PROSE = "prose"
    MULTI_WOUND = "multi_wound"
    ENVIVE = "envive"
    UNKNOWN = "unknown"


@dataclass
class Diagnosis:
    id: int
    patient_id: str
    icd10_code: Optional[str] = None
    icd10_description: Optional[str] = None
    clinical_status: Optional[str] = None
    onset_date: Optional[str] = None
    last_modified_at: Optional[str] = None


@dataclass
class Coverage:
    id: int
    patient_id: str
    payer_name: Optional[str] = None
    payer_code: Optional[str] = None
    payer_type: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    last_modified_at: Optional[str] = None


@dataclass
class ProgressNote:
    id: int
    patient_id: int
    org_id: str = ""
    pcc_note_id: Optional[int] = None
    note_type: Optional[str] = None
    effective_date: Optional[str] = None
    note_text: Optional[str] = None
    created_by: Optional[str] = None
    note_label: Optional[str] = None
    sync_version: int = 1
    is_current: bool = True


@dataclass
class Assessment:
    id: int
    patient_id: int
    org_id: str = ""
    pcc_assessment_id: Optional[int] = None
    assessment_type: Optional[str] = None
    status: Optional[str] = None
    assessment_date: Optional[str] = None
    completion_date: Optional[str] = None
    template_id: Optional[int] = None
    assessment_type_description: Optional[str] = None
    raw_json: Optional[str] = None
    sync_version: int = 1
    is_current: bool = True

    def parsed_json(self) -> dict:
        if self.raw_json:
            try:
                return json.loads(self.raw_json)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}


@dataclass
class WoundData:
    wound_type: Optional[str] = None
    wound_stage: Optional[int] = None
    location: Optional[str] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    drainage_amount: Optional[str] = None
    needs_review: bool = False
    extraction_source: str = "unknown"
    note_format: str = NoteFormat.UNKNOWN.value

    def has_complete_measurements(self) -> bool:
        return all(v is not None for v in [self.length_cm, self.width_cm, self.depth_cm])

    def has_wound(self) -> bool:
        return self.wound_type is not None


@dataclass
class Patient:
    id: int
    facility_id: int
    patient_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    primary_payer_code: Optional[str] = None
    last_modified_at: Optional[str] = None
    is_new_admission: bool = False
    diagnoses: list[Diagnosis] = field(default_factory=list)
    coverages: list[Coverage] = field(default_factory=list)
    notes: list[ProgressNote] = field(default_factory=list)
    assessments: list[Assessment] = field(default_factory=list)


@dataclass
class EligibilityResult:
    patient_id: str
    internal_id: int
    name: str
    facility_id: int
    wound_type: Optional[str] = None
    wound_stage: Optional[int] = None
    wound_location: Optional[str] = None
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    drainage_amount: Optional[str] = None
    has_mcb_coverage: bool = False
    icd10_codes: list[str] = field(default_factory=list)
    routing_decision: str = RoutingDecision.REJECT.value
    reason: str = ""
    note_format: str = NoteFormat.UNKNOWN.value
    extraction_source: str = "unknown"
    last_assessment_date: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
