"""OpenAI-powered wound data extractor for the wound care billing pipeline."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError

from pipeline.models import Assessment, NoteFormat, ProgressNote, WoundData

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a clinical wound care specialist extracting structured data from wound assessment notes.

Extract the following fields and return them as a JSON object:
- wound_type: string — e.g. "Pressure Ulcer", "Diabetic Foot Ulcer", "Venous Ulcer", "Arterial Ulcer", "Surgical Wound". Normalize abbreviations: PU→"Pressure Ulcer", DFU→"Diabetic Foot Ulcer", VU→"Venous Ulcer".
- wound_stage: integer or null — staging number (1–4, or unstageable). Only for pressure ulcers/injuries. Null for all other wound types.
- location: string or null — anatomical location, e.g. "Sacrum", "Left Heel", "Right Heel". Expand abbreviations: L→Left, R→Right.
- length_cm: number or null — longest dimension in centimeters.
- width_cm: number or null — perpendicular dimension in centimeters.
- depth_cm: number or null — depth dimension in centimeters. If noted as "0" it is 0.0, not null.
- drainage_amount: string or null — normalize to one of: "None", "Scant", "Minimal", "Moderate", "Large", "Copious". Abbreviations: mod→Moderate, min→Minimal, lg→Large.
- note_format: string — classify the note format:
    * "structured" — clearly labeled fields like "Location:", "Width:", "Drainage:" on separate lines or with colons
    * "prose" — abbreviated shorthand run together, e.g. "Meas 4.2x3.1x1.5cm, mod seros drainage. Stage 3 PU L heel."
    * "multi_wound" — describes two or more distinct wounds
    * "envive" — longer narrative paragraph style, e.g. "Patient seen for weekly wound evaluation. The sacral wound continues..."

If the note describes multiple wounds, extract data for the PRIMARY or most clinically significant wound (typically the largest or highest-staged).

Measurement parsing rules:
- "3.2x2.1x0.4" → length=3.2, width=2.1, depth=0.4
- "3.2 cm x 2.1 cm" → length=3.2, width=2.1
- "Meas 4.2x3.1x1.5cm" → length=4.2, width=3.1, depth=1.5

Return ONLY valid JSON with these exact keys. Set missing or ambiguous values to null.

Example output:
{
  "wound_type": "Pressure Ulcer",
  "wound_stage": 2,
  "location": "Sacrum",
  "length_cm": 3.2,
  "width_cm": 2.1,
  "depth_cm": 0.4,
  "drainage_amount": "Moderate",
  "note_format": "structured"
}"""

_REQUIRED_FIELDS = ["wound_type", "location", "length_cm", "width_cm", "depth_cm"]
_MAX_RETRIES = 3
_RETRY_DELAY_SECONDS = 2.0


