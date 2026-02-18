import pytest
from fhir_custom.component import _to_float, ComponentValidationError, _model_dump_safe, build_components_validated
from decimal import Decimal
from fhir.resources.quantity import Quantity
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
import json

# Tests for "_to_float"
def test_to_float_integer():
    assert _to_float(42) == 42.0


def test_to_float_float():
    assert _to_float(3.14) == 3.14


def test_to_float_decimal():
    assert _to_float(Decimal("2.5")) == 2.5


def test_to_float_str_numeric():
    assert _to_float("  6.0  ") == 6.0


def test_to_float_str_as_decimal():
    # str that can’t be cast to float but can be cast to Decimal
    assert _to_float("1e-3") == 0.001


@pytest.mark.parametrize("val", [None, "  ", {}])
def test_to_float_invalid(val):
    with pytest.raises(ComponentValidationError):
        _to_float(val)


def test_to_float_unacceptable_type():
    with pytest.raises(ComponentValidationError) as exc:
        _to_float([1, 2, 3])
    assert "Type de 'value' non supporté" in str(exc.value)
    

# Tests for "_model_dump_safe"
def test_model_dump_safe_fhirmodel():
    q = Quantity(value=12, unit='kJ')
    assert _model_dump_safe(q) == q.model_dump()   

class Dummy:
    def dict(self):
        return {"foo":"bar"}

def test_model_dump_safe_dict():
    d = Dummy()
    assert _model_dump_safe(d) == {"foo":"bar"}
    
# Tests for "build_components_validated"
raw_one = [
    {
        "code_system[0]": "http://loinc.org",
        "code_code[0]": "41981-2",
        "code_display[0]": "Energy expended",
        "value_value[0]": "42",
        "value_unit[0]": "kJ",
        # interprétation historique (string)
        "inter_system[0]": "http://example.org",
        "inter_code[0]": "123-456",
        "inter_display[0]": "example"
    }
]

def test_build_components_validated_full_valid():
    res = build_components_validated(raw_one)
    # res est une liste de dicts FHIR
    assert isinstance(res, list)
    c = res[0]
    # Vérif code
    assert c["code"]["coding"][0]["system"] == "http://loinc.org"
    assert c["code"]["coding"][0]["code"] == "41981-2"
    # Vérif quantity
    assert c["valueQuantity"]["value"] == 42.0
    assert c["valueQuantity"]["unit"] == "kJ"
    # Vérif interprétation
    assert isinstance(c["interpretation"], list)
    assert c["interpretation"][0]["coding"][0]["display"] == "example"
    
def test_missing_code():
    raw = [{"value_value[0]": 10}]
    with pytest.raises(ComponentValidationError, match=r'champs code_\* manquants'):
        build_components_validated(raw)

def test_invalid_quantity_unit():
    raw = [{
        "code_system[0]": "http://loinc.org",
        "code_code[0]": "41981-2",
        "value_value[0]": "no-number",
    }]
    with pytest.raises(ComponentValidationError, match=r'value_value invalide'):
        build_components_validated(raw)

def test_interpretation_with_list_display():
    raw = [{
        "code_system[0]": "http://loinc.org",
        "code_code[0]": "41981-2",
        "inter_display[0]": ["red", "green"],
        "inter_system[0]": "http://example.org",
    }]
    result = build_components_validated(raw)
    interprets = result[0]["interpretation"][0]["coding"]
    assert len(interprets) == 2
    assert interprets[0]["display"] == "red"
    assert interprets[1]["display"] == "green"

def test_interpretation_string_history():
    raw = [{
        "code_system[0]": "http://loinc.org",
        "code_code[0]": "41981-2",
        # using historical single string display
        "inter_display[0]": "positive",
        "inter_code[0]": "POS",
        "inter_system[0]": "http://clinicalinterpretation.org"
    }]
    result = build_components_validated(raw)
    interp = result[0]["interpretation"][0]
    assert interp["coding"][0]["code"] == "POS"
    assert interp["coding"][0]["display"] == "positive"
    assert interp["coding"][0]["system"] == "http://clinicalinterpretation.org"