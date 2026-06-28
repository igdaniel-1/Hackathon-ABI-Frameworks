from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass
from typing import Any

import aiohttp

from .config import Settings, settings
from .db import (
    connect,
    init_db,
    record_failed_job,
    replace_child_rows,
    set_status_flag,
    upsert_patients,
)
from .extraction import refresh_final_output


@dataclass
class Job:
    job_type: str
    target_id: str | int
    attempt: int = 1
    not_before: float = 0


class RateLimited(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limited; retry after {retry_after}s")
        self.retry_after = retry_after


class Pipeline:
    def __init__(self, runtime_settings: Settings = settings) -> None:
        self.settings = runtime_settings
        self.queue: asyncio.Queue[Job] | None = None
        self.session: aiohttp.ClientSession | None = None

    async def run(self) -> None:
        init_db(self.settings.db_path)
        self.queue = asyncio.Queue()
        timeout = aiohttp.ClientTimeout(total=self.settings.request_timeout_seconds)
        async with aiohttp.ClientSession(base_url=self.settings.api_base_url, timeout=timeout) as session:
            self.session = session
            for facility_id in self.settings.facilities:
                await self.enqueue(Job("fetch_patients", facility_id))

            workers = [
                asyncio.create_task(self.worker(worker_id))
                for worker_id in range(self.settings.worker_count)
            ]
            await self.queue.join()
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

        with connect(self.settings.db_path) as connection:
            final_rows = refresh_final_output(connection)
        print(f"Ingestion complete. Refreshed {final_rows} final output rows.")

    async def worker(self, worker_id: int) -> None:
        while True:
            queue = self.require_queue()
            job = await queue.get()
            try:
                now = time.monotonic()
                if job.not_before > now:
                    await asyncio.sleep(min(job.not_before - now, 1.0))
                    await self.enqueue(job)
                    continue
                await self.execute(job)
            except RateLimited as error:
                await self.retry_or_fail(job, str(error), error.retry_after)
            except Exception as error:
                await self.retry_or_fail(job, repr(error), min(2**job.attempt, 30))
            finally:
                queue.task_done()

    async def retry_or_fail(self, job: Job, error: str, delay_seconds: float) -> None:
        if job.attempt >= self.settings.max_attempts:
            with connect(self.settings.db_path) as connection:
                record_failed_job(connection, job.job_type, str(job.target_id), job.attempt, error)
            print(f"failed {job.job_type}:{job.target_id} after {job.attempt} attempts: {error}")
            return
        if "Rate limited" in error:
            print(
                f"429 retry {job.job_type}:{job.target_id} "
                f"attempt {job.attempt}/{self.settings.max_attempts}; waiting {delay_seconds:.0f}s"
            )
        await self.enqueue(
            Job(
                job.job_type,
                job.target_id,
                attempt=job.attempt + 1,
                not_before=time.monotonic() + delay_seconds,
            )
        )

    async def execute(self, job: Job) -> None:
        if job.job_type == "fetch_patients":
            rows = await self.get_json("/pcc/patients", {"facility_id": job.target_id})
            with connect(self.settings.db_path) as connection:
                patients = upsert_patients(connection, rows)
            for patient in patients:
                await self.enqueue(Job("fetch_diagnoses", patient["patient_id"]))
                await self.enqueue(Job("fetch_coverage", patient["patient_id"]))
                await self.enqueue(Job("fetch_notes", patient["id"]))
                await self.enqueue(Job("fetch_assessments", patient["id"]))
            print(f"loaded {len(patients)} patients for facility {job.target_id}")
            return

        if job.job_type == "fetch_diagnoses":
            rows = await self.get_json("/pcc/diagnoses", {"patient_id": job.target_id})
            with connect(self.settings.db_path) as connection:
                count = replace_child_rows(connection, "diagnoses", "patient_id", job.target_id, rows)
                set_status_flag(connection, str(job.target_id), None, "has_diagnoses", count > 0)
            return

        if job.job_type == "fetch_coverage":
            rows = await self.get_json("/pcc/coverage", {"patient_id": job.target_id})
            with connect(self.settings.db_path) as connection:
                count = replace_child_rows(connection, "coverage", "patient_id", job.target_id, rows)
                set_status_flag(connection, str(job.target_id), None, "has_coverage", count > 0)
            return

        if job.job_type == "fetch_notes":
            rows = await self.get_json("/pcc/notes", {"patient_id": job.target_id})
            with connect(self.settings.db_path) as connection:
                count = replace_child_rows(connection, "notes", "patient_id", job.target_id, rows)
                set_status_flag(connection, None, int(job.target_id), "has_notes", count > 0)
            return

        if job.job_type == "fetch_assessments":
            rows = await self.get_json("/pcc/assessments", {"patient_id": job.target_id})
            with connect(self.settings.db_path) as connection:
                count = replace_child_rows(connection, "assessments", "patient_id", job.target_id, rows)
                set_status_flag(connection, None, int(job.target_id), "has_assessments", count > 0)
            return

        raise ValueError(f"Unknown job type: {job.job_type}")

    async def get_json(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if self.session is None:
            raise RuntimeError("Pipeline session has not been initialized")
        async with self.session.get(path, params=params) as response:
            if response.status == 429:
                retry_after = float(response.headers.get("Retry-After", "1"))
                raise RateLimited(retry_after)
            response.raise_for_status()
            payload = await response.json()
            if not isinstance(payload, list):
                raise ValueError(f"Expected list response from {path}, got {type(payload).__name__}")
            return payload

    def require_queue(self) -> asyncio.Queue[Job]:
        if self.queue is None:
            raise RuntimeError("Pipeline queue has not been initialized")
        return self.queue

    async def enqueue(self, job: Job) -> None:
        await self.require_queue().put(job)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ABI Frameworks ingestion backend.")
    parser.add_argument("--db-path", default=str(settings.db_path), help="SQLite database path")
    parser.add_argument("--workers", type=int, default=settings.worker_count, help="Concurrent worker count")
    parser.add_argument("--max-attempts", type=int, default=settings.max_attempts, help="Retry attempts per job")
    parser.add_argument("--api-base-url", default=settings.api_base_url, help="Mock PCC API base URL")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runtime_settings = Settings(
        api_base_url=args.api_base_url,
        db_path=args.db_path,
        worker_count=args.workers,
        max_attempts=args.max_attempts,
    )
    asyncio.run(Pipeline(runtime_settings).run())


if __name__ == "__main__":
    main()