class WoundExtractor:
    def __init__(self, api_key: str) -> None:
        self._client = OpenAI(api_key=api_key)

    def extract_from_note(self, note: ProgressNote) -> WoundData:
        if not note.note_text or not note.note_text.strip():
            logger.warning("ProgressNote id=%s has no note_text; skipping LLM call", note.id)
            return WoundData(needs_review=True, extraction_source="progress_note")

        raw = self._call_llm(note.note_text)
        if raw is None:
            return WoundData(needs_review=True, extraction_source="progress_note")

        return self._parse_llm_response(raw, source="progress_note")

    def extract_from_assessment(self, assessment: Assessment) -> WoundData:
        data = assessment.parsed_json()
        if not data:
            logger.warning(
                "Assessment id=%s has no parseable raw_json; flagging for review", assessment.id
            )
            return WoundData(
                needs_review=True,
                extraction_source="assessment",
                note_format=NoteFormat.STRUCTURED.value,
            )

        # Flat structure: keys like wound_type, length_cm exist at top level
        if "wound_type" in data or "type" in data:
            return self._parse_flat_assessment(data)

        # Nested structure: sections/questions format from HP Skin & Wound assessments
        # Flatten it into a text block and send to the LLM
        text = self._flatten_nested_assessment(data)
        if text:
            raw = self._call_llm(text)
            if raw is not None:
                result = self._parse_llm_response(raw, source="assessment")
                result.note_format = NoteFormat.STRUCTURED.value
                # Re-evaluate needs_review: assessment data is structured, so only
                # flag if actual fields are missing
                result.needs_review = not result.has_wound() or not result.has_complete_measurements()
                return result

        return WoundData(
            needs_review=True,
            extraction_source="assessment",
            note_format=NoteFormat.STRUCTURED.value,
        )

    def _parse_flat_assessment(self, data: dict) -> WoundData:
        wound_type = data.get("wound_type") or data.get("type")
        raw_stage = data.get("stage") or data.get("wound_stage")
        wound_stage: Optional[int] = None
        if raw_stage is not None:
            try:
                wound_stage = int(raw_stage)
            except (ValueError, TypeError):
                wound_stage = None

        location = data.get("location")

        def _to_float(val: object) -> Optional[float]:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        length_cm = _to_float(data.get("length_cm"))
        width_cm = _to_float(data.get("width_cm"))
        depth_cm = _to_float(data.get("depth_cm"))
        drainage_amount = data.get("drainage_amount") or data.get("drainage_type")

        present = {wound_type, location, length_cm, width_cm, depth_cm}
        needs_review = None in present or not wound_type

        return WoundData(
            wound_type=wound_type,
            wound_stage=wound_stage,
            location=location,
            length_cm=length_cm,
            width_cm=width_cm,
            depth_cm=depth_cm,
            drainage_amount=str(drainage_amount) if drainage_amount is not None else None,
            needs_review=needs_review,
            extraction_source="assessment",
            note_format=NoteFormat.STRUCTURED.value,
        )

    @staticmethod
    def _flatten_nested_assessment(data: dict) -> Optional[str]:
        """Convert nested sections/questions assessment JSON into readable text for the LLM."""
        parts: list[str] = []
        for section in data.get("sections", []):
            section_name = section.get("sectionName", "")
            if section_name:
                parts.append(f"[{section_name}]")
            for q in section.get("questions", []):
                question = q.get("question", "")
                answer = q.get("answer", "")
                if question and answer:
                    parts.append(f"{question}: {answer}")
        return "\n".join(parts) if parts else None

    def extract_for_patient(
        self,
        notes: list[ProgressNote],
        assessments: list[Assessment],
    ) -> WoundData:
        candidates: list[WoundData] = []

        for assessment in assessments:
            try:
                result = self.extract_from_assessment(assessment)
                if result.has_wound():
                    candidates.append(result)
            except Exception:
                logger.exception("Unexpected error extracting assessment id=%s", assessment.id)

        if not candidates:
            for note in notes:
                try:
                    result = self.extract_from_note(note)
                    if result.has_wound():
                        candidates.append(result)
                except Exception:
                    logger.exception("Unexpected error extracting note id=%s", note.id)

        if not candidates:
            logger.info("No wound data found across %d notes and %d assessments", len(notes), len(assessments))
            return WoundData()

        return max(candidates, key=self._completeness_score)

    def _call_llm(self, note_text: str) -> Optional[dict]:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    model="gpt-5.4-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": note_text},
                    ],
                    temperature=0,
                )
                content = response.choices[0].message.content
                return json.loads(content)
            except RateLimitError:
                logger.warning("OpenAI rate limit hit (attempt %d/%d); retrying in %.1fs", attempt, _MAX_RETRIES, _RETRY_DELAY_SECONDS)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_SECONDS * attempt)
                else:
                    logger.error("OpenAI rate limit exceeded after %d attempts", _MAX_RETRIES)
                    return None
            except APITimeoutError:
                logger.warning("OpenAI request timed out (attempt %d/%d); retrying", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_SECONDS)
                else:
                    logger.error("OpenAI request timed out after %d attempts", _MAX_RETRIES)
                    return None
            except APIConnectionError:
                logger.warning("OpenAI connection error (attempt %d/%d); retrying", attempt, _MAX_RETRIES)
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_SECONDS)
                else:
                    logger.error("OpenAI connection error after %d attempts", _MAX_RETRIES)
                    return None
            except json.JSONDecodeError as exc:
                logger.error("Failed to parse LLM JSON response: %s", exc)
                return None
            except Exception:
                logger.exception("Unexpected error calling OpenAI API")
                return None
        return None

    def _parse_llm_response(self, data: dict, source: str) -> WoundData:
        def _to_float(val: object) -> Optional[float]:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        def _to_int(val: object) -> Optional[int]:
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        wound_type = data.get("wound_type") or None
        wound_stage = _to_int(data.get("wound_stage"))
        location = data.get("location") or None
        length_cm = _to_float(data.get("length_cm"))
        width_cm = _to_float(data.get("width_cm"))
        depth_cm = _to_float(data.get("depth_cm"))
        drainage_amount = data.get("drainage_amount") or None

        raw_format = (data.get("note_format") or "").lower()
        format_map = {
            "structured": NoteFormat.STRUCTURED,
            "prose": NoteFormat.PROSE,
            "multi_wound": NoteFormat.MULTI_WOUND,
            "envive": NoteFormat.ENVIVE,
        }
        note_format = format_map.get(raw_format, NoteFormat.UNKNOWN)

        missing = any(
            v is None
            for v in [wound_type, location, length_cm, width_cm, depth_cm]
        )
        needs_review = missing or note_format == NoteFormat.UNKNOWN

        return WoundData(
            wound_type=wound_type,
            wound_stage=wound_stage,
            location=location,
            length_cm=length_cm,
            width_cm=width_cm,
            depth_cm=depth_cm,
            drainage_amount=drainage_amount,
            needs_review=needs_review,
            extraction_source=source,
            note_format=note_format.value,
        )

    @staticmethod
    def _completeness_score(wd: WoundData) -> int:
        score = 0
        if wd.wound_type:
            score += 2
        if wd.location:
            score += 1
        if wd.length_cm is not None:
            score += 1
        if wd.width_cm is not None:
            score += 1
        if wd.depth_cm is not None:
            score += 1
        if wd.drainage_amount:
            score += 1
        if wd.wound_stage is not None:
            score += 1
        if wd.extraction_source == "assessment":
            score += 2
        if not wd.needs_review:
            score += 1
        return score
