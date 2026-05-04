import json
import pytest
from pathlib import Path
from fhir_custom.worker_template import normalize_name, FillResource, CreatePreFHIR, CreatePreFHIR_name, CreatePreFHIR_workouts
import fhir_custom.worker_template

@pytest.fixture
def fake_metadata(tmp_path):
    meta = {
        "template": "test_template.json",
        "constants": {"system": "test-system"}
    }
    path = tmp_path / "meta_test.json"
    path.write_text(json.dumps(meta))
    return meta, path

@pytest.fixture
def fake_template(tmp_path):
    tpl = {
        "code": {"text": "name"},
        "valueQuantity": {"value": "qty", "unit": "units"}
    }
    path = tmp_path / "test_template.json"
    path.write_text(json.dumps(tpl))
    return tpl, path


# Tests for "normalize_name"
def test_normalize_name_mapping():
    assert normalize_name("Yoga") == "yoga"
    assert normalize_name("Flexibilité") == "workouts"

def test_normalize_name_ascii_cleanup():
    assert normalize_name("Entraînement de Force") == "entrainement_de_force"

def test_normalize_name_trim_and_lower():
    assert normalize_name("  Test Name  ") == "test_name"
    

# Tests for "FillResource"
def test_fill_resource_simple_replace():
    template = {"a": "x"}
    src = {"x": 42}
    result = FillResource(src).build(template)
    assert result["a"] == 42

def test_fill_resource_nested_path():
    template = {"a": "b.c"}
    src = {"b": {"c": 99}}
    result = FillResource(src).build(template)
    assert result["a"] == 99

def test_fill_resource_not_found_keeps_string():
    template = {"a": "missing"}
    result = FillResource({}).build(template)
    assert result["a"] == "missing"
    

# Tests for "CreatePreFHIR"
def test_create_prefhir_render_basic(monkeypatch, tmp_path, fake_metadata, fake_template):
    meta, meta_path = fake_metadata
    tpl, tpl_path = fake_template

    monkeypatch.setattr(fhir_custom.worker_template, "METADATA_PATH", "")
    monkeypatch.setattr(fhir_custom.worker_template, "TEMPLATE_PATH", "")

    monkeypatch.setattr(
        fhir_custom.worker_template.CreatePreFHIR,
        "_load_metadata",
        lambda self, _: meta
    )
    monkeypatch.setattr(
        fhir_custom.worker_template.CreatePreFHIR,
        "_load_template",
        lambda self, _: tpl
    )

    payload = {
        "name": "Test",
        "units": "kg",
        "data": [{"qty": 10}]
    }

    cpf = CreatePreFHIR(payload, round_digits=1)
    result = cpf.render()

    assert isinstance(result, list)
    assert result[0]["valueQuantity"]["value"] == 10
    assert result[0]["valueQuantity"]["unit"] == "kg"
    

# Tests for "CreatePreFHIR_name"
def test_create_prefhir_name_injects_name():
    payload = {"data": [{"qty": 1}], "units": "kg"}
    obj = CreatePreFHIR_name(payload, name="custom")
    assert obj.raw_name == "custom"

def test_create_prefhir_name_rejects_existing_name():
    payload = {"name": "bad", "data": []}
    with pytest.raises(ValueError):
        CreatePreFHIR_name(payload, name="x")

def test_create_prefhir_name_invalid_name():
    with pytest.raises(ValueError):
        CreatePreFHIR_name({}, name="")
        
# Tests for "CreatePreFHIR_workouts"
def test_CreatePreFHIR_workouts():

    payload = {
        "name": "Yoga",
        "units": "count/min",
        "heartRateData": [
            {"Avg": 80, "date": "2025-01-01"}
        ]
    }

    creator = CreatePreFHIR_workouts()
    observations, parent_index, children_indices = creator.process(payload)

    assert len(observations) == 2
    assert parent_index == 0
    assert children_indices == [1]
