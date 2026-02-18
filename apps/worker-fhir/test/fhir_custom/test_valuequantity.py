import pytest
from fhir_custom.valuequantity import _to_float, ValueQuantityValidationError, _model_dump_safe, value_quantity
from fhir.resources.quantity import Quantity
from decimal import Decimal, InvalidOperation


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
    with pytest.raises(ValueQuantityValidationError):
        _to_float(val)


def test_to_float_unacceptable_type():
    with pytest.raises(ValueQuantityValidationError) as exc:
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
    
# Tests for "value_quantity"
def test_value_quantity_int():
    valuequantity = value_quantity(5, "kg")
    assert valuequantity == {"value": 5.0, "unit": "kg"}
    
def test_value_quantity_float():
    valuequantity = value_quantity(5.123, "km")
    assert valuequantity == {"value": 5.123, "unit": "km"}
    
def test_value_quantity_string():
    valuequantity = value_quantity("80.36", "dB")
    assert valuequantity == {"value": 80.36, "unit": "dB"}
    
def test_value_quantity_no_value():
    with pytest.raises(ValueQuantityValidationError) as exc:
        valuequantity = value_quantity(value=None, unit="dB")
    assert "value absente ou incorrecte" in str(exc.value)
    
def test_value_quantity_no_unit():
    valuequantity = value_quantity(value=8, unit=None)
    assert valuequantity == {"value": 8}
    