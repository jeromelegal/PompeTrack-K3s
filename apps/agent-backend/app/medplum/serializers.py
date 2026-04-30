from datetime import date, timedelta
from fetch_queries import (
    fetch_fhir_condition,
    fetch_fhir_medicationadministration,
    fetch_fhir_observation,
)
import os

MEDPLUM_PATIENT_ID = os.getenv("MEDPLUM_PATIENT_ID")


def _first_coding_value(codeable_concept: dict, key: str) -> str | None:
    coding = codeable_concept.get("coding", [])
    first_coding = coding[0] if coding else {}
    return first_coding.get(key)


def _codeable_display(codeable_concept: dict | None) -> str | None:
    if not isinstance(codeable_concept, dict):
        return None
    return (
        codeable_concept.get("text")
        or _first_coding_value(codeable_concept, "display")
        or _first_coding_value(codeable_concept, "code")
    )


def _codeable_code(codeable_concept: dict | None) -> str | None:
    if not isinstance(codeable_concept, dict):
        return None
    return _first_coding_value(codeable_concept, "code")


def simplify_observation(obs: dict) -> dict:
    code = obs.get("code", {})
    coding = code.get("coding", [])
    first_coding = coding[0] if coding else {}

    value_quantity = obs.get("valueQuantity") or {}

    return {
        "id": obs.get("id"),
        "date": obs.get("effectiveDateTime")
            or obs.get("effectivePeriod", {}).get("start"),
        "code": first_coding.get("code"),
        "display": first_coding.get("display") or code.get("text"),
        "value": value_quantity.get("value"),
        "unit": value_quantity.get("unit") or value_quantity.get("code"),
        "category": [
            c.get("text") or c.get("coding", [{}])[0].get("display")
            for c in obs.get("category", [])
        ],
        "interpretation": obs.get("interpretation"),
    }


def simplify_condition(condition: dict) -> dict:
    code = condition.get("code", {})

    return {
        "id": condition.get("id"),
        "date": condition.get("recordedDate")
            or condition.get("onsetDateTime")
            or condition.get("onsetPeriod", {}).get("start"),
        "code": _codeable_code(code),
        "display": _codeable_display(code),
        "severity": _codeable_display(condition.get("severity")),
        "clinicalStatus": _codeable_display(condition.get("clinicalStatus")),
        "verificationStatus": _codeable_display(condition.get("verificationStatus")),
        "category": [
            _codeable_display(c)
            for c in condition.get("category", [])
        ],
        "abatementDate": condition.get("abatementDateTime")
            or condition.get("abatementPeriod", {}).get("start"),
        "notes": [
            note.get("text")
            for note in condition.get("note", [])
            if note.get("text")
        ],
        "source": "condition",
    }


def get_recent_metrics(days: int = 30) -> list[dict]:
    days = max(1, min(days, 90))

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    return fetch_fhir_observation(
        patient=MEDPLUM_PATIENT_ID,
        payload={
            "tag": "metrics",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "max_records": 500,
            "page_count": 100,
            "max_pages": 20,
        },
    )


def get_recent_symptoms(days: int = 30) -> list[dict]:
    days = max(1, min(days, 90))

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    symptoms = [
        simplify_condition(condition)
        for condition in fetch_fhir_condition(
            patient=MEDPLUM_PATIENT_ID,
            payload={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "max_records": 500,
                "page_count": 100,
                "max_pages": 20,
            },
        )
    ]

    symptom_observations = fetch_fhir_observation(
        patient=MEDPLUM_PATIENT_ID,
        payload={
            "tag": "symptoms",
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "max_records": 500,
            "page_count": 100,
            "max_pages": 20,
        },
    )

    for obs in symptom_observations:
        symptom = simplify_observation(obs)
        symptom["source"] = "observation"
        symptoms.append(symptom)

    return sorted(
        symptoms,
        key=lambda item: item.get("date") or "",
        reverse=True,
    )


def simplify_medication_administration(medadmin: dict) -> dict:
    medication = medadmin.get("medicationReference")

    med_display = None
    if isinstance(medication, dict):
        med_display = medication.get("display")
        code = medication.get("code", {})
        med_display = med_display or code.get("text")

        if not med_display:
            coding = code.get("coding", [])
            if coding:
                med_display = coding[0].get("display")

    return {
        "id": medadmin.get("id"),
        "date": medadmin.get("effectiveDateTime")
            or medadmin.get("effectivePeriod", {}).get("start"),
        "status": medadmin.get("status"),
        "medication": med_display,
        "dosage": medadmin.get("dosage"),
    }


def get_medication_intake_history(days: int = 30) -> list[dict]:
    days = max(1, min(days, 90))

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    rows = fetch_fhir_medicationadministration(
        patient=MEDPLUM_PATIENT_ID,
        payload={
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "max_records": 500,
            "page_count": 100,
            "max_pages": 20,
        },
    )

    return [simplify_medication_administration(row) for row in rows]

