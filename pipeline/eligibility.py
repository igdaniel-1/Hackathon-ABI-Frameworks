"""Eligibility engine for the wound care billing pipeline."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from pipeline.models import (
    Coverage,
    EligibilityResult,
    NoteFormat,
    Patient,
    RoutingDecision,
    WoundData,
)

logger = logging.getLogger(__name__)


class EligibilityEngine:

    def has_active_mcb_coverage(self, coverages: list[Coverage]) -> bool:
        today = date.today()
        for coverage in coverages:
            if coverage.payer_code != "MCB":
                continue
            if coverage.effective_to is None:
                return True
            try:
                raw = coverage.effective_to.replace("Z", "+00:00")
                expiry = datetime.fromisoformat(raw).date()
                if expiry >= today:
                    return True
            except (ValueError, TypeError):
                logger.warning(
                    "Could not parse effective_to date '%s' for coverage id=%s",
                    coverage.effective_to,
                    coverage.id,
                )
        return False

    def determine_routing(
        self, patient: Patient, wound_data: WoundData
    ) -> EligibilityResult:
        patient_name = " ".join(
            filter(None, [patient.first_name, patient.last_name])
        ) or "Unknown"

        icd10_codes = [
            d.icd10_code
            for d in patient.diagnoses
            if d.icd10_code and d.clinical_status == "active"
        ]

        has_mcb = self.has_active_mcb_coverage(patient.coverages)

        last_assessment_date: Optional[str] = None
        if patient.assessments:
            dated = [a.assessment_date for a in patient.assessments if a.assessment_date]
            if dated:
                last_assessment_date = max(dated)

        result = EligibilityResult(
            patient_id=patient.patient_id,
            internal_id=patient.id,
            name=patient_name,
            facility_id=patient.facility_id,
            wound_type=wound_data.wound_type,
            wound_stage=wound_data.wound_stage,
            wound_location=wound_data.location,
            length_cm=wound_data.length_cm,
            width_cm=wound_data.width_cm,
            depth_cm=wound_data.depth_cm,
            drainage_amount=wound_data.drainage_amount,
            has_mcb_coverage=has_mcb,
            icd10_codes=icd10_codes,
            note_format=wound_data.note_format,
            extraction_source=wound_data.extraction_source,
            last_assessment_date=last_assessment_date,
        )

        if not has_mcb or not wound_data.has_wound():
            result.routing_decision = RoutingDecision.REJECT.value
            result.reason = self.generate_reason(result, wound_data)
            logger.info(
                "REJECT patient=%s reason=%s", patient.patient_id, result.reason
            )
            return result

        complete_measurements = wound_data.has_complete_measurements()
        drainage_documented = wound_data.drainage_amount is not None
        clean_format = wound_data.note_format in (
            NoteFormat.STRUCTURED.value,
            "assessment",
        )

        auto_accept = (
            complete_measurements
            and drainage_documented
            and not wound_data.needs_review
            and clean_format
        )

        if auto_accept:
            result.routing_decision = RoutingDecision.AUTO_ACCEPT.value
        else:
            result.routing_decision = RoutingDecision.FLAG_FOR_REVIEW.value

        result.reason = self.generate_reason(result, wound_data)
        logger.info(
            "%-15s patient=%s", result.routing_decision.upper(), patient.patient_id
        )
        return result

    def generate_reason(
        self, result: EligibilityResult, wound_data: WoundData
    ) -> str:
        decision = result.routing_decision

        if decision == RoutingDecision.REJECT.value:
            if not result.has_mcb_coverage:
                if result.wound_type is None and not wound_data.has_wound():
                    return (
                        "No active Medicare Part B coverage and no wound data found. "
                        "Patient does not qualify for wound care billing."
                    )
                return (
                    "Patient does not have active Medicare Part B coverage. "
                    "Medicare Part B is required for wound care billing eligibility."
                )
            return (
                "No wound data found in clinical notes or assessments. "
                "Patient does not qualify for wound care billing."
            )

        mcb_line = "Medicare Part B coverage is active."

        if decision == RoutingDecision.AUTO_ACCEPT.value:
            wound_desc = _describe_wound(result)
            measurement_desc = (
                f"({result.length_cm} x {result.width_cm} x {result.depth_cm} cm)"
                if all(
                    v is not None
                    for v in [result.length_cm, result.width_cm, result.depth_cm]
                )
                else "with complete measurements"
            )
            return (
                f"Active {wound_desc} with complete measurements {measurement_desc}. "
                f"{mcb_line} All required billing fields are documented."
            )

        missing_parts: list[str] = []
        if not wound_data.has_complete_measurements():
            missing = []
            if result.length_cm is None:
                missing.append("length")
            if result.width_cm is None:
                missing.append("width")
            if result.depth_cm is None:
                missing.append("depth")
            if missing:
                missing_parts.append(
                    f"wound {' and '.join(missing)} measurement{'s' if len(missing) > 1 else ''} "
                    f"{'are' if len(missing) > 1 else 'is'} missing"
                )

        if wound_data.drainage_amount is None:
            missing_parts.append("drainage is not documented")

        if wound_data.needs_review:
            missing_parts.append("extraction flagged for manual review")

        if wound_data.note_format in (
            NoteFormat.ENVIVE.value,
            NoteFormat.PROSE.value,
            NoteFormat.MULTI_WOUND.value,
        ):
            missing_parts.append(
                f"note format is '{wound_data.note_format}' and may require verification"
            )

        wound_desc = _describe_wound(result)
        if missing_parts:
            issues = "; ".join(missing_parts).capitalize()
            return (
                f"{wound_desc.capitalize()} identified but {issues}. "
                f"{mcb_line} Manual review needed to confirm billing eligibility."
            )

        return (
            f"{wound_desc.capitalize()} identified with incomplete documentation. "
            f"{mcb_line} Manual review needed to confirm billing eligibility."
        )

    def process_all(
        self,
        patients: list[Patient],
        wound_data_map: dict[str, WoundData],
    ) -> list[EligibilityResult]:
        results: list[EligibilityResult] = []
        for patient in patients:
            wound_data = wound_data_map.get(patient.patient_id, WoundData())
            try:
                result = self.determine_routing(patient, wound_data)
                results.append(result)
            except Exception:
                logger.exception(
                    "Unexpected error processing patient=%s", patient.patient_id
                )
        return results


def _describe_wound(result: EligibilityResult) -> str:
    parts: list[str] = []
    if result.wound_stage is not None:
        parts.append(f"Stage {result.wound_stage}")
    if result.wound_type:
        parts.append(result.wound_type)
    if result.wound_location:
        parts.append(f"on {result.wound_location}")
    return " ".join(parts) if parts else "wound"
