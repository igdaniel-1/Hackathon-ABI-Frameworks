from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any


WOUND_TYPES = {
    "pressure": "pressure_ulcer",
    "diabetic": "diabetic_foot_ulcer",
    "venous": "venous_stasis_ulcer",
    "arterial": "arterial_ulcer",
    "surgical": "surgical_site_infection",
    "abscess": "abscess",
    "burn": "burn",
}

DRAINAGE_AMOUNTS = ("none", "light", "moderate", "heavy")


@dataclass
class WoundExtraction:
    wound_type: str | None = None
    wound_stage: str | None = None
    location: str | None = None
    length_cm: float | None = None
    width_cm: float | None = None
    depth_cm: float | None = None
    drainage_amount: str | None = None
    source: str | None = None

    @property
    def complete(self) -> bool:
        return bool(
            self.wound_type
            and self.location
            and self.length_cm is not None
            and self.width_cm is not None
            and self.depth_cm is not None
            and self.drainage_amount
        )


def normalize_drainage(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    for amount in DRAINAGE_AMOUNTS:
        if amount in lowered:
            return amount
    if "scant" in lowered or "minimal" in lowered or "small" in lowered:
        return "light"
    if "copious" in lowered or "large" in lowered:
        return "heavy"
    return None


def normalize_wound_type(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower().replace("-", " ")
    for needle, normalized in WOUND_TYPES.items():
        if needle in lowered:
            return normalized
    return None


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_from_assessment(raw_json: str | None) -> WoundExtraction | None:
    if not raw_json:
        return None
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if "sections" in data:
        answers = {}
        narrative = None
        for section in data.get("sections", []):
            for item in section.get("questions", []):
                question = str(item.get("question", "")).strip().lower()
                answer = item.get("answer")
                answers[question] = answer
                if "narrative" in question and answer:
                    narrative = str(answer)
        extraction = WoundExtraction(
            wound_type=normalize_wound_type(answers.get("wound type") or narrative),
            wound_stage=_stage_or_none(answers.get("stage")),
            location=answers.get("location"),
            length_cm=parse_float(answers.get("length (cm)")),
            width_cm=parse_float(answers.get("width (cm)")),
            depth_cm=parse_float(answers.get("depth (cm)")),
            drainage_amount=normalize_drainage(answers.get("drainage amount") or answers.get("drainage type") or narrative),
            source="assessment",
        )
        if narrative:
            narrative_extraction = extract_from_note(narrative)
            extraction.location = extraction.location or narrative_extraction.location
            extraction.length_cm = extraction.length_cm if extraction.length_cm is not None else narrative_extraction.length_cm
            extraction.width_cm = extraction.width_cm if extraction.width_cm is not None else narrative_extraction.width_cm
            extraction.depth_cm = extraction.depth_cm if extraction.depth_cm is not None else narrative_extraction.depth_cm
        return extraction
    return WoundExtraction(
        wound_type=normalize_wound_type(data.get("wound_type")) or data.get("wound_type"),
        wound_stage=_stage_or_none(data.get("stage")),
        location=data.get("location"),
        length_cm=parse_float(data.get("length_cm")),
        width_cm=parse_float(data.get("width_cm")),
        depth_cm=parse_float(data.get("depth_cm")),
        drainage_amount=normalize_drainage(data.get("drainage_amount") or data.get("drainage_type")),
        source="assessment",
    )


def extract_from_note(text: str | None) -> WoundExtraction | None:
    if not text:
        return None
    extraction = WoundExtraction(source="note")
    extraction.location = _first_group(text, r"Location:\s*([^\n\r]+)") or _first_group(
        text, r"(?:on|at)\s+(sacrum|heel|coccyx|buttock|foot|ankle|leg|toe|hip)", re.I
    )
    wound_line = _first_group(text, r"Wound Type:\s*([^\n\r]+)")
    extraction.wound_type = normalize_wound_type(wound_line or text)
    extraction.wound_stage = _first_group(text, r"Stage\s*[:\-]?\s*(\d|[IVX]+|unstageable)", re.I)

    labeled = re.search(
        r"Length:\s*(\d+(?:\.\d+)?)\s*cm\s+Width:\s*(\d+(?:\.\d+)?)\s*cm\s+Depth:\s*(\d+(?:\.\d+)?)\s*cm",
        text,
        re.I,
    )
    compact = re.search(r"(?:Meas(?:ures|urement)?\.?\s*)?(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*cm", text, re.I)
    match = labeled or compact
    if match:
        extraction.length_cm = parse_float(match.group(1))
        extraction.width_cm = parse_float(match.group(2))
        extraction.depth_cm = parse_float(match.group(3))

    drainage_line = _first_group(text, r"Drainage:\s*([^\n\r]+)") or _first_group(
        text, r"(none|light|moderate|heavy|scant|minimal|small|copious|large)\s+drainage", re.I
    )
    extraction.drainage_amount = normalize_drainage(drainage_line)
    return extraction


def _first_group(text: str, pattern: str, flags: int = re.I) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else None


def _stage_or_none(value: Any) -> str | None:
    if value in (None, "", "N/A"):
        return None
    text = str(value).strip()
    match = re.search(r"(\d|[IVX]+|unstageable)", text, re.I)
    return match.group(1) if match else text


def has_active_medicare_part_b(connection: sqlite3.Connection, patient_id: str) -> bool:
    rows = connection.execute(
        """
        SELECT payer_code, payer_type, effective_to
        FROM coverage
        WHERE patient_id = ?
        """,
        (patient_id,),
    ).fetchall()
    for row in rows:
        is_part_b = row["payer_code"] == "MCB" or row["payer_type"] == "Medicare B"
        if is_part_b and not row["effective_to"]:
            return True
    return False


def best_extraction(connection: sqlite3.Connection, internal_id: int) -> WoundExtraction | None:
    assessments = connection.execute(
        "SELECT raw_json FROM assessments WHERE patient_id = ? ORDER BY assessment_date DESC, id DESC",
        (internal_id,),
    ).fetchall()
    for row in assessments:
        extraction = extract_from_assessment(row["raw_json"])
        if extraction and extraction.complete:
            return extraction

    notes = connection.execute(
        "SELECT note_text FROM notes WHERE patient_id = ? ORDER BY effective_date DESC, id DESC",
        (internal_id,),
    ).fetchall()
    best_partial: WoundExtraction | None = None
    for row in notes:
        extraction = extract_from_note(row["note_text"])
        if extraction and extraction.complete:
            return extraction
        if extraction and not best_partial:
            best_partial = extraction
    return best_partial


def refresh_final_output(connection: sqlite3.Connection) -> int:
    patients = connection.execute(
        """
        SELECT patient_id, internal_id
        FROM patient_status
        WHERE ready_for_processing = 1
        """
    ).fetchall()
    written = 0
    for patient in patients:
        patient_id = patient["patient_id"]
        internal_id = patient["internal_id"]
        extraction = best_extraction(connection, internal_id) or WoundExtraction()
        active_part_b = has_active_medicare_part_b(connection, patient_id)
        if not active_part_b:
            decision = "reject"
            reason = "Patient does not have active Medicare Part B coverage."
        elif extraction.complete:
            decision = "auto_accept"
            reason = "Active Medicare Part B coverage and complete wound documentation are present."
        elif extraction.wound_type or extraction.location or extraction.length_cm is not None:
            decision = "flag_for_review"
            reason = "Active Medicare Part B coverage is present, but wound documentation is incomplete or ambiguous."
        else:
            decision = "reject"
            reason = "No reliable wound documentation was found in notes or assessments."

        connection.execute(
            """
            INSERT INTO final_output (
                patient_id, internal_id, wound_type, wound_stage, location, length_cm, width_cm,
                depth_cm, drainage_amount, active_medicare_part_b, routing_decision, reason, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(patient_id) DO UPDATE SET
                wound_type=excluded.wound_type,
                wound_stage=excluded.wound_stage,
                location=excluded.location,
                length_cm=excluded.length_cm,
                width_cm=excluded.width_cm,
                depth_cm=excluded.depth_cm,
                drainage_amount=excluded.drainage_amount,
                active_medicare_part_b=excluded.active_medicare_part_b,
                routing_decision=excluded.routing_decision,
                reason=excluded.reason,
                source=excluded.source,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                patient_id,
                internal_id,
                extraction.wound_type,
                extraction.wound_stage,
                extraction.location,
                extraction.length_cm,
                extraction.width_cm,
                extraction.depth_cm,
                extraction.drainage_amount,
                int(active_part_b),
                decision,
                reason,
                extraction.source,
            ),
        )
        written += 1
    connection.commit()
    return written
