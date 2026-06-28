"""Pipeline orchestrator: ingestion -> extraction -> eligibility -> JSON output."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime

from pipeline.ingestion import PccClient
from pipeline.extractor import WoundExtractor
from pipeline.eligibility import EligibilityEngine
from pipeline.models import EligibilityResult, Patient, WoundData

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


class PipelineRunner:
    def __init__(self, openai_api_key: str, since: str | None = None) -> None:
        self.client = PccClient()
        self.extractor = WoundExtractor(api_key=openai_api_key)
        self.eligibility = EligibilityEngine()
        self.since = since

    def run(self) -> list[EligibilityResult]:
        t0 = time.time()
        logger.info("=== Pipeline starting ===")

        logger.info("Phase 1/3: Ingesting data from PCC API...")
        patients = self.client.fetch_and_enrich_all(since=self.since)
        logger.info("Ingested %d patients in %.1fs", len(patients), time.time() - t0)

        logger.info("Phase 2/3: Extracting wound data...")
        t1 = time.time()
        wound_map = self._extract_all(patients)
        logger.info("Extracted wound data in %.1fs", time.time() - t1)

        logger.info("Phase 3/3: Determining eligibility...")
        results = self.eligibility.process_all(patients, wound_map)

        elapsed = time.time() - t0
        self._log_summary(results, elapsed)
        return results

    def run_and_save(self, output_path: str | None = None) -> str:
        results = self.run()
        if output_path is None:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(OUTPUT_DIR, "results.json")

        output = [r.to_dict() for r in results]
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2, default=str)

        logger.info("Results written to %s (%d records)", output_path, len(output))
        return output_path

    def _extract_all(self, patients: list[Patient]) -> dict[str, WoundData]:
        wound_map: dict[str, WoundData] = {}
        total = len(patients)
        for i, patient in enumerate(patients, 1):
            if i % 50 == 0 or i == total:
                logger.info("Extraction progress: %d/%d patients", i, total)
            try:
                wound_data = self.extractor.extract_for_patient(
                    patient.notes, patient.assessments
                )
                wound_map[patient.patient_id] = wound_data
            except Exception:
                logger.exception("Failed extraction for patient %s", patient.patient_id)
                wound_map[patient.patient_id] = WoundData()
        return wound_map

    @staticmethod
    def _log_summary(results: list[EligibilityResult], elapsed: float) -> None:
        total = len(results)
        auto = sum(1 for r in results if r.routing_decision == "auto_accept")
        review = sum(1 for r in results if r.routing_decision == "flag_for_review")
        reject = sum(1 for r in results if r.routing_decision == "reject")

        logger.info("=== Pipeline complete in %.1fs ===", elapsed)
        logger.info("  Total patients:    %d", total)
        logger.info("  auto_accept:       %d (%.0f%%)", auto, 100 * auto / total if total else 0)
        logger.info("  flag_for_review:   %d (%.0f%%)", review, 100 * review / total if total else 0)
        logger.info("  reject:            %d (%.0f%%)", reject, 100 * reject / total if total else 0)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Set the OPENAI_API_KEY environment variable.")
        sys.exit(1)

    since = None
    if len(sys.argv) > 1:
        since = sys.argv[1]
        logger.info("Using incremental sync with since=%s", since)

    runner = PipelineRunner(openai_api_key=api_key, since=since)
    path = runner.run_and_save()
    print(f"\nResults saved to: {path}")


if __name__ == "__main__":
    main()
