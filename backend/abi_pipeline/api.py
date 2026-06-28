from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query

from .config import settings
from .db import connect, init_db

app = FastAPI(title="ABI Frameworks Backend", version="0.1.0")


def db_path() -> Path:
    init_db(settings.db_path)
    return settings.db_path


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/patients/ready")
def ready_patients(limit: int = Query(100, ge=1, le=1000)) -> list[dict]:
    with connect(db_path()) as connection:
        rows = connection.execute(
            """
            SELECT ps.*, p.first_name, p.last_name, p.facility_id
            FROM patient_status ps
            JOIN patients p ON p.patient_id = ps.patient_id
            WHERE ps.ready_for_processing = 1
            ORDER BY ps.patient_id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/output")
def output(
    decision: str | None = Query(None, pattern="^(auto_accept|flag_for_review|reject)$"),
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict]:
    where = "WHERE routing_decision = ?" if decision else ""
    params = (decision, limit) if decision else (limit,)
    with connect(db_path()) as connection:
        rows = connection.execute(
            f"""
            SELECT f.*, p.first_name, p.last_name, p.facility_id
            FROM final_output f
            JOIN patients p ON p.patient_id = f.patient_id
            {where}
            ORDER BY
                CASE f.routing_decision
                    WHEN 'auto_accept' THEN 1
                    WHEN 'flag_for_review' THEN 2
                    ELSE 3
                END,
                f.patient_id
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/summary")
def summary() -> dict:
    with connect(db_path()) as connection:
        counts = connection.execute(
            """
            SELECT routing_decision, COUNT(*) AS count
            FROM final_output
            GROUP BY routing_decision
            """
        ).fetchall()
        status = connection.execute(
            """
            SELECT
                COUNT(*) AS patients,
                SUM(ready_for_processing) AS ready,
                SUM(has_coverage) AS with_coverage,
                SUM(has_notes) AS with_notes,
                SUM(has_assessments) AS with_assessments
            FROM patient_status
            """
        ).fetchone()
        failures = connection.execute("SELECT COUNT(*) AS count FROM failed_jobs").fetchone()
    return {
        "ingestion": dict(status),
        "routing_decisions": {row["routing_decision"]: row["count"] for row in counts},
        "failed_jobs": failures["count"],
    }
