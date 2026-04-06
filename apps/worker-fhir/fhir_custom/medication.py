from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path
from typing import Any, Optional, Union

from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.medication  import Medication
from pydantic_core import from_json

logger = logging.getLogger(__name__)


# Function to extract code
def _extract_medication_code(
    raw: dict[str, Any], 
    parent_context: Optional[dict[str, Any]] = None
) -> Optional[str]:
    """
    Extract the medication_code from the raw data or the parent_context.
    """
    # 1) raw format
    medication_code = raw.get("code_code")
    if medication_code:
        return medication_code

    # 2) format FHIR / pré-FHIR
    code = raw.get("code")
    if hasattr(code, "coding") and code.coding:
        first = code.coding[0]
        if getattr(first, "code", None):
            return first.code

    if isinstance(code, dict):
        coding = code.get("coding")
        if isinstance(coding, list) and coding:
            first = coding[0]
            if isinstance(first, dict) and first.get("code"):
                return first["code"]

    # 3) fallback parent_context
    if parent_context:
        medication_code = parent_context.get("code_code")
        if medication_code:
            return medication_code

        code = parent_context.get("code")
        if isinstance(code, dict):
            coding = code.get("coding")
            if isinstance(coding, list) and coding:
                first = coding[0]
                if isinstance(first, dict) and first.get("code"):
                    return first["code"]

    return None


# Function to extract display
def _extract_medication_display(
    raw: dict[str, Any], 
    parent_context: Optional[dict[str, Any]] = None
) -> Optional[str]:
    """
    Extract the medication_display from the raw data or the parent_context.
    """
    # 1) raw format
    medication_display = raw.get("code_display")
    if medication_display:
        return medication_display

    # 2) format FHIR / pré-FHIR
    code = raw.get("code")
    if hasattr(code, "coding") and code.coding:
        first = code.coding[0]
        if getattr(first, "display", None):
            return first.display

    if isinstance(code, dict):
        coding = code.get("coding")
        if isinstance(coding, list) and coding:
            first = coding[0]
            if isinstance(first, dict) and first.get("display"):
                return first["display"]

    # 3) fallback parent_context
    if parent_context:
        medication_display = parent_context.get("code_display")
        if medication_display:
            return medication_display

        code = parent_context.get("code")
        if isinstance(code, dict):
            coding = code.get("coding")
            if isinstance(coding, list) and coding:
                first = coding[0]
                if isinstance(first, dict) and first.get("display"):
                    return first["display"]

    return None

# Function to resolve hash fields
def resolve_hash_fields(
    raw: dict[str, Any],
    parent_context: Optional[dict[str, Any]] = None,
) -> tuple[str, str, Union[str, datetime], Optional[Union[str, float, int]]]:
    """
    Extract medication_code and display from the raw data or the parent_context.
    """
    medication_code = _extract_medication_code(raw, parent_context)
    medication_display = _extract_medication_display(raw, parent_context)

    if not medication_code:
        raise ValueError("medication_code introuvable ni dans raw ni dans parent_context.")
    if not medication_display:
        raise ValueError("medication_display introuvable ni dans raw ni dans parent_context.")

    return medication_code, medication_display

# Function to build hash
def build_medication_hash(
    medication_code: str,
    medication_display: str
) -> str:
    """
    Build a hash from medication_code and medication_display.
    """
    medication_code_norm = medication_code.strip().lower()
    medication_display_norm = medication_display.strip().lower()

    canonical_string = f"{medication_code_norm}|{medication_display_norm}"
    return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

# Function to build CodeableConcept
def _codeable(
    system: Optional[str] = None,
    code: Optional[str] = None,
    display: Optional[str] = None,
    text: Optional[str] = None,
) -> CodeableConcept:
    """
    Create a CodeableConcept object.
    """
    return CodeableConcept(
        coding=[
            Coding(
                system=system,
                code=code,
                display=display,
            )
        ],
        text=text,
    )


# Function to build Medication kwargs
def _build_medication_args(
    raw: dict[str, Any],
    parent_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Retrieve raw data and build the Medication kwargs.
    """
    if not isinstance(raw, dict):
        raise TypeError(f"raw doit être un dict, reçu {type(raw)}")

    raw = raw.copy()
    med_kwargs: dict[str, Any] = {"status": raw.get("status") or "active"}

    # code
    if (
        raw.get("code_system") is not None
        or raw.get("code_code") is not None
        or raw.get("code_display") is not None
        or raw.get("code_text") is not None
    ):
        med_kwargs["code"] = _codeable(
            system=raw.get("code_system"),
            code=raw.get("code_code"),
            display=raw.get("code_display"),
            text=raw.get("code_text"),
        )

    # meta.tag
    if raw.get("tag_system") is not None or raw.get("tag_code") is not None:
        med_kwargs.setdefault("meta", {})
        med_kwargs["meta"].setdefault("tag", [])
        med_kwargs["meta"]["tag"].append(
            {
                "system": raw.get("tag_system"),
                "code": raw.get("tag_code"),
            }
        )

    # Makes hash
    medication_code, medication_display = resolve_hash_fields(
        raw=raw,
        parent_context=parent_context,
    )

    med_hash = build_medication_hash(
        medication_code=medication_code,
        medication_display=medication_display,
    )

    if raw.get("identifier_value") is not None:
        med_kwargs["identifier"] = [
        {
            "system": "https://phylcero.fr/fhir/identifier/source-medication",
            "value": raw.get("identifier_value"),
        }
    ]
    else:
        med_kwargs["identifier"] = [
            {
                "system": "https://phylcero.fr/fhir/identifier/source-medication",
                "value": med_hash,
            }
        ]
    

    return med_kwargs

# Function to build a FHIR Medication
def to_fhir_medication(
    raw: Union[dict[str, Any], str],
    parent_context: Optional[dict[str, Any]] = None,
) -> Medication:
    """
    Build a FHIR Medication from:
    - a raw dict
    - a JSON file path
    """
    if isinstance(raw, dict):
        data = raw

    elif isinstance(raw, str):
        file_path = Path(raw)
        if not file_path.is_file():
            raise FileNotFoundError(f"Fichier non trouvé : {file_path!s}")

        json_bytes = file_path.read_bytes()
        try:
            data = from_json(json_bytes)
        except Exception as exc:
            raise ValueError(
                f"Erreur de décodage JSON dans {file_path!s} : {exc}"
            ) from exc

    else:
        raise TypeError("raw doit être un dict ou le chemin d’un fichier JSON.")

    med_kwargs = _build_medication_args(data, parent_context=parent_context)
    return Medication(**med_kwargs)

# Function to build a list of FHIR Medications
def list_to_fhir_medication(
    raw: list[dict[str, Any]],
    total_created: int = 0,
) -> tuple[list[Medication], int]:
    """
    Build a list of FHIR Medication from a list of dict inputs.

    Returns:
        (med_list, total_created)
    """
    if not isinstance(raw, list):
        raise TypeError("raw doit être une liste de dictionnaires.")

    med_list: list[Medication] = []

    for data in raw:
        if not isinstance(data, dict):
            logger.exception(f"Élément ignoré car ce n'est pas un dict: {data}")
            total_created += 1
            continue

        try:
            med_kwargs = _build_medication_args(data)
            med_kwargs["id"] = str(uuid.uuid4())
            med_list.append(Medication(**med_kwargs))
        except Exception:
            logger.exception(
                f"Validation error for medication #{total_created} with data={data}")

        total_created += 1

    return med_list, total_created