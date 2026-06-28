"""Normalize one patient's data, extract wound evidence, and decide eligibility.

This module intentionally does not fetch API data. It operates on patient-level
records after another component has already retrieved demographics, diagnoses,
coverage, progress notes, and structured assessments.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
import json
import re
from typing import Any


ACCEPT = "Accept"
REJECT = "Reject"

WOUND_KEYWORDS = {
    "pressure ulcer": "pressure_ulcer",
    "pressure injury": "pressure_ulcer",
    "diabetic foot ulcer": "diabetic_foot_ulcer",
    "dfu": "diabetic_foot_ulcer",
    "venous stasis ulcer": "venous_stasis_ulcer",
    "venous ulcer": "venous_stasis_ulcer",
    "arterial ulcer": "arterial_ulcer",
    "surgical site infection": "surgical_site_infection",
    "abscess": "abscess",
    "burn": "burn",
}

WOUND_DIAGNOSIS_PREFIXES = (
    "L89",  # pressure ulcer
    "L97",  # non-pressure chronic ulcer
    "E08.621",
    "E09.621",
    "E10.621",
    "E11.621",
    "E13.621",  # diabetic foot ulcer
    "I83.0",
    "I83.2",
    "I87.3",  # venous ulcers / stasis
)

LOCATION_PATTERN = re.compile(
    r"(?:location|loc|site)\s*[:=-]\s*([A-Za-z][A-Za-z\s/-]{1,60})(?=\n|;|,|\.|$)",
    re.IGNORECASE,
)
STAGE_PATTERN = re.compile(r"\bstage\s*(?:[:=-]\s*)?(2|3|4|II|III|IV|unstageable)\b", re.IGNORECASE)
DIMENSION_PATTERN = re.compile(
    r"(?:(?:meas(?:urement)?s?)\s*[:=-]?\s*)?"
    r"(\d+(?:\.\d+)?)\s*(?:cm)?\s*[xX]\s*"
    r"(\d+(?:\.\d+)?)\s*(?:cm)?\s*[xX]\s*"
    r"(\d+(?:\.\d+)?)\s*cm?",
    re.IGNORECASE,
)
LABELED_MEASUREMENT_PATTERNS = {
    "length_cm": re.compile(r"\blength\s*[:=-]\s*(\d+(?:\.\d+)?)\s*cm\b", re.IGNORECASE),
    "width_cm": re.compile(r"\bwidth\s*[:=-]\s*(\d+(?:\.\d+)?)\s*cm\b", re.IGNORECASE),
    "depth_cm": re.compile(r"\bdepth\s*[:=-]\s*(\d+(?:\.\d+)?)\s*cm\b", re.IGNORECASE),
}
DRAINAGE_PATTERN = re.compile(r"\b(none|light|scant|small|moderate|heavy|large|copious)\b", re.IGNORECASE)


@dataclass
class WoundEvidence:
    wound_type: str | None = None
    stage: str | None = None
    location: str | None = None
    length_cm: float | None = None
    width_cm: float | None = None
    depth_cm: float | None = None
    drainage_amount: str | None = None
    source: str | None = None
    source_date: str | None = None
    evidence_text: str | None = None

    def completeness_score(self) -> int:
        fields = (
            self.wound_type,
            self.location,
            self.length_cm,
            self.width_cm,
            self.depth_cm,
            self.drainage_amount,
        )
        score = sum(value is not None and value != "" for value in fields)
        if self.wound_type == "pressure_ulcer" and self.stage:
            score += 1
        return score


def evaluate_patient(payload: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Return an Accept/Reject eligibility decision for one already-fetched patient.

    Expected payload keys:
      patient: demographics / identity dict
      diagnoses: list of ICD-10 diagnosis dicts
      coverage: list of insurance coverage dicts
      notes: list of progress-note dicts
      assessments: list of structured assessment dicts
    """

    today = today or date.today()
    normalized = normalize_payload(payload)
    coverage_evidence = active_medicare_part_b_coverage(normalized["coverage"], today)
    medicare_b = coverage_evidence is not None
    diagnosis_evidence = find_wound_diagnoses(normalized["diagnoses"])
    wound_evidence = select_best_wound_evidence(normalized)

    missing = missing_required_fields(wound_evidence)
    reasons: list[str] = []

    if not medicare_b:
        reasons.append("No active Medicare Part B coverage was found.")
    if not wound_evidence:
        reasons.append("No wound evidence was found in assessments, notes, or active diagnoses.")
    elif missing:
        reasons.append("Wound evidence is incomplete: missing " + ", ".join(missing) + ".")
    if wound_evidence and not diagnosis_evidence:
        reasons.append("Wound was documented clinically, but no active wound ICD-10 diagnosis was found.")

    decision = ACCEPT if medicare_b and wound_evidence and not missing else REJECT
    routing_decision = determine_routing_decision(medicare_b, wound_evidence, missing)
    if decision == ACCEPT:
        reasons.append("Active wound, measurements, drainage, and Medicare Part B coverage are documented.")

    patient = normalized["patient"]
    wound = wound_evidence or WoundEvidence()
    return {
        "patient_id": patient.get("patient_id"),
        "internal_id": patient.get("id"),
        "patient_name": format_name(patient),
        "facility_id": patient.get("facility_id"),
        "decision": decision,
        "active_medicare_part_b": medicare_b,
        "coverage_source": format_coverage_source(coverage_evidence),
        "active_wound_found": wound_evidence is not None,
        "wound_type": wound.wound_type,
        "stage": wound.stage,
        "location": wound.location,
        "length_cm": wound.length_cm,
        "width_cm": wound.width_cm,
        "depth_cm": wound.depth_cm,
        "drainage_amount": wound.drainage_amount,
        "evidence_source": wound.source,
        "evidence_text": wound.evidence_text,
        "missing_fields": missing,
        "reason": " ".join(reasons),
        "routing_decision": routing_decision,
    }


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "patient": dict(payload.get("patient") or payload.get("demographics") or {}),
        "diagnoses": list(payload.get("diagnoses") or []),
        "coverage": list(payload.get("coverage") or payload.get("insurance") or []),
        "notes": list(payload.get("notes") or payload.get("progress_notes") or []),
        "assessments": list(payload.get("assessments") or payload.get("structured_assessments") or []),
    }


