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
from fhir.resources.observation import Observation
from pydantic_core import from_json

from fhir_custom.component import build_components_validated
from fhir_custom.range import build_range_validated
from fhir_custom.valuequantity import value_quantity

logger = logging.getLogger(__name__)

def _extract_patient_id(raw: dict[str, Any], parent_context: Optional[dict[str, Any]] = None) -> Optional[str]:
    # 1) format brut
    patient_id = raw.get("patient_id")
    if patient_id:
        return patient_id

    # 2) format FHIR / pré-FHIR
    subject = raw.get("subject")
    if isinstance(subject, dict):
        ref = subject.get("reference")
        if isinstance(ref, str) and ref.startswith("Patient/"):
            return ref.split("/", 1)[1]

    # 3) fallback parent_context
    if parent_context:
        patient_id = parent_context.get("patient_id")
        if patient_id:
            return patient_id

        subject = parent_context.get("subject")
        if isinstance(subject, dict):
            ref = subject.get("reference")
            if isinstance(ref, str) and ref.startswith("Patient/"):
                return ref.split("/", 1)[1]

    return None


def _extract_timestamp(
    raw: dict[str, Any],
    parent_context: Optional[dict[str, Any]] = None,
) -> Optional[Union[str, datetime]]:
    # 1) format brut
    timestamp = raw.get("effectiveDateTime") or raw.get("periodstart") or raw.get("date") or raw.get("start")
    if timestamp is not None:
        return timestamp

    # 2) format FHIR / pré-FHIR
    effective_period = raw.get("effectivePeriod")
    if isinstance(effective_period, dict):
        timestamp = effective_period.get("start")
        if timestamp is not None:
            return timestamp

    # 3) fallback parent_context
    if parent_context:
        timestamp = (
            parent_context.get("effectiveDateTime")
            or parent_context.get("periodstart")
            or parent_context.get("date")
            or parent_context.get("start")
        )
        if timestamp is not None:
            return timestamp

        effective_period = parent_context.get("effectivePeriod")
        if isinstance(effective_period, dict):
            timestamp = effective_period.get("start")
            if timestamp is not None:
                return timestamp

    return None


def _extract_measurement_type(raw: dict[str, Any], parent_context: Optional[dict[str, Any]] = None) -> Optional[str]:
    # 1) format brut
    measurement_type = raw.get("code_code")
    if measurement_type:
        return measurement_type

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
        measurement_type = parent_context.get("code_code")
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


def resolve_hash_fields(
    raw: dict[str, Any],
    parent_context: Optional[dict[str, Any]] = None,
) -> tuple[str, str, Union[str, datetime], Optional[Union[str, float, int]]]:
    patient_id = _extract_patient_id(raw, parent_context)
    measurement_type = _extract_measurement_type(raw, parent_context)
    timestamp = _extract_timestamp(raw, parent_context)
    value = raw.get("value_value")

    if value is None:
        value_quantity = raw.get("valueQuantity")
        if isinstance(value_quantity, dict):
            value = value_quantity.get("value")

    if value is None:
        value = raw.get("valueString")

    if not patient_id:
        raise ValueError("patient_id introuvable ni dans raw ni dans parent_context.")
    if not measurement_type:
        raise ValueError("measurement_type introuvable ni dans raw ni dans parent_context.")
    if timestamp is None:
        raise ValueError("timestamp introuvable ni dans raw ni dans parent_context.")

    return patient_id, measurement_type, timestamp, value

