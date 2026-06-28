import tempfile
import unittest
from pathlib import Path

from abi_pipeline.db import connect, init_db, set_status_flag, upsert_patients


class DatabaseTests(unittest.TestCase):
    def test_patient_readiness_requires_coverage_and_clinical_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            init_db(db_path)

            with connect(db_path) as connection:
                upsert_patients(
                    connection,
                    [
                        {
                            "id": 1,
                            "facility_id": 101,
                            "patient_id": "FA-001",
                            "is_new_admission": True,
                        }
                    ],
                )
                set_status_flag(connection, "FA-001", None, "has_coverage", True)
                row = connection.execute(
                    "SELECT ready_for_processing FROM patient_status WHERE patient_id = 'FA-001'"
                ).fetchone()
                self.assertEqual(row["ready_for_processing"], 0)

                set_status_flag(connection, None, 1, "has_notes", True)
                row = connection.execute(
                    "SELECT ready_for_processing FROM patient_status WHERE patient_id = 'FA-001'"
                ).fetchone()
                self.assertEqual(row["ready_for_processing"], 1)


if __name__ == "__main__":
    unittest.main()
