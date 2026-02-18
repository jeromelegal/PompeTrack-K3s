from typing import Union, Optional
from pydantic_core import ValidationError
from fhir.resources.quantity import Quantity
from typing import Any
from decimal import Decimal, InvalidOperation

class ValueQuantityValidationError(ValueError):
    pass

def _to_float(value: Any) -> float:
    """
    Transform in float
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


def _model_dump_safe(m):
    """Utilitaire pour sérialiser un modèle pydantic FHIR selon la version."""
    try:
        return m.model_dump()
    except AttributeError:
        return m.dict()


def value_quantity(
    value: Union[int, float, str],
    unit: Optional[str] = None
) -> dict:
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
