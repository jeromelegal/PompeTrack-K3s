from typing import Any, Dict, List, Optional
from decimal import Decimal, InvalidOperation
from pint import UnitRegistry, UndefinedUnitError

# Pint instance - Units validation
ureg = UnitRegistry()

# HHIR allowed comparators 
ALLOWED_COMPARATORS = {"<", "<=", ">", ">=", "ad"}

# Exceptions
class ReferenceRangeValidationError(ValueError):
    pass

# Function to transform any value in float
def _to_float(value: Any) -> float:
    """
    Transform any value in float
    """
    if value is None:
        raise ReferenceRangeValidationError("value is None")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            try:
                return float(Decimal(value))
            except (InvalidOperation, ValueError):
                raise ReferenceRangeValidationError(f"Impossible de convertir en float: {value!r}")
    raise ReferenceRangeValidationError(f"Type de 'value' non supporté: {type(value)}")

# Function to make pint quantity
def _make_pint_quantity(value: float, unit: Optional[str]):
    """
    Returns pint quantity. unit None -> dimensionless
    """
    if unit is None or unit == "":
        return value * ureg.dimensionless
    try:
        return value * ureg(unit)
    except UndefinedUnitError as e:
        raise ReferenceRangeValidationError(f"Unité inconnue pour pint: {unit!r}") from e

# Function to interpret comparator
def _interpret_comparator(comparator: Optional[str], is_low: bool) -> str:
    """
    Return comparator.
    Default to '>=' if None.
    """
    if comparator is None:
        # default inclusive
        return ">=" if is_low else "<="
    if comparator not in ALLOWED_COMPARATORS:
        raise ReferenceRangeValidationError(f"Comparator invalide: {comparator!r}")
    # map shorthand 'ad' -> treat as inclusive
    if comparator == "ad":
        return ">=" if is_low else "<="
    return comparator

# Function to interpret comparator
def _as_interval_bounds(val: float, comp: str):
    """
    Return (min, max, inclusif_min, inclusif_max)
    """
    if comp in (">", ">="):
        return val, None, comp == ">=", None
    if comp in ("<", "<="):
        return None, val, None, comp == "<="
    raise ReferenceRangeValidationError(f"Comparator invalide: {comp}")

# Function to check if interval is empty
def _is_interval_empty(
    low_val: float, 
    low_incl: bool, 
    high_val: float, 
    high_incl: bool
) -> bool:
    """
    Return True if interval is empty.
    """
    if low_val > high_val:
        return True
    if low_val < high_val:
        return False
    # low_val == high_val
    return (not low_incl) and (not high_incl)

# Function to build range
def build_range_validated(
    range_low: Optional[Dict[str, Any]],
    range_high: Optional[Dict[str, Any]],
    range_text: Optional[str],
    convert_to_unit: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    raw example:
    {
      "range_low": {"comparator": ">", "value": "2", "unit": "kg"},
      "range_high": {"comparator": "<", "value": "20", "unit": "kg"},
      "range_text": "test de force"
    }
    Returns:
    [
      {
        "low": {"comparator": "...", "value": <float>, "unit": "<unit str>"},
        "high": {"comparator": "...", "value": <float>, "unit": "<unit str>"},
        "text": "..."
      }
    ]
    Raises ReferenceRangeValidationError on invalid input.
    """
    # Extract raw parts (keys are optional)
    # low_raw = raw.get("range_low")
    # high_raw = raw.get("range_high")
    # text = raw.get("range_text")

    # parse helper: returns dict with keys: 'pint' (or None), 'unit' (or None), 'comparator' (or None), 'numeric' (or None)
    def _parse_side(side_raw, side_name: str):
        if side_raw is None:
            return {"pint": None, "unit": None, "comparator": None, "numeric": None}
        if not isinstance(side_raw, dict):
            raise ReferenceRangeValidationError(f"{side_name} doit être un dict ou absent")
        comp = side_raw.get("comparator")
        if comp is not None and comp not in ALLOWED_COMPARATORS:
            raise ReferenceRangeValidationError(f"{side_name}.comparator invalide : {comp!r}")
        val_raw = side_raw.get("value")
        unit_raw = side_raw.get("unit")
        if val_raw is None:
            # allowed: quantity without numeric value
            return {"pint": None, "unit": unit_raw, "comparator": comp, "numeric": None}
        # try to convert to float
        num = _to_float(val_raw)
        # make pint quantity (may raise if unit unknown)
        pq = _make_pint_quantity(num, unit_raw)
        return {"pint": pq, "unit": unit_raw, "comparator": comp, "numeric": num}

    low = _parse_side(range_low, "range_low")
    high = _parse_side(range_high, "range_high")

    normalized: Dict[str, Any] = {}

    # If both sides have pint quantities with numeric values -> convert to common units
    if low["pint"] is not None and high["pint"] is not None:
        try:
            if convert_to_unit:
                target = ureg(convert_to_unit)
                low_conv = low["pint"].to(target)
                high_conv = high["pint"].to(target)
                used_unit = str(target.units)
            else:
                # try to convert high to low units first
                try:
                    high_conv = high["pint"].to(low["pint"].units)
                    low_conv = low["pint"]
                    used_unit = str(low["pint"].units)
                except Exception:
                    # try reverse (low -> high units)
                    try:
                        low_conv = low["pint"].to(high["pint"].units)
                        high_conv = high["pint"]
                        used_unit = str(high["pint"].units)
                    except Exception as e:
                        raise ReferenceRangeValidationError(
                            f"Unités incompatibles ou conversion impossible: {low.get('unit')!r} vs {high.get('unit')!r}"
                        ) from e
        except UndefinedUnitError as e:
            raise ReferenceRangeValidationError(f"Unité inconnue pour pint: {e}") from e

        low_val_num = float(low_conv.magnitude)
        high_val_num = float(high_conv.magnitude)

        # Interpret comparators -> inclusive/exclusive booleans
        low_comp  = _interpret_comparator(low["comparator"],  is_low=True)
        high_comp = _interpret_comparator(high["comparator"], is_low=False)

        low_min, low_max, low_min_inc, low_max_inc = _as_interval_bounds(low_val_num, low_comp)
        high_min, high_max, high_min_inc, high_max_inc = _as_interval_bounds(high_val_num, high_comp)

        # borne basse réelle
        min_val = max(v for v in (low_min, high_min) if v is not None)
        min_inc = (
            low_min_inc if low_min == min_val else high_min_inc
        )

        # borne haute réelle
        max_val = min(v for v in (low_max, high_max) if v is not None)
        max_inc = (
            low_max_inc if low_max == max_val else high_max_inc
        )

        if _is_interval_empty(min_val, min_inc, max_val, max_inc):
            raise ReferenceRangeValidationError(
                f"Intervalle vide après normalisation: [{min_val}, {max_val}]"
            )
            
        def _normalize_unit(unit: Optional[str]) -> Optional[str]:
            if unit is None:
                return None
            if unit == "dimensionless":
                return None
            return unit

        normalized["low"] = {
            "comparator": low["comparator"],
            "value": low_val_num,
            "unit": _normalize_unit(used_unit)
        }
        normalized["high"] = {
            "comparator": high["comparator"],
            "value": high_val_num,
            "unit": _normalize_unit(used_unit)
        }

    else:
        # Handle cases where one or both sides are missing numeric value
        if low["pint"] is not None:
            try:
                if convert_to_unit:
                    low_conv = low["pint"].to(convert_to_unit)
                    used_unit = str(low_conv.units)
                    normalized["low"] = {"comparator": low["comparator"], "value": float(low_conv.magnitude), "unit": used_unit}
                else:
                    normalized["low"] = {"comparator": low["comparator"], "value": float(low["pint"].magnitude), "unit": str(low["pint"].units)}
            except UndefinedUnitError as e:
                raise ReferenceRangeValidationError(f"Low: unité inconnue pour pint: {e}") from e
        elif low["numeric"] is None and (range_low is not None):
            # low present but no numeric
            normalized["low"] = {"comparator": low["comparator"], "value": None, "unit": low["unit"]}

        if high["pint"] is not None:
            try:
                if convert_to_unit:
                    high_conv = high["pint"].to(convert_to_unit)
                    used_unit = str(high_conv.units)
                    normalized["high"] = {"comparator": high["comparator"], "value": float(high_conv.magnitude), "unit": used_unit}
                else:
                    normalized["high"] = {"comparator": high["comparator"], "value": float(high["pint"].magnitude), "unit": str(high["pint"].units)}
            except UndefinedUnitError as e:
                raise ReferenceRangeValidationError(f"High: unité inconnue pour pint: {e}") from e
        elif high["numeric"] is None and (range_high is not None):
            normalized["high"] = {"comparator": high["comparator"], "value": None, "unit": high["unit"]}

    if range_text is not None:
        normalized["text"] = range_text

    # Build final FHIR referenceRange list with one element
    final = [{"low": normalized.get("low"), "high": normalized.get("high"), "text": normalized.get("text")}]

    # Remove keys that are None to keep compact FHIR structure
    rr0 = final[0]
    rr0 = {k: v for k, v in rr0.items() if v is not None}
    return [rr0]


if __name__ == "__main__":
    raw = {
        "range_low": {"comparator": ">", "value": "2", "unit": "kg"},
        "range_high": {"comparator": "<", "value": "20", "unit": "kg"},
        "range_text": "test de force"
    }
    out = build_range_validated(
        range_low=raw.get("range_low"),
        range_high=raw.get("range_high"),
        range_text=range_text
    )
    import json
    print(json.dumps(out, indent=2, ensure_ascii=False))