def has_active_medicare_part_b(coverage: list[dict[str, Any]], today: date) -> bool:
    return active_medicare_part_b_coverage(coverage, today) is not None


def active_medicare_part_b_coverage(coverage: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    for item in coverage:
        payer_code = str(item.get("payer_code") or "").upper()
        payer_type = str(item.get("payer_type") or "").lower()
        payer_name = str(item.get("payer_name") or "").lower()
        is_medicare_b = payer_code == "MCB" or "medicare b" in payer_type or "medicare part b" in payer_name
        if is_medicare_b and is_effective(item.get("effective_from"), item.get("effective_to"), today):
            return item
    return None


def is_effective(start: Any, end: Any, today: date) -> bool:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if start_date and start_date > today:
        return False
    if end_date and end_date < today:
        return False
    return True


def find_wound_diagnoses(diagnoses: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    matches = []
    for diagnosis in diagnoses:
        status = str(diagnosis.get("clinical_status") or "").lower()
        code = str(diagnosis.get("icd10_code") or "").upper()
        description = str(diagnosis.get("icd10_description") or "")
        if status not in {"active", ""}:
            continue
        if code.startswith(WOUND_DIAGNOSIS_PREFIXES) or contains_wound_keyword(description):
            matches.append(
                {
                    "icd10_code": code or None,
                    "icd10_description": description or None,
                    "onset_date": diagnosis.get("onset_date"),
                }
            )
    return matches


def select_best_wound_evidence(normalized: dict[str, Any]) -> WoundEvidence | None:
    candidates: list[WoundEvidence] = []

    for assessment in normalized["assessments"]:
        evidence = evidence_from_assessment(assessment)
        if evidence:
            candidates.append(evidence)

    for note in normalized["notes"]:
        evidence = evidence_from_note(note)
        if evidence:
            candidates.append(evidence)

    for diagnosis in normalized["diagnoses"]:
        evidence = evidence_from_diagnosis(diagnosis)
        if evidence:
            candidates.append(evidence)

    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (item.completeness_score(), parse_date(item.source_date) or date.min),
        reverse=True,
    )[0]


def evidence_from_assessment(assessment: dict[str, Any]) -> WoundEvidence | None:
    if str(assessment.get("status") or "").lower() not in {"", "complete"}:
        return None
    raw = assessment.get("raw_json")
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
    elif isinstance(raw, dict):
        data = raw
    else:
        return None

    wound_type = normalize_wound_type(data.get("wound_type") or data.get("type"))
    if not wound_type and not any(data.get(field) is not None for field in ("length_cm", "width_cm", "depth_cm")):
        return None

    return WoundEvidence(
        wound_type=wound_type,
        stage=normalize_stage(data.get("stage")),
        location=clean_text(data.get("location")),
        length_cm=parse_float(data.get("length_cm")),
        width_cm=parse_float(data.get("width_cm")),
        depth_cm=parse_float(data.get("depth_cm")),
        drainage_amount=normalize_drainage(data.get("drainage_amount")),
        source="assessment",
        source_date=assessment.get("assessment_date") or assessment.get("completion_date"),
        evidence_text="Structured wound assessment",
    )


def evidence_from_note(note: dict[str, Any]) -> WoundEvidence | None:
    text = str(note.get("note_text") or "")
    if not contains_wound_keyword(text) and not DIMENSION_PATTERN.search(text):
        return None

    wound_type = normalize_wound_type(text)
    location = extract_location(text)
    length_cm, width_cm, depth_cm = extract_measurements(text)

    return WoundEvidence(
        wound_type=wound_type,
        stage=extract_stage(text),
        location=location,
        length_cm=length_cm,
        width_cm=width_cm,
        depth_cm=depth_cm,
        drainage_amount=extract_drainage(text),
        source="progress_note",
        source_date=note.get("effective_date"),
        evidence_text=compact_evidence_text(text),
    )


def evidence_from_diagnosis(diagnosis: dict[str, Any]) -> WoundEvidence | None:
    if not find_wound_diagnoses([diagnosis]):
        return None
    description = str(diagnosis.get("icd10_description") or "")
    return WoundEvidence(
        wound_type=normalize_wound_type(description),
        stage=extract_stage(description),
        source="diagnosis",
        source_date=diagnosis.get("onset_date"),
        evidence_text=description or diagnosis.get("icd10_code"),
    )


def missing_required_fields(evidence: WoundEvidence | None) -> list[str]:
    if not evidence:
        return ["wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount"]
    missing = []
    for field in ("wound_type", "length_cm", "width_cm", "depth_cm", "drainage_amount"):
        if getattr(evidence, field) in (None, ""):
            missing.append(field)
    return missing


def determine_routing_decision(
    medicare_b: bool,
    evidence: WoundEvidence | None,
    missing: list[str],
) -> str:
    if medicare_b and evidence and not missing:
        return "auto_accept"
    if medicare_b and evidence and missing:
        return "flag_for_review"
    return "reject"


def normalize_wound_type(value: Any) -> str | None:
    text = str(value or "").replace("_", " ").lower()
    for label, normalized in WOUND_KEYWORDS.items():
        if label in text:
            return normalized
    return None


def contains_wound_keyword(text: str) -> bool:
    lowered = text.lower().replace("_", " ")
    return any(label in lowered for label in WOUND_KEYWORDS)


def extract_location(text: str) -> str | None:
    match = LOCATION_PATTERN.search(text)
    if match:
        return clean_text(match.group(1))
    common_locations = ("sacrum", "coccyx", "heel", "ankle", "foot", "toe", "buttock", "hip", "leg")
    lowered = text.lower()
    for location in common_locations:
        if location in lowered:
            return location.title()
    return None


def extract_stage(text: str) -> str | None:
    match = STAGE_PATTERN.search(text)
    if not match:
        return None
    return normalize_stage(match.group(1))


def normalize_stage(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    roman = {"ii": "2", "iii": "3", "iv": "4"}
    return roman.get(text, text)


def extract_measurements(text: str) -> tuple[float | None, float | None, float | None]:
    labeled = {
        field: parse_float(pattern.search(text).group(1)) if pattern.search(text) else None
        for field, pattern in LABELED_MEASUREMENT_PATTERNS.items()
    }
    if all(value is not None for value in labeled.values()):
        return labeled["length_cm"], labeled["width_cm"], labeled["depth_cm"]

    match = DIMENSION_PATTERN.search(text)
    if match:
        return parse_float(match.group(1)), parse_float(match.group(2)), parse_float(match.group(3))
    return labeled["length_cm"], labeled["width_cm"], labeled["depth_cm"]


def extract_drainage(text: str) -> str | None:
    drainage_index = text.lower().find("drain")
    searchable = text[drainage_index : drainage_index + 90] if drainage_index >= 0 else text
    match = DRAINAGE_PATTERN.search(searchable)
    if not match:
        return None
    return normalize_drainage(match.group(1))


def normalize_drainage(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"scant", "small"}:
        return "light"
    if text in {"large", "copious"}:
        return "heavy"
    if text in {"none", "light", "moderate", "heavy"}:
        return text
    return None


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip(" -:;,.")
    return text or None


def compact_evidence_text(text: str, max_length: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def format_name(patient: dict[str, Any]) -> str | None:
    first = clean_text(patient.get("first_name"))
    last = clean_text(patient.get("last_name"))
    name = " ".join(part for part in (first, last) if part)
    return name or None


def format_coverage_source(coverage: dict[str, Any] | None) -> str | None:
    if not coverage:
        return None
    payer_name = clean_text(coverage.get("payer_name"))
    payer_code = clean_text(coverage.get("payer_code"))
    payer_type = clean_text(coverage.get("payer_type"))
    effective_from = clean_text(coverage.get("effective_from"))
    parts = [part for part in (payer_name, payer_code, payer_type) if part]
    label = " / ".join(parts) if parts else "Medicare Part B coverage"
    return f"{label}; effective_from={effective_from}" if effective_from else label
