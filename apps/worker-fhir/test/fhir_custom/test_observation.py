import pytest
from fhir_custom.observation import to_fhir_datetime, _codeable, iso_to_dt, _coding_list, _build_obs_args, to_fhir_observation, list_to_fhir_observation
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List
import pytest
from fhir.resources.observation import Observation
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
import fhir_custom.observation


# Tests for "to_fhir_datetime"
def test_to_fhir_datetime_from_iso_string_naive():
    iso_str = "2025-09-22T14:30:00"
    expected = "2025-09-22T14:30:00Z"
    assert to_fhir_datetime(iso_str) == expected


def test_to_fhir_datetime_with_tz():
    iso_str = "2025-09-22T14:30:00+02:00"
    expected = "2025-09-22T14:30:00+02:00"
    assert to_fhir_datetime(iso_str) == expected


def test_to_fhir_datetime_from_datetime_obj():
    dt = datetime(2025, 9, 22, 14, 30, tzinfo=timezone(timedelta(hours=3)))
    expected = "2025-09-22T14:30:00+03:00"
    assert to_fhir_datetime(dt) == expected

# Tests for "_codeable"
def test_codeable_basic():
    res = _codeable(system="http://loinc.org",
                                        code="1234-5",
                                        display="Heart Rate",
                                        text="HR")
    assert isinstance(res, CodeableConcept)
    assert res.text == "HR"
    assert res.coding[0].system == "http://loinc.org"
    assert res.coding[0].code == "1234-5"
    assert res.coding[0].display == "Heart Rate"
    
# Tests for "_coding_list"
def test_coding_list_multiple():
    codings = ["a", "b", "c"]
    res = _coding_list(codings=codings)
    assert isinstance(res, dict)
    assert "coding" in res
    assert res["coding"] == [{"code": "a", "display": "a"},
                             {"code": "b", "display": "b"},
                             {"code": "c", "display": "c"}]
    
# Tests for "iso_to_dt"
def test_iso_to_dt():
    iso = "2025-09-22T14:30:00+02:00"
    dt = iso_to_dt(iso)
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
    assert dt == datetime(2025, 9, 22, 14, 30, tzinfo=timezone(timedelta(hours=2)))
    
# Mock
@pytest.fixture
def mock_external(monkeypatch):
    """Patch les fonctions de fhir_custom pour retourner des valeurs simples."""
    def fake_range(*_, **__):
        return [{"low": {"value": 0, "unit": "kg"}, "high": {"value": 100, "unit": "kg"}}]

    def fake_components(*_, **__):
        return [{"code": {"coding":[{"code":"component1","display":"component1"}],
                          "text":"component1"},
                 "valueQuantity": {"value": 10, "unit":"mg"}}]

    def fake_value_quantity(value, unit):
        return {"value": value, "unit": unit}

    monkeypatch.setattr("fhir_custom.observation.build_range_validated", fake_range)
    monkeypatch.setattr("fhir_custom.observation.build_components_validated", fake_components)
    monkeypatch.setattr("fhir_custom.observation.value_quantity", fake_value_quantity)
    
# Tests for "_build_obs_args"
def test_build_obs_args_minimal(mock_external):
    raw = {
        "status": "final",
        "code_system": "http://loinc.org",
        "code_code": "82810-5",
        "patient_id": "123",
    }
    kwargs = _build_obs_args(raw)

    assert kwargs["status"] == "final"
    assert kwargs["subject"]["reference"] == "Patient/123"

    assert isinstance(kwargs["code"], CodeableConcept)

    for key in ["effectiveDateTime", "effectivePeriod", "category", "interpretation",
                "note", "bodySite", "method", "device", "referenceRange",
                "component", "valueQuantity", "extension", "hasMember"]:
        assert key not in kwargs


def test_build_obs_args_sleep_analysis(mock_external):
    raw = {
        "status": "final",
        "code_system": "http://my.codes",
        "code_code": "sleep_analysis",
        "patient_id": "456",
        "periodstart": "2025-01-01T23:00:00Z",
        "periodend": "2025-01-02T07:00:00Z",
    }
    kwargs = _build_obs_args(raw)
    start = iso_to_dt(raw["periodstart"])
    end = iso_to_dt(raw["periodend"])
    expected_hours = (end - start).total_seconds() / 3600
    assert kwargs["valueQuantity"]["value"] == expected_hours
    assert kwargs["effectivePeriod"]["start"] == "2025-01-01T23:00:00Z"
    assert kwargs["effectivePeriod"]["end"] == "2025-01-02T07:00:00Z"


def test_to_fhir_observation_dict(mock_external):
    raw = {
        "status": "final",
        "code_system": "http://loinc.org",
        "code_code": "718-7",
        "value_value": 12.5,
        "value_unit": "mg/dL",
        "patient_id": "001",
    }
    obs = to_fhir_observation(raw)
    assert isinstance(obs, Observation)
    assert obs.status == "final"
    assert obs.subject.reference == "Patient/001"
    assert obs.valueQuantity.value == 12.5
    assert obs.valueQuantity.unit == "mg/dL"


def test_to_fhir_observation_json_file(tmp_path, mock_external):
    data = {
        "status": "final",
        "code_system": "http://loinc.org",
        "code_code": "59408-5",
        "value_value": 8.1,
        "value_unit": "mmol/L",
        "patient_id": "001",
    }
    file_path = tmp_path / "obs.json"
    file_path.write_text(json.dumps(data))
    obs = to_fhir_observation(str(file_path))
    assert isinstance(obs, Observation)
    assert obs.valueQuantity.unit == "mmol/L"


def test_list_to_fhir_observation_batch(mock_external):
    raws = [
        {"status": "final", "code_system": "http://loinc.org", "code_code": "1234-5", "patient_id": "1"},
        {"status": "final", "code_system": "http://loinc.org", "code_code": "2345-6", "patient_id": "2"},
    ]
    obs_list, total = list_to_fhir_observation(raws, 0)
    assert len(obs_list) == 2
    assert total == 2
    ids = {obs.id for obs in obs_list}
    assert len(ids) == 2  # id unique
    assert all(obs.subject.reference in ["Patient/1", "Patient/2"] for obs in obs_list)


def test_build_obs_args_tag(mock_external):
    raw = {
        "status": "final",
        "code_system": "http://loinc.org",
        "code_code": "1234-5",
        "patient_id": "001",
        "tag_system": "http://example.org/ext",
        "tag_code": "mycode",
    }
    kwargs = _build_obs_args(raw)
    assert kwargs["meta"]["tag"][0]["system"] == "http://example.org/ext"
    assert kwargs["meta"]['tag'][0]["code"] == "mycode"