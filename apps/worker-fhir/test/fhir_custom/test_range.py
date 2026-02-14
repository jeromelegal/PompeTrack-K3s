import pytest
from decimal import Decimal
from pint import UndefinedUnitError
from fhir_custom.range import (
    _to_float,
    _make_pint_quantity,
    _interpret_comparator,
    _is_interval_empty,
    build_range_validated,
    ReferenceRangeValidationError,
    ureg,
)


# Tests for "_to_float"
@pytest.mark.parametrize(
    "value,expected",
    [
        (10, 10.0),
        (10.5, 10.5),
        (Decimal("2.34"), 2.34),
        ("3.5", 3.5),
        ("1.2e3", 1200.0),
    ],
)
def test_to_float_valid(value, expected):
    assert _to_float(value) == pytest.approx(expected)

@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "1,2",  # not a valid float
        None,
        [1, 2],
        object(),
    ],
)
def test_to_float_invalid(value):
    with pytest.raises(ReferenceRangeValidationError):
        _to_float(value)



# Tests for "_make_pint_quantity"
@pytest.mark.parametrize(
    "value,unit,expected_units",
    [
        (5, None, ureg.dimensionless),
        (3, "", ureg.dimensionless),
        (2, "kg", ureg.kg),
        (7, "m/s", ureg.meter / ureg.second),
    ],
)
def test_make_pint_quantity(value, unit, expected_units):
    q = _make_pint_quantity(value, unit)
    assert isinstance(q, ureg.Quantity)
    assert q.units == expected_units
    assert q.magnitude == pytest.approx(value)

def test_make_pint_quantity_unknown_unit():
    with pytest.raises(ReferenceRangeValidationError):
        _make_pint_quantity(1, "unknown_unit")


# Tests for "_interpret_comparator"
@pytest.mark.parametrize(
    ("comp", "is_low", "expected"),
    [
        (None, True, ">="),
        (None, False, "<="),
        ("ad", True, ">="),
        ("ad", False, "<="),
        ("<", False, "<"),
        (">", True, ">"),
        ("<=", False, "<="),
        (">=", True, ">="),
    ],
)
def test_interpret_comparator(comp, is_low, expected):
    result = _interpret_comparator(comp, is_low)
    assert result == expected

def test_interpret_comparator_invalid():
    with pytest.raises(ReferenceRangeValidationError):
        _interpret_comparator("invalid_cmp", is_low=True)


# Tests for "_is_interval_empty"
@pytest.mark.parametrize(
    ("low_val,low_incl,high_val,high_incl,expected"),
    [
        # straightforward overlaps
        (1, True, 5, True, False),
        (5, False, 5, False, True),  # exclusive both
        (5, False, 5, True, False),  # exclusive low, inclusive high
        (5, True, 5, False, False),  # inclusive low, exclusive high
        (6, True, 5, True, True),    # low > high
    ],
)
def test_is_interval_empty(low_val, low_incl, high_val, high_incl, expected):
    assert _is_interval_empty(low_val, low_incl, high_val, high_incl) is expected


# Tests for "build_range_validated"
def test_build_range_validated_same_unit():
    raw_low = {"comparator": ">", "value": "2", "unit": "kg"}
    raw_high = {"comparator": "<", "value": "20", "unit": "kg"}
    rr = build_range_validated(raw_low, raw_high, "normal", None)
    assert rr == [
        {
            "low": {"comparator": ">", "value": 2.0, "unit": "kilogram"},
            "high": {"comparator": "<", "value": 20.0, "unit": "kilogram"},
            "text": "normal",
        }
    ]

def test_build_range_validated_convert_units():
    # 2 kg -> cm
    raw_low = {"comparator": ">=", "value": "2", "unit": "kg"}
    raw_high = {"comparator": "<", "value": "2000", "unit": "g"}  # 2 kg
    rr = build_range_validated(raw_low, raw_high, None, convert_to_unit="kg")
    assert rr == [
        {
            "low": {"comparator": ">=", "value": 2.0, "unit": "kilogram"},
            "high": {"comparator": "<", "value": 2.0, "unit": "kilogram"},
        }
    ]

def test_build_range_validated_incompatible_units():
    raw_low = {"comparator": ">", "value": "1", "unit": "kg"}
    raw_high = {"comparator": "<", "value": "100", "unit": "m"}
    with pytest.raises(ReferenceRangeValidationError):
        build_range_validated(raw_low, raw_high, None)


def test_build_range_validated_missing_numeric():
    # only unit, no numeric
    raw_low = {"comparator": ">", "unit": "kPa"}
    raw_high = {"comparator": "<", "value": "10", "unit": "kPa"}
    rr = build_range_validated(raw_low, raw_high, "Pressure")
    assert rr == [
        {
            "low": {"comparator": ">", "value": None, "unit": "kPa"},
            "high": {"comparator": "<", "value": 10.0, "unit": "kilopascal"},
            "text": "Pressure",
        }
    ]


def test_build_range_validated_unitless():
    raw_low = {"comparator": "<=", "value": "5"}
    raw_high = {"comparator": ">=", "value": "2"}
    rr = build_range_validated(raw_low, raw_high, None)
    assert rr == [
        {
            "low": {"comparator": "<=", "value": 5.0, "unit": None},
            "high": {"comparator": ">=", "value": 2.0, "unit": None},
        }
    ]

def test_build_range_validated_empty_interval():
    raw_low = {"comparator": ">", "value": "5", "unit": "kg"}
    raw_high = {"comparator": "<", "value": "5", "unit": "kg"}
    with pytest.raises(ReferenceRangeValidationError):
        build_range_validated(raw_low, raw_high, None)

def test_build_range_validated_ad_comparator():
    raw_low = {"comparator": "ad", "value": "1", "unit": "m"}
    raw_high = {"comparator": "ad", "value": "1", "unit": "m"}
    rr = build_range_validated(raw_low, raw_high, None)
    # Should NOT raise error because 'ad' means inclusive
    assert rr == [
        {
            "low": {"comparator": "ad", "value": 1.0, "unit": "meter"},
            "high": {"comparator": "ad", "value": 1.0, "unit": "meter"},
        }
    ]

def test_build_range_validated_only_low():
    raw_low = {"comparator": ">=", "value": "3", "unit": "g"}
    rr = build_range_validated(raw_low, None, None)
    assert rr == [
        {
            "low": {"comparator": ">=", "value": 3.0, "unit": "gram"},
        }
    ]

def test_build_range_validated_only_high():
    raw_high = {"comparator": "<=", "value": "8", "unit": "g"}
    rr = build_range_validated(None, raw_high, None)
    assert rr == [
        {
            "high": {"comparator": "<=", "value": 8.0, "unit": "gram"},
        }
    ]

def test_build_range_validated_invalid_side_type():
    # raw_low should be dict or None
    with pytest.raises(ReferenceRangeValidationError):
        build_range_validated("not a dict", None, None)

def test_build_range_validated_invalid_comp():
    raw_low = {"comparator": ">>", "value": "1", "unit": "kg"}
    with pytest.raises(ReferenceRangeValidationError):
        build_range_validated(raw_low, None, None)