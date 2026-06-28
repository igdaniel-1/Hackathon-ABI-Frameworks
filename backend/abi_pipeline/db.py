from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY,
    facility_id INTEGER NOT NULL,
    patient_id TEXT NOT NULL UNIQUE,
    first_name TEXT,
    last_name TEXT,
    birth_date TEXT,
    gender TEXT,
    primary_payer_code TEXT,
    last_modified_at TEXT,
    is_new_admission INTEGER,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id INTEGER PRIMARY KEY,
    patient_id TEXT NOT NULL,
    icd10_code TEXT,
    icd10_description TEXT,
    clinical_status TEXT,
    onset_date TEXT,
    last_modified_at TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coverage (
    id INTEGER PRIMARY KEY,
    patient_id TEXT NOT NULL,
    payer_name TEXT,
    payer_code TEXT,
    payer_type TEXT,
    effective_from TEXT,
    effective_to TEXT,
    last_modified_at TEXT,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    org_id TEXT,
    pcc_note_id INTEGER,
    note_type TEXT,
    effective_date TEXT,
    note_text TEXT,
    created_by TEXT,
    note_label TEXT,
    sync_version INTEGER,
    is_current INTEGER,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    org_id TEXT,
    pcc_assessment_id INTEGER,
    assessment_type TEXT,
    status TEXT,
    assessment_date TEXT,
    completion_date TEXT,
    template_id INTEGER,
    assessment_type_description TEXT,
    raw_json TEXT,
    sync_version INTEGER,
    is_current INTEGER,
    record_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_status (
    patient_id TEXT PRIMARY KEY,
    internal_id INTEGER NOT NULL UNIQUE,
    has_diagnoses INTEGER NOT NULL DEFAULT 0,
    has_coverage INTEGER NOT NULL DEFAULT 0,
    has_notes INTEGER NOT NULL DEFAULT 0,
    has_assessments INTEGER NOT NULL DEFAULT 0,
    ready_for_processing INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS failed_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    last_error TEXT NOT NULL,
    failed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS final_output (
    patient_id TEXT PRIMARY KEY,
    internal_id INTEGER NOT NULL,
    wound_type TEXT,
    wound_stage TEXT,
    location TEXT,
    length_cm REAL,
    width_cm REAL,
    depth_cm REAL,
    drainage_amount TEXT,
    active_medicare_part_b INTEGER NOT NULL,
    routing_decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    source TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)


def upsert_patients(connection: sqlite3.Connection, patients: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(patients)
    for row in rows:
        connection.execute(
            """
            INSERT INTO patients (
                id, facility_id, patient_id, first_name, last_name, birth_date, gender,
                primary_payer_code, last_modified_at, is_new_admission, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                facility_id=excluded.facility_id,
                patient_id=excluded.patient_id,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                birth_date=excluded.birth_date,
                gender=excluded.gender,
                primary_payer_code=excluded.primary_payer_code,
                last_modified_at=excluded.last_modified_at,
                is_new_admission=excluded.is_new_admission,
                raw_json=excluded.raw_json
            """,
            (
                row.get("id"),
                row.get("facility_id"),
                row.get("patient_id"),
                row.get("first_name"),
                row.get("last_name"),
                row.get("birth_date"),
                row.get("gender"),
                row.get("primary_payer_code"),
                row.get("last_modified_at"),
                int(bool(row.get("is_new_admission"))),
                json.dumps(row),
            ),
        )
        connection.execute(
            """
            INSERT INTO patient_status (patient_id, internal_id)
            VALUES (?, ?)
            ON CONFLICT(patient_id) DO UPDATE SET
                internal_id=excluded.internal_id,
                updated_at=CURRENT_TIMESTAMP
            """,
            (row.get("patient_id"), row.get("id")),
        )
    connection.commit()
    return rows


def replace_child_rows(
    connection: sqlite3.Connection,
    table: str,
    key_column: str,
    key_value: str | int,
    rows: Iterable[dict[str, Any]],
) -> int:
    allowed_tables = {"diagnoses", "coverage", "notes", "assessments"}
    if table not in allowed_tables:
        raise ValueError(f"Unsupported table: {table}")

    items = list(rows)
    connection.execute(f"DELETE FROM {table} WHERE {key_column} = ?", (key_value,))
    for row in items:
        if table == "diagnoses":
            connection.execute(
                """
                INSERT INTO diagnoses
                (id, patient_id, icd10_code, icd10_description, clinical_status, onset_date, last_modified_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("id"),
                    row.get("patient_id"),
                    row.get("icd10_code"),
                    row.get("icd10_description"),
                    row.get("clinical_status"),
                    row.get("onset_date"),
                    row.get("last_modified_at"),
                    json.dumps(row),
                ),
            )
        elif table == "coverage":
            connection.execute(
                """
                INSERT INTO coverage
                (id, patient_id, payer_name, payer_code, payer_type, effective_from, effective_to, last_modified_at, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("id"),
                    row.get("patient_id"),
                    row.get("payer_name"),
                    row.get("payer_code"),
                    row.get("payer_type"),
                    row.get("effective_from"),
                    row.get("effective_to"),
                    row.get("last_modified_at"),
                    json.dumps(row),
                ),
            )
        elif table == "notes":
            connection.execute(
                """
                INSERT INTO notes
                (id, patient_id, org_id, pcc_note_id, note_type, effective_date, note_text, created_by,
                 note_label, sync_version, is_current, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("id"),
                    row.get("patient_id"),
                    row.get("org_id"),
                    row.get("pcc_note_id"),
                    row.get("note_type"),
                    row.get("effective_date"),
                    row.get("note_text"),
                    row.get("created_by"),
                    row.get("note_label"),
                    row.get("sync_version"),
                    int(bool(row.get("is_current"))),
                    json.dumps(row),
                ),
            )
        elif table == "assessments":
            connection.execute(
                """
                INSERT INTO assessments
                (id, patient_id, org_id, pcc_assessment_id, assessment_type, status, assessment_date,
                 completion_date, template_id, assessment_type_description, raw_json, sync_version,
                 is_current, record_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("id"),
                    row.get("patient_id"),
                    row.get("org_id"),
                    row.get("pcc_assessment_id"),
                    row.get("assessment_type"),
                    row.get("status"),
                    row.get("assessment_date"),
                    row.get("completion_date"),
                    row.get("template_id"),
                    row.get("assessment_type_description"),
                    row.get("raw_json"),
                    row.get("sync_version"),
                    int(bool(row.get("is_current"))),
                    json.dumps(row),
                ),
            )
    connection.commit()
    return len(items)


def set_status_flag(connection: sqlite3.Connection, patient_id: str | None, internal_id: int | None, flag: str, value: bool) -> None:
    allowed_flags = {"has_diagnoses", "has_coverage", "has_notes", "has_assessments"}
    if flag not in allowed_flags:
        raise ValueError(f"Unsupported status flag: {flag}")
    if patient_id is None and internal_id is not None:
        row = connection.execute("SELECT patient_id FROM patient_status WHERE internal_id = ?", (internal_id,)).fetchone()
        patient_id = row["patient_id"] if row else None
    if patient_id is None:
        return
    connection.execute(
        f"""
        UPDATE patient_status
        SET {flag} = ?, updated_at = CURRENT_TIMESTAMP
        WHERE patient_id = ?
        """,
        (int(value), patient_id),
    )
    refresh_readiness(connection, patient_id)
    connection.commit()


def refresh_readiness(connection: sqlite3.Connection, patient_id: str | None = None) -> None:
    clause = "WHERE patient_id = ?" if patient_id else ""
    parameters = (patient_id,) if patient_id else ()
    connection.execute(
        f"""
        UPDATE patient_status
        SET ready_for_processing = CASE
            WHEN has_coverage = 1 AND (has_notes = 1 OR has_assessments = 1) THEN 1
            ELSE 0
        END,
        updated_at = CURRENT_TIMESTAMP
        {clause}
        """,
        parameters,
    )


def record_failed_job(connection: sqlite3.Connection, job_type: str, target_id: str, attempts: int, last_error: str) -> None:
    connection.execute(
        """
        INSERT INTO failed_jobs (job_type, target_id, attempts, last_error)
        VALUES (?, ?, ?, ?)
        """,
        (job_type, target_id, attempts, last_error),
    )
    connection.commit()
