from typing import Union, Optional
from pydantic_core import ValidationError
from fhir.resources.quantity import Quantity
from typing import Any
from decimal import Decimal, InvalidOperation

# Exceptions
class ValueQuantityValidationError(ValueError):
    pass

# Function to transform any value in float
def _to_float(value: Any) -> float:
    """
    Transform any value in float
    """
    if value is None:
        raise ValueQuantityValidationError("value is None")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            raise ValueQuantityValidationError("value string empty")
        try:
            return float(s)
        except ValueError:
            try:
                return float(Decimal(s))
            except (InvalidOperation, ValueError):
                raise ValueQuantityValidationError(f"Impossible de convertir en float: {value!r}")
    raise ValueQuantityValidationError(f"Type de 'value' non supporté: {type(value)}")

# Function to serialize a pydantic FHIR model
def _model_dump_safe(m):
    """
    Serialize any pydantic model.
    """
    try:
        return m.model_dump()
    except AttributeError:
        return m.dict()

# Function to create value
def value_quantity(
    value: Union[int, float, str],
    unit: Optional[str] = None
) -> dict:
    """
    Creates valueQuantity from any value
    """
    if value is None:
        raise ValueQuantityValidationError("value absente ou incorrecte")
    try:
        numeric = _to_float(value)
    except ValueQuantityValidationError as e:
        raise ValueQuantityValidationError(f"value invalide: {e}") from e

    q_kwargs = {"value": numeric}
    if unit is not None:
        q_kwargs["unit"] = unit

    try:
        q = Quantity(**q_kwargs)
    except ValidationError as e:
        raise ValueQuantityValidationError(f"valueQuantity invalide: {e}") from e

    return _model_dump_safe(q)
