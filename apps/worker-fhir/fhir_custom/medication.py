from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from dateutil import parser
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.medication  import Medication
from pydantic_core import from_json

logger = logging.getLogger(__name__)



def _extract_medication_code(
    raw: dict[str, Any], 
    parent_context: Optional[dict[str, Any]] = None
) -> Optional[str]:
    """
    Extract the medication_code from the raw data or the parent_context.
    """
    # 1) raw format
    medication_code = raw.get("medication_code")
    if medication_code:
        return medication_code

    # 2) format FHIR / pré-FHIR
    code = raw.get("medicationCodeableConcept")
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
        measurement_type = parent_context.get("medication_code")
        if measurement_type:
            return measurement_type

        code = parent_context.get("code")
        if isinstance(code, dict):
            coding = code.get("coding")
            if isinstance(coding, list) and coding:
                first = coding[0]
                if isinstance(first, dict) and first.get("code"):
                    return first["code"]

    return None


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
    med_kwargs: dict[str, Any] = {"status": raw.get("status") or "completed"}

    # effectiveDateTime
    if raw.get("effectiveDateTime") is not None:
        med_kwargs["effective"] = to_fhir_datetime(raw.get("effectiveDateTime"))

    # effectivePeriod
    if raw.get("periodstart") is not None and raw.get("periodend") is not None:
        start = to_fhir_datetime(raw.get("periodstart"))
        end = to_fhir_datetime(raw.get("periodend"))

        med_kwargs["effectivePeriod"] = {"start": start, "end": end}
        delta = iso_to_dt(end) - iso_to_dt(start)

    # medicationCodeableConcept
    if (
        raw.get("medication_system") is not None
        or raw.get("medication_code") is not None
        or raw.get("medication_display") is not None
        or raw.get("medication_text") is not None
    ):
        med_kwargs["medication"] = _codeable(
            system=raw.get("medication_system"),
            code=raw.get("medication_code"),
            display=raw.get("medication_display"),
            text=raw.get("medication_text"),
        )

    # statusReason
    if (
        raw.get("status_system") is not None
        or raw.get("status_code") is not None
        or raw.get("status_display") is not None
        or raw.get("status_text") is not None
    ):
        med_kwargs["statusReason"] = _codeable(
            system=raw.get("status_system"),
            code=raw.get("status_code"),
            display=raw.get("status_display"),
            text=raw.get("status_text"),
        )

    # subject
    if raw.get("patient_id") is not None:
        med_kwargs["subject"] = {"reference": f"Patient/{raw.get('patient_id')}"}

    # performer
    if raw.get("performer_id") is not None:
        med_kwargs["performer"] = [{"reference": f"Patient/{raw.get('performer_id')}"}]

    # note
    if raw.get("note_text") is not None:
        note_text = raw.get("note_text")

        if isinstance(note_text, str):
            med_kwargs["note"] = [{"text": note_text}]
        elif isinstance(note_text, list):
            med_kwargs["note"] = [{"text": str(note)} for note in note_text]
        else:
            raise TypeError(
                f"note_text doit être une str ou une liste, reçu {type(note_text)}"
            )

    # dosage
    if raw.get("dose_value") is not None:
        med_kwargs["dosage"] = {"dose": {"value": raw.get("dose_value"), "unit": "count"}}

    # device
    if raw.get("device_id") is not None:
        med_kwargs["device"] = {"reference": f"Device/{raw.get('device_id')}"}

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

    # hasMember
    if raw.get("hasMember") is not None:
        med_kwargs["hasMember"] = raw.get("hasMember")

    # Makes hash
    patient_id, medication_code, hash_timestamp, value_for_hash = resolve_hash_fields(
        raw=raw,
        parent_context=parent_context,
    )

    med_hash = build_medication_hash(
        patient_id=patient_id,
        medication_code=medication_code,
        timestamp=hash_timestamp,
        value=value_for_hash,
    )

    med_kwargs["identifier"] = [
        {
            "system": "https://medplum.phylcero.fr/medication-hash",
            "value": med_hash,
        }
    ]

    return med_kwargs

# Function to build a FHIR MedicationAdministration
def to_fhir_medication(
    raw: Union[dict[str, Any], str],
    parent_context: Optional[dict[str, Any]] = None,
) -> MedicationAdministration:
    """
    Build a FHIR MedicationAdministration from:
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
    return MedicationAdministration(**med_kwargs)

# Function to build a list of FHIR Medications
def list_to_fhir_medication(
    raw: list[dict[str, Any]],
    total_created: int = 0,
) -> tuple[list[MedicationAdministration], int]:
    """
    Build a list of FHIR MedicationAdministration from a list of dict inputs.

    Returns:
        (med_list, total_created)
    """
    if not isinstance(raw, list):
        raise TypeError("raw doit être une liste de dictionnaires.")

    med_list: list[MedicationAdministration] = []

    for data in raw:
        if not isinstance(data, dict):
            logger.exception("Élément ignoré car ce n'est pas un dict: %r", data)
            total_created += 1
            continue

        try:
            med_kwargs = _build_obs_args(data)
            med_kwargs["id"] = str(uuid.uuid4())
            med_list.append(MedicationAdministration(**med_kwargs))
        except Exception:
            logger.exception(
                f"Validation error for medicationadministration #{total_created} with data={data}")

        total_created += 1

    return med_list, total_created