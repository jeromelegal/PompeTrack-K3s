from typing import List, Dict, Any
from decimal import Decimal, InvalidOperation
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.quantity import Quantity
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  

class ComponentValidationError(ValueError):
    pass

def _to_float(value: Any) -> float:
    if value is None:
        raise ComponentValidationError("value is None")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            raise ComponentValidationError("value string empty")
        try:
            return float(s)
        except ValueError:
            try:
                return float(Decimal(s))
            except (InvalidOperation, ValueError):
                raise ComponentValidationError(f"Impossible de convertir en float: {value!r}")
    raise ComponentValidationError(f"Type de 'value' non supporté: {type(value)}")

def _model_dump_safe(m):
    """Utilitaire pour sérialiser un modèle pydantic FHIR selon la version."""
    try:
        return m.model_dump()
    except AttributeError:
        return m.dict()

def build_components_validated(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transforme une liste de dicts simples en liste 'component' FHIR validée.
    Input expected example element:
    {
      "code_system": "http://loinc.org",
      "code_code": "41981-2",
      "code_display": "Energy expended",
      "value_value": "42",
      "value_unit": "kJ",
      "inter_system": "http://example.org",
      "inter_code": "123-456",
      "inter_display": "example"
    }
    Returns list of component dicts ready for Observation.component.
    Raises ComponentValidationError on invalid input.
    """
    if not isinstance(raw, list):
        raise ComponentValidationError("raw doit être une liste")

    components_out: List[Dict[str, Any]] = []

    for idx, rc in enumerate(raw):
        if not isinstance(rc, dict):
            raise ComponentValidationError(f"component[{idx}] doit être un dict")

        # logger.debug(f"Processing component : {rc} ")
        
        comp_out: Dict[str, Any] = {}

        # --- code (CodeableConcept with Coding[]) ---
        code_system = rc.get(f"code_system[{idx}]")
        # logger.debug(f"CodeableConept on component {idx} - get code_system : {code_system}")
        code_code = rc.get(f"code_code[{idx}]")
        # logger.debug(f"CodeableConept on component {idx} - get code_code : {code_code}")
        code_display = rc.get(f"code_display[{idx}]")
        # logger.debug(f"CodeableConept on component {idx} - get code_display : {code_display}")

        if code_system or code_code or code_display:
            # require at least code or system ideally; we will allow partial but validate via fhir model
            coding = {}
            if code_system is not None:
                coding["system"] = code_system
            if code_code is not None:
                coding["code"] = code_code
            if code_display is not None:
                coding["display"] = code_display

            try:
                # logger.debug(f"Try CodeableConept on component {idx}")
                cc = CodeableConcept(coding=[Coding(**coding)])
            except ValidationError as e:
                raise ComponentValidationError(f"component[{idx}].code invalide: {e}") from e
            comp_out["code"] = _model_dump_safe(cc)
        else:
            # If totally missing code, it's unusual for a component, but we allow if user expects
            raise ComponentValidationError(f"component[{idx}]: champs code_* manquants (au moins un requis)")

        # --- valueQuantity (optional) ---
        vv = rc.get(f"value_value[{idx}]")
        unit = rc.get(f"value_unit[{idx}]")
        if vv is not None:
            try:
                numeric = _to_float(vv)
            except ComponentValidationError as e:
                raise ComponentValidationError(f"component[{idx}].value_value invalide: {e}") from e

            q_kwargs = {"value": numeric}
            if unit is not None:
                q_kwargs["unit"] = unit
            try:
                q = Quantity(**q_kwargs)
            except ValidationError as e:
                raise ComponentValidationError(f"component[{idx}].valueQuantity invalide: {e}") from e
            comp_out["valueQuantity"] = _model_dump_safe(q)
            # logger.debug(f"valueQuantity components {idx} is : {comp_out['valueQuantity']}")

        # --- interpretation (optional) : built from inter_* keys ---
        inter_system = rc.get(f"inter_system[{idx}]")
        inter_code = rc.get(f"inter_code[{idx}]")
        inter_display = rc.get(f"inter_display[{idx}]")

        if inter_system or inter_code or inter_display:
            codings: List[Coding] = []

            # Cas 1 : inter_display est une liste -> plusieurs Coding
            if isinstance(inter_display, list):
                for val in inter_display:
                    if not isinstance(val, str):
                        raise ComponentValidationError(
                            f"component[{idx}].inter_display contient un élément non string: {val!r}"
                        )
                    coding_kwargs = {
                        "code": val,
                        "display": val
                    }
                    if inter_system is not None:
                        coding_kwargs["system"] = inter_system

                    try:
                        codings.append(Coding(**coding_kwargs))
                    except ValidationError as e:
                        raise ComponentValidationError(
                            f"component[{idx}].interpretation.coding invalide: {e}"
                        ) from e

            # Cas 2 : inter_display est une string (comportement historique)
            else:
                coding_kwargs = {}
                if inter_system is not None:
                    coding_kwargs["system"] = inter_system
                if inter_code is not None:
                    coding_kwargs["code"] = inter_code
                if inter_display is not None:
                    coding_kwargs["display"] = inter_display

                try:
                    codings.append(Coding(**coding_kwargs))
                except ValidationError as e:
                    raise ComponentValidationError(
                        f"component[{idx}].interpretation invalide: {e}"
                    ) from e

            try:
                interp_cc = CodeableConcept(coding=codings)
            except ValidationError as e:
                raise ComponentValidationError(
                    f"component[{idx}].interpretation invalide: {e}"
                ) from e

            comp_out["interpretation"] = [_model_dump_safe(interp_cc)]

        # Append normalized component
        components_out.append(comp_out)

    return components_out

# -------------------------
# Exemple d'utilisation
if __name__ == "__main__":
    raw = [
        {
            "code_system": "http://loinc.org",
            "code_code": "41981-2",
            "code_display": "Energy expended",
            "value_value": "42",
            "value_unit": "kJ",
            "inter_system": "http://example.org",
            "inter_code": "123-456",
            "inter_display": "test"
        }
    ]
    comps = build_components_validated(raw)
    import json
    print(json.dumps({"component": comps}, indent=2, ensure_ascii=False))