def to_fhir_datetime(value: Union[str, datetime]) -> str:
    """
    Convertit une date en chaîne ISO stable pour le hash.
    """
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace(" ", "T"))
        except ValueError:
            dt = parser.parse(value)
    elif isinstance(value, datetime):
        dt = value
    else:
        raise TypeError(f"timestamp doit être str ou datetime, reçu {type(value)}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    iso_str = dt.isoformat(timespec="seconds")
    if iso_str.endswith("+00:00"):
        iso_str = iso_str[:-6] + "Z"
    return iso_str

def normalize_value(value: Optional[Union[str, float, int]]) -> str:
    """
    None -> ""
    float -> représentation stable
    sinon -> str nettoyée en lowercase
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value).strip().lower()

def build_observation_hash(
    patient_id: str,
    measurement_type: str,
    timestamp: Union[str, datetime],
    value: Optional[Union[str, float, int]] = None,
) -> str:
    """
    Hash toujours calculable si patient_id, measurement_type et timestamp sont présents.
    value est optionnelle.
    """
    patient_id_norm = patient_id.strip().lower()
    measurement_type_norm = measurement_type.strip().lower()
    timestamp_norm = to_fhir_datetime(timestamp)
    value_norm = normalize_value(value)

    canonical_string = f"{patient_id_norm}|{measurement_type_norm}|{timestamp_norm}|{value_norm}"
    return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()


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


def iso_to_dt(iso_value: str) -> datetime:
    return parser.isoparse(iso_value)


def _coding_list(codings: Optional[Union[list[str], str]] = None) -> dict[str, list[dict[str, str]]]:
    """
    Create a coding list structure:
    {"coding": [{"code": "...", "display": "..."}]}
    """
    coding: list[dict[str, str]] = []

    if codings:
        if isinstance(codings, str):
            codings = [codings]
        elif not isinstance(codings, list):
            raise TypeError(f"codings doit être une liste ou une str, reçu {type(codings)}")

        for code in codings:
            coding.append({"code": str(code), "display": str(code)})

    return {"coding": coding}


def _coding_bodysite(data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Create a bodySite structure:
    {"coding": [...], "text": "..."}
    """
    if not isinstance(data, dict):
        raise TypeError(f"bodysite doit être un dict, reçu: {type(data)}")

    return {
        "coding": [
            {
                "system": data.get("system"),
                "code": data.get("code") or data.get("display"),
                "display": data.get("display") or data.get("code"),
            }
        ],
        "text": data.get("text"),
    }


def _build_obs_args(
    raw: dict[str, Any],
    parent_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Retrieve raw data and build the Observation kwargs.
    """
    if not isinstance(raw, dict):
        raise TypeError(f"raw doit être un dict, reçu {type(raw)}")

    raw = raw.copy()
    obs_kwargs: dict[str, Any] = {"status": raw.get("status") or "final"}

    # effectiveDateTime
    if raw.get("effectiveDateTime") is not None:
        obs_kwargs["effectiveDateTime"] = to_fhir_datetime(raw.get("effectiveDateTime"))

    # effectivePeriod
    if raw.get("periodstart") is not None and raw.get("periodend") is not None:
        start = to_fhir_datetime(raw.get("periodstart"))
        end = to_fhir_datetime(raw.get("periodend"))

        obs_kwargs["effectivePeriod"] = {"start": start, "end": end}

        delta = iso_to_dt(end) - iso_to_dt(start)
        if raw.get("code_code") == "sleep_analysis":
            raw["value_value"] = delta.total_seconds() / 3600

    # category
    if (
        raw.get("cat_system") is not None
        or raw.get("cat_code") is not None
        or raw.get("cat_display") is not None
        or raw.get("cat_text") is not None
    ):
        obs_kwargs["category"] = [
            _codeable(
                system=raw.get("cat_system"),
                code=raw.get("cat_code"),
                display=raw.get("cat_display"),
                text=raw.get("cat_text"),
            )
        ]

    # code
    if (
        raw.get("code_system") is not None
        or raw.get("code_code") is not None
        or raw.get("code_display") is not None
        or raw.get("code_text") is not None
    ):
        obs_kwargs["code"] = _codeable(
            system=raw.get("code_system"),
            code=raw.get("code_code"),
            display=raw.get("code_display"),
            text=raw.get("code_text"),
        )

    # valueCodeableConcept
    if (
        raw.get("vcc_system") is not None
        or raw.get("vcc_code") is not None
        or raw.get("vcc_display") is not None
        or raw.get("vcc_text") is not None
    ):
        obs_kwargs["valueCodeableConcept"] = _codeable(
            system=raw.get("vcc_system"),
            code=raw.get("vcc_code"),
            display=raw.get("vcc_display"),
            text=raw.get("vcc_text"),
        )

    # subject
    if raw.get("patient_id") is not None:
        obs_kwargs["subject"] = {"reference": f"Patient/{raw.get('patient_id')}"}

    # performer
    if raw.get("performer_id") is not None:
        obs_kwargs["performer"] = [{"reference": f"Patient/{raw.get('performer_id')}"}]

    # interpretation
    if (
        raw.get("interpret_system") is not None
        or raw.get("interpret_code") is not None
        or raw.get("interpret_display") is not None
        or raw.get("interpret_text") is not None
    ):
        obs_kwargs["interpretation"] = [
            _codeable(
                system=raw.get("interpret_system"),
                code=raw.get("interpret_code"),
                display=raw.get("interpret_display"),
                text=raw.get("interpret_text"),
            )
        ]

    # note
    if raw.get("note_text") is not None:
        note_text = raw.get("note_text")

        if isinstance(note_text, str):
            obs_kwargs["note"] = [{"text": note_text}]
        elif isinstance(note_text, list):
            obs_kwargs["note"] = [{"text": str(note)} for note in note_text]
        else:
            raise TypeError(
                f"note_text doit être une str ou une liste, reçu {type(note_text)}"
            )

    # bodySite
    if raw.get("bodysite") is not None:
        obs_kwargs["bodySite"] = _coding_bodysite(data=raw.get("bodysite"))

    # valueString
    if raw.get("value_string") is not None:
        obs_kwargs["valueString"] = raw.get("value_string")

    # method
    if raw.get("method") is not None:
        obs_kwargs["method"] = _coding_list(codings=raw.get("method"))

    # device
    if raw.get("device_id") is not None:
        obs_kwargs["device"] = {"reference": f"Device/{raw.get('device_id')}"}

    # referenceRange
    if (
        raw.get("range_low") is not None
        or raw.get("range_high") is not None
        or raw.get("range_text") is not None
    ):
        obs_kwargs["referenceRange"] = build_range_validated(
            range_low=raw.get("range_low"),
            range_high=raw.get("range_high"),
            range_text=raw.get("range_text"),
        )

    # component
    if raw.get("component") is not None:
        obs_kwargs["component"] = build_components_validated(raw=raw.get("component"))

    # valueQuantity
    if raw.get("value_value") is not None or raw.get("value_unit") is not None:
        obs_kwargs["valueQuantity"] = value_quantity(
            value=raw.get("value_value"),
            unit=raw.get("value_unit"),
        )

    # meta.tag
    if raw.get("tag_system") is not None or raw.get("tag_code") is not None:
        obs_kwargs.setdefault("meta", {})
        obs_kwargs["meta"].setdefault("tag", [])
        obs_kwargs["meta"]["tag"].append(
            {
                "system": raw.get("tag_system"),
                "code": raw.get("tag_code"),
            }
        )

    # hasMember
    if raw.get("hasMember") is not None:
        obs_kwargs["hasMember"] = raw.get("hasMember")

    # Makes hash
    patient_id, measurement_type, hash_timestamp, value_for_hash = resolve_hash_fields(
        raw=raw,
        parent_context=parent_context,
    )

    obs_hash = build_observation_hash(
        patient_id=patient_id,
        measurement_type=measurement_type,
        timestamp=hash_timestamp,
        value=value_for_hash,
    )

    obs_kwargs["identifier"] = [
        {
            "system": "https://medplum.phylcero.fr/observation-hash",
            "value": obs_hash,
        }
    ]

    return obs_kwargs


def to_fhir_observation(
    raw: Union[dict[str, Any], str],
    parent_context: Optional[dict[str, Any]] = None,
) -> Observation:
    """
    Build a FHIR Observation from:
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

    obs_kwargs = _build_obs_args(data, parent_context=parent_context)
    return Observation(**obs_kwargs)


def list_to_fhir_observation(
    raw: list[dict[str, Any]],
    total_created: int = 0,
) -> tuple[list[Observation], int]:
    """
    Build a list of FHIR Observations from a list of dict inputs.

    Returns:
        (obs_list, total_created)
    """
    if not isinstance(raw, list):
        raise TypeError("raw doit être une liste de dictionnaires.")

    obs_list: list[Observation] = []

    for data in raw:
        if not isinstance(data, dict):
            logger.exception("Élément ignoré car ce n'est pas un dict: %r", data)
            total_created += 1
            continue

        try:
            obs_kwargs = _build_obs_args(data)
            obs_kwargs["id"] = str(uuid.uuid4())
            obs_list.append(Observation(**obs_kwargs))
        except Exception:
            logger.exception(
                "Validation error for observation #%s with data=%r",
                total_created,
                data,
            )

        total_created += 1

    return obs_list, total_created