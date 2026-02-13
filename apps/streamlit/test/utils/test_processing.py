import pytest
from utils.processing import process_weekly_data, process_monthly_data, process_force_data, process_pain_map

def assert_iso_date(value: str):
    """Vérifie que la date est une string ISO 8601."""
    assert isinstance(value, str)
    assert "T" in value
    assert value.endswith("+00:00") or value.endswith("Z")


# process_weekly_data
def test_weekly_data_empty():
    result = process_weekly_data()
    assert result == {"metrics": []}

def test_weekly_weight_only():
    result = process_weekly_data(weight=72.5)
    metrics = result["metrics"]

    assert len(metrics) == 1
    m = metrics[0]
    assert m["name"] == "manual_weight"
    assert m["data"][0]["units"] == "kg"
    assert m["type"] == "weekly"
    assert m["data"][0]["qty"] == 72.5
    assert_iso_date(m["data"][0]["date"])
    # {'data': [{'date': '2026-01-19T16:55:09.152930+00:00', 'qty': 72.5, 'units': 'kg'}], 
    # 'name': 'manual_weight', 'type': 'weekly'}

def test_weekly_heart_rate_only():
    result = process_weekly_data(heart_rate=60)
    m = result["metrics"][0]

    assert m["name"] == "manual_heart_rate"
    assert m["data"][0]["units"] == "bpm"
    assert m["data"][0]["qty"] == 60

def test_weekly_bp_complete():
    result = process_weekly_data(systolic=120, diastolic=80)
    m = result["metrics"][0]

    assert m["name"] == "manual_bp"
    assert m["data"][0]["units"] == "mmHg"
    assert len(m["data"]) == 1

    #measures = {"manual_bp": d["qty"] for d in m["data"]}
    assert m["data"][0]["systolic_value"] == 120
    assert m["data"][0]["diastolic_value"] == 80

def test_weekly_bp_incomplete_not_added():
    result = process_weekly_data(systolic=120)
    assert result["metrics"] == []

def test_weekly_symptoms_empty_string_not_added():
    result = process_weekly_data(symptoms="")
    assert result["metrics"] == []

def test_weekly_symptoms_added():
    result = process_weekly_data(symptoms="fatigue")
    m = result["metrics"][0]

    assert m["name"] == "manual_symptoms"
    assert m["data"][0]["note"] == "fatigue"


# process_monthly_data
def test_monthly_empty():
    result = process_monthly_data()
    assert result == {"metrics": []}

def test_monthly_multiple_metrics():
    result = process_monthly_data(
        calf_left=35.0,
        waist=90.0,
        comments="stable"
    )

    metrics = result["metrics"]
    names = {m["name"] for m in metrics}

    assert names == {"manual_calf_left", "manual_waist", "manual_comments"}

def test_monthly_units():
    result = process_monthly_data(neck=38.5)
    m = result["metrics"][0]

    assert m["data"][0]["units"] == "cm"
    assert m["data"][0]["qty"] == 38.5


# process_force_data
def test_force_empty():
    result = process_force_data()
    assert result == {"metrics": []}

def test_force_quadriceps_and_grip():
    result = process_force_data(
        quadriceps_left=320.0,
        grip_right=45.0
    )

    metrics = result["metrics"]
    names = {m["name"] for m in metrics}

    assert names == {"manual_quadriceps_left", "manual_grip_right"}

def test_force_rpe_without_units():
    result = process_force_data(rpe=7)
    m = result["metrics"][0]

    assert m["name"] == "manual_rpe"
    assert "units" not in m
    assert m["data"][0]["qty"] == 7

def test_force_strength_notes():
    result = process_force_data(strength_notes="bonne séance")
    m = result["metrics"][0]

    assert m["name"] == "manual_strength_notes"
    assert m["data"][0]["note"] == "bonne séance"


# process_pain_map
def test_pain_map_empty():
    result = process_pain_map([])
    assert result == {"metrics": []}

def test_pain_map_single():
    pain = {"zone": "Tête", "intensity": 5}
    result = process_pain_map([pain])

    metrics = result["metrics"]
    assert len(metrics) == 1
    assert metrics[0]["name"] == "manual_pain"
    assert metrics[0]["data"]["body_text"] == "Tête"
    assert metrics[0]["data"]["value_value"] == 5

def test_pain_map_multiple():
    pains = [
        {"zone": "Bas du dos", "intensity": 3},
        {"zone": "Genou gauche", "intensity": 6},
    ]
    result = process_pain_map(pains)

    metrics = result["metrics"]
    assert len(metrics) == 2
