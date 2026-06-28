from datetime import date

from wound_eligibility.engine import evaluate_patient


def test_accepts_complete_structured_assessment_with_active_medicare_b():
    payload = {
        "patient": {"id": 1, "patient_id": "FA-001", "facility_id": 101},
        "diagnoses": [
            {
                "icd10_code": "L89.152",
                "icd10_description": "Pressure ulcer of sacral region, stage 2",
                "clinical_status": "active",
            }
        ],
        "coverage": [
            {
                "payer_code": "MCB",
                "payer_type": "Medicare B",
                "effective_from": "2020-01-01T00:00:00",
                "effective_to": None,
            }
        ],
        "notes": [],
        "assessments": [
            {
                "status": "Complete",
                "assessment_date": "2026-05-10",
                "raw_json": {
                    "wound_type": "pressure_ulcer",
                    "stage": 2,
                    "location": "Sacrum",
                    "length_cm": 3.2,
                    "width_cm": 2.1,
                    "depth_cm": 0.4,
                    "drainage_amount": "moderate",
                },
            }
        ],
    }

    result = evaluate_patient(payload, today=date(2026, 6, 28))

    assert result["decision"] == "Accept"
    assert result["routing_decision"] == "auto_accept"
    assert result["active_medicare_part_b"] is True
    assert result["evidence_source"] == "assessment"
    assert result["length_cm"] == 3.2


def test_extracts_prose_note_measurements_and_drainage():
    payload = {
        "patient": {"id": 5, "patient_id": "FA-005"},
        "diagnoses": [],
        "coverage": [{"payer_code": "MCB", "effective_from": "2020-01-01", "effective_to": None}],
        "notes": [
            {
                "effective_date": "2026-05-12T11:00:00",
                "note_text": "DFU to left foot. Meas 4.2x3.1x1.5cm. Drainage heavy today.",
            }
        ],
        "assessments": [],
    }

    result = evaluate_patient(payload, today=date(2026, 6, 28))

    assert result["decision"] == "Accept"
    assert result["wound_type"] == "diabetic_foot_ulcer"
    assert result["location"] == "Foot"
    assert result["drainage_amount"] == "heavy"


def test_rejects_when_medicare_part_b_is_not_active():
    payload = {
        "patient": {"id": 2, "patient_id": "FA-002"},
        "diagnoses": [{"icd10_code": "L89.153", "clinical_status": "active"}],
        "coverage": [{"payer_code": "HMO", "effective_from": "2020-01-01", "effective_to": None}],
        "notes": [
            {
                "note_text": "Location: Sacrum\nWound Type: Pressure Ulcer Stage 3\nLength: 2.0 cm Width: 1.0 cm Depth: 0.3 cm\nDrainage: light",
                "effective_date": "2026-05-10T09:00:00",
            }
        ],
        "assessments": [],
    }

    result = evaluate_patient(payload, today=date(2026, 6, 28))

    assert result["decision"] == "Reject"
    assert result["routing_decision"] == "reject"
    assert "No active Medicare Part B coverage" in result["reason"]


def test_rejects_when_required_wound_fields_are_missing():
    payload = {
        "patient": {"id": 3, "patient_id": "FA-003"},
        "diagnoses": [{"icd10_code": "L89.152", "clinical_status": "active"}],
        "coverage": [{"payer_code": "MCB", "effective_from": "2020-01-01", "effective_to": None}],
        "notes": [{"note_text": "Pressure ulcer noted at sacrum. Drainage moderate."}],
        "assessments": [],
    }

    result = evaluate_patient(payload, today=date(2026, 6, 28))

    assert result["decision"] == "Reject"
    assert result["routing_decision"] == "flag_for_review"
    assert "missing length_cm, width_cm, depth_cm" in result["reason"]
