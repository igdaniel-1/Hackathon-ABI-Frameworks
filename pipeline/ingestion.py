"""PCC API client for the wound care billing pipeline."""

from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import Callable, TypeVar

import requests

from pipeline.models import Assessment, Coverage, Diagnosis, Patient, ProgressNote

logger = logging.getLogger(__name__)

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"
FACILITY_IDS = [101, 102, 103]
MAX_RETRIES = 5

F = TypeVar("F", bound=Callable)


def _with_retry(func: F) -> F:
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except _RateLimitError as exc:
                last_exc = exc
                retry_after = exc.retry_after
                # Exponential backoff with full jitter on top of the server-mandated wait.
                backoff = (2 ** attempt) + random.uniform(0, 1)
                wait = retry_after + backoff
                logger.warning(
                    "429 on attempt %d/%d — waiting %.2fs (Retry-After=%ds + backoff=%.2fs)",
                    attempt + 1,
                    MAX_RETRIES,
                    wait,
                    retry_after,
                    backoff,
                )
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    return wrapper  # type: ignore[return-value]


class _RateLimitError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Rate limited; Retry-After={retry_after}")
        self.retry_after = retry_after


class PccClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._session = requests.Session()
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"
        self._session.headers["Accept"] = "application/json"

    def _get(self, path: str, params: dict | None = None) -> list | dict:
        url = f"{BASE_URL}{path}"
        logger.debug("GET %s params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            try:
                retry_after = int(resp.headers.get("Retry-After", 1))
                retry_after = max(1, min(retry_after, 5))
            except (ValueError, TypeError):
                retry_after = 1
            raise _RateLimitError(retry_after)
        resp.raise_for_status()
        return resp.json()

    @_with_retry
    def health(self) -> dict:
        return self._get("/health")  # type: ignore[return-value]

    @_with_retry
    def get_patients(self, facility_id: int, since: str | None = None) -> list[Patient]:
        params: dict = {"facility_id": facility_id}
        if since is not None:
            params["since"] = since
        data = self._get("/pcc/patients", params=params)
        return [_parse_patient(r) for r in data]  # type: ignore[union-attr]

    @_with_retry
    def get_diagnoses(self, patient_id: str) -> list[Diagnosis]:
        data = self._get("/pcc/diagnoses", params={"patient_id": patient_id})
        return [_parse_diagnosis(r) for r in data]  # type: ignore[union-attr]

    @_with_retry
    def get_coverage(self, patient_id: str) -> list[Coverage]:
        data = self._get("/pcc/coverage", params={"patient_id": patient_id})
        return [_parse_coverage(r) for r in data]  # type: ignore[union-attr]

    @_with_retry
    def get_notes(self, patient_id: int, since: str | None = None) -> list[ProgressNote]:
        params: dict = {"patient_id": patient_id}
        if since is not None:
            params["since"] = since
        data = self._get("/pcc/notes", params=params)
        return [_parse_note(r) for r in data]  # type: ignore[union-attr]

    @_with_retry
    def get_assessments(self, patient_id: int, since: str | None = None) -> list[Assessment]:
        params: dict = {"patient_id": patient_id}
        if since is not None:
            params["since"] = since
        data = self._get("/pcc/assessments", params=params)
        return [_parse_assessment(r) for r in data]  # type: ignore[union-attr]

    def fetch_all_patients(self, since: str | None = None) -> list[Patient]:
        patients: list[Patient] = []
        for fid in FACILITY_IDS:
            logger.info("Fetching patients for facility %d", fid)
            batch = self.get_patients(fid, since=since)
            logger.info("Got %d patients from facility %d", len(batch), fid)
            patients.extend(batch)
        return patients

    def enrich_patient(self, patient: Patient) -> Patient:
        logger.debug("Enriching patient %s (id=%d)", patient.patient_id, patient.id)
        patient.diagnoses = self.get_diagnoses(patient.patient_id)
        patient.coverages = self.get_coverage(patient.patient_id)
        patient.notes = self.get_notes(patient.id)
        patient.assessments = self.get_assessments(patient.id)
        return patient

    def fetch_and_enrich_all(self, since: str | None = None) -> list[Patient]:
        patients = self.fetch_all_patients(since=since)
        logger.info("Enriching %d patients with max_workers=5", len(patients))
        enriched: list[Patient] = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(self.enrich_patient, p): p for p in patients}
            for future in as_completed(futures):
                patient = futures[future]
                try:
                    enriched.append(future.result())
                except Exception:
                    logger.exception(
                        "Failed to enrich patient %s (id=%d)", patient.patient_id, patient.id
                    )
        return enriched


# ---------------------------------------------------------------------------
# Parsers — pull only the keys each dataclass actually declares to avoid
# unexpected-keyword-argument errors when the API adds new fields.
# ---------------------------------------------------------------------------

def _parse_patient(r: dict) -> Patient:
    return Patient(
        id=r["id"],
        facility_id=r["facility_id"],
        patient_id=r["patient_id"],
        first_name=r.get("first_name"),
        last_name=r.get("last_name"),
        birth_date=r.get("birth_date"),
        gender=r.get("gender"),
        primary_payer_code=r.get("primary_payer_code"),
        last_modified_at=r.get("last_modified_at"),
        is_new_admission=r.get("is_new_admission", False),
    )


def _parse_diagnosis(r: dict) -> Diagnosis:
    return Diagnosis(
        id=r["id"],
        patient_id=r["patient_id"],
        icd10_code=r.get("icd10_code"),
        icd10_description=r.get("icd10_description"),
        clinical_status=r.get("clinical_status"),
        onset_date=r.get("onset_date"),
        last_modified_at=r.get("last_modified_at"),
    )


def _parse_coverage(r: dict) -> Coverage:
    return Coverage(
        id=r["id"],
        patient_id=r["patient_id"],
        payer_name=r.get("payer_name"),
        payer_code=r.get("payer_code"),
        payer_type=r.get("payer_type"),
        effective_from=r.get("effective_from"),
        effective_to=r.get("effective_to"),
        last_modified_at=r.get("last_modified_at"),
    )


def _parse_note(r: dict) -> ProgressNote:
    return ProgressNote(
        id=r["id"],
        patient_id=r["patient_id"],
        org_id=r.get("org_id", ""),
        pcc_note_id=r.get("pcc_note_id"),
        note_type=r.get("note_type"),
        effective_date=r.get("effective_date"),
        note_text=r.get("note_text"),
        created_by=r.get("created_by"),
        note_label=r.get("note_label"),
        sync_version=r.get("sync_version", 1),
        is_current=r.get("is_current", True),
    )


def _parse_assessment(r: dict) -> Assessment:
    return Assessment(
        id=r["id"],
        patient_id=r["patient_id"],
        org_id=r.get("org_id", ""),
        pcc_assessment_id=r.get("pcc_assessment_id"),
        assessment_type=r.get("assessment_type"),
        status=r.get("status"),
        assessment_date=r.get("assessment_date"),
        completion_date=r.get("completion_date"),
        template_id=r.get("template_id"),
        assessment_type_description=r.get("assessment_type_description"),
        raw_json=r.get("raw_json"),
        sync_version=r.get("sync_version", 1),
        is_current=r.get("is_current", True),
    )
