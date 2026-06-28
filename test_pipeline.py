"""Quick smoke test for the pipeline ingestion and extraction layers."""

import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test")


def test_ingestion():
    from pipeline.ingestion import PccClient

    client = PccClient()

    logger.info("--- Health check ---")
    health = client.health()
    logger.info("Health: %s", health)

    logger.info("--- Fetching patients from facility 101 ---")
    patients = client.get_patients(101)
    logger.info("Got %d patients from facility 101", len(patients))
    if patients:
        p = patients[0]
        logger.info("Sample patient: id=%d, patient_id=%s, name=%s %s, payer=%s",
                     p.id, p.patient_id, p.first_name, p.last_name, p.primary_payer_code)

        logger.info("--- Fetching diagnoses for %s ---", p.patient_id)
        diag = client.get_diagnoses(p.patient_id)
        logger.info("Got %d diagnoses", len(diag))
        for d in diag[:2]:
            logger.info("  %s: %s (%s)", d.icd10_code, d.icd10_description, d.clinical_status)

        logger.info("--- Fetching coverage for %s ---", p.patient_id)
        cov = client.get_coverage(p.patient_id)
        logger.info("Got %d coverage records", len(cov))
        for c in cov:
            logger.info("  %s (%s) effective %s -> %s", c.payer_name, c.payer_code, c.effective_from, c.effective_to)

        logger.info("--- Fetching notes for internal id=%d ---", p.id)
        notes = client.get_notes(p.id)
        logger.info("Got %d notes", len(notes))
        if notes:
            n = notes[0]
            logger.info("  Note type=%s, date=%s, text preview: %s",
                         n.note_type, n.effective_date, (n.note_text or "")[:200])

        logger.info("--- Fetching assessments for internal id=%d ---", p.id)
        assessments = client.get_assessments(p.id)
        logger.info("Got %d assessments", len(assessments))
        if assessments:
            a = assessments[0]
            logger.info("  Assessment type=%s, date=%s", a.assessment_type, a.assessment_date)
            logger.info("  raw_json: %s", a.raw_json[:200] if a.raw_json else "None")

    return patients


def test_extraction(notes, assessments):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set - skipping extraction test")
        return None

    from pipeline.extractor import WoundExtractor
    extractor = WoundExtractor(api_key=api_key)

    logger.info("--- Testing extraction ---")
    wound_data = extractor.extract_for_patient(notes, assessments)
    logger.info("Wound data: type=%s, stage=%s, location=%s",
                 wound_data.wound_type, wound_data.wound_stage, wound_data.location)
    logger.info("  Measurements: %.1f x %.1f x %.1f cm",
                 wound_data.length_cm or 0, wound_data.width_cm or 0, wound_data.depth_cm or 0)
    logger.info("  Drainage: %s, needs_review: %s, source: %s, format: %s",
                 wound_data.drainage_amount, wound_data.needs_review,
                 wound_data.extraction_source, wound_data.note_format)
    return wound_data


def test_eligibility(patient, wound_data):
    from pipeline.eligibility import EligibilityEngine
    engine = EligibilityEngine()

    logger.info("--- Testing eligibility ---")
    result = engine.determine_routing(patient, wound_data)
    logger.info("Result for %s: %s", result.patient_id, result.routing_decision)
    logger.info("  Reason: %s", result.reason)
    logger.info("  MCB: %s, ICD10: %s", result.has_mcb_coverage, result.icd10_codes)
    return result


if __name__ == "__main__":
    logger.info("=== Starting pipeline smoke test ===")

    patients = test_ingestion()
    if not patients:
        logger.error("No patients returned - aborting")
        sys.exit(1)

    p = patients[0]
    from pipeline.ingestion import PccClient
    client = PccClient()
    p = client.enrich_patient(p)

    wd = test_extraction(p.notes, p.assessments)

    if wd is None:
        from pipeline.models import WoundData
        wd = WoundData()

    test_eligibility(p, wd)

    logger.info("=== Smoke test complete ===")
