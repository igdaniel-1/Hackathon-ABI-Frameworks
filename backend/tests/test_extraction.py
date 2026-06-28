import unittest

from abi_pipeline.extraction import extract_from_assessment, extract_from_note


class ExtractionTests(unittest.TestCase):
    def test_extracts_structured_note(self):
        note = """
        Wound Assessment Note
        Location: Sacrum
        Wound Type: Pressure Ulcer, Stage 2
        Length: 3.2 cm  Width: 2.1 cm  Depth: 0.4 cm
        Drainage: Moderate serosanguineous
        """

        result = extract_from_note(note)

        self.assertIsNotNone(result)
        self.assertTrue(result.complete)
        self.assertEqual(result.wound_type, "pressure_ulcer")
        self.assertEqual(result.wound_stage, "2")
        self.assertEqual(result.location, "Sacrum")
        self.assertEqual(result.length_cm, 3.2)
        self.assertEqual(result.width_cm, 2.1)
        self.assertEqual(result.depth_cm, 0.4)
        self.assertEqual(result.drainage_amount, "moderate")

    def test_extracts_compact_measurements(self):
        note = "Venous wound on ankle. Meas 4.2x3.1x1.5cm with heavy drainage."

        result = extract_from_note(note)

        self.assertIsNotNone(result)
        self.assertEqual(result.wound_type, "venous_stasis_ulcer")
        self.assertEqual(result.location, "ankle")
        self.assertEqual(result.length_cm, 4.2)
        self.assertEqual(result.width_cm, 3.1)
        self.assertEqual(result.depth_cm, 1.5)
        self.assertEqual(result.drainage_amount, "heavy")

    def test_extracts_assessment_json(self):
        result = extract_from_assessment(
            '{"wound_type": "pressure_ulcer", "stage": 3, "location": "Heel", '
            '"length_cm": 2.0, "width_cm": 1.5, "depth_cm": 0.2, "drainage_amount": "light"}'
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.complete)
        self.assertEqual(result.source, "assessment")
        self.assertEqual(result.drainage_amount, "light")


if __name__ == "__main__":
    unittest.main()
