from datetime import date, datetime, timedelta, timezone
from typing import Callable

from app.medplum.serializers import get_recent_metrics
from app.medplum.serializers import get_recent_manual_monthly
from app.medplum.serializers import get_recent_spirometry
from app.medplum.serializers import get_recent_stateofminds
from app.medplum.serializers import get_recent_symptoms
from app.medplum.serializers import get_recent_workouts
from app.medplum.serializers import get_medication_intake_history
from app.medplum.serializers import simplify_observation


def _get_recent_for_model(
    fetcher: Callable[..., list[dict]],
    *,
    days: int,
    serializer: Callable[[dict], dict] | None = None,
) -> list[dict]:
    rows = fetcher(days=days)
    if serializer is None:
        return rows

    return [serializer(row) for row in rows]


def tool_get_recent_metrics(days: int = 30) -> list[dict]:
    return _get_recent_for_model(
        get_recent_metrics,
        days=days,
        serializer=simplify_observation,
    )


def tool_get_recent_medication(days: int = 30) -> list[dict]:
    return _get_recent_for_model(get_medication_intake_history, days=days)


def tool_get_recent_stateofminds(days: int = 30) -> list[dict]:
    return _get_recent_for_model(get_recent_stateofminds, days=days)


def tool_get_recent_workouts(days: int = 30) -> list[dict]:
    return _get_recent_for_model(get_recent_workouts, days=days)


def tool_get_recent_spirometry(days: int = 30) -> list[dict]:
    return _get_recent_for_model(get_recent_spirometry, days=days)


def tool_get_recent_manual_monthly(days: int = 30) -> list[dict]:
    return _get_recent_for_model(get_recent_manual_monthly, days=days)


def tool_get_recent_symptoms(days: int = 30) -> list[dict]:
    return _get_recent_for_model(get_recent_symptoms, days=days)


def _parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.min

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
        except ValueError:
            return datetime.min


def _event_date(item: dict) -> str | None:
    return item.get("date") or item.get("effectiveDateTime")


def _timeline_event(event_type: str, item: dict) -> dict:
    event = {
        "type": event_type,
        "date": _event_date(item),
        "id": item.get("id"),
    }

    if event_type == "metric":
        event.update({
            "label": item.get("display") or item.get("code"),
            "value": item.get("value"),
            "unit": item.get("unit"),
            "interpretation": item.get("interpretation"),
        })
    elif event_type == "medication":
        event.update({
            "label": item.get("medication"),
            "status": item.get("status"),
            "dosage": item.get("dosage"),
        })
    elif event_type == "symptom":
        event.update({
            "label": item.get("display") or item.get("code"),
            "severity": item.get("severity"),
            "clinicalStatus": item.get("clinicalStatus"),
            "source": item.get("source"),
        })
    elif event_type == "stateofmind":
        event.update({
            "label": item.get("display") or item.get("code"),
            "value": item.get("value"),
            "unit": item.get("unit"),
            "interpretation": item.get("interpretation"),
            "components": item.get("components"),
        })

    return event


def _sort_by_date_desc(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: _parse_date(_event_date(item)),
        reverse=True,
    )


def _build_health_timeline(
    days: int,
    metrics: list[dict],
    medications: list[dict],
    symptoms: list[dict],
    stateofminds: list[dict] | None = None,
) -> dict:
    stateofminds = stateofminds or []

    events = []
    events.extend(_timeline_event("metric", metric) for metric in metrics)
    events.extend(_timeline_event("medication", medication) for medication in medications)
    events.extend(_timeline_event("symptom", symptom) for symptom in symptoms)
    events.extend(_timeline_event("stateofmind", item) for item in stateofminds)
    events = _sort_by_date_desc([event for event in events if event.get("date")])

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    return {
        "period": {
            "days": days,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
        "counts": {
            "metrics": len(metrics),
            "medications": len(medications),
            "symptoms": len(symptoms),
            "stateofminds": len(stateofminds),
            "events": len(events),
        },
        "events": events,
    }


def get_health_timeline(days: int = 14) -> dict:
    days = max(1, min(days, 90))

    metrics = get_recent_metrics(days=days)
    medications = get_recent_medication(days=days)
    symptoms = get_recent_symptoms(days=days)
    stateofminds = get_recent_stateofminds(days=days)

    return _build_health_timeline(days, metrics, medications, symptoms, stateofminds)


def create_health_summary(days: int = 30) -> dict:
    days = max(1, min(days, 90))

    metrics = _sort_by_date_desc(get_recent_metrics(days=days))
    medications = _sort_by_date_desc(get_recent_medication(days=days))
    symptoms = _sort_by_date_desc(get_recent_symptoms(days=days))
    stateofminds = _sort_by_date_desc(get_recent_stateofminds(days=days))

    latest_metrics_by_code = {}
    for metric in metrics:
        key = metric.get("code") or metric.get("display") or metric.get("id")
        if key and key not in latest_metrics_by_code:
            latest_metrics_by_code[key] = metric

    active_symptoms = [
        symptom for symptom in symptoms
        if not symptom.get("abatementDate")
        and (symptom.get("clinicalStatus") or "").lower() not in {"inactive", "resolved"}
    ]

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    return {
        "period": {
            "days": days,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
        "counts": {
            "metrics": len(metrics),
            "medications": len(medications),
            "symptoms": len(symptoms),
            "stateofminds": len(stateofminds),
            "activeSymptoms": len(active_symptoms),
        },
        "latestMetrics": list(latest_metrics_by_code.values()),
        "recentStateOfMinds": stateofminds[:10],
        "recentSymptoms": symptoms[:10],
        "activeSymptoms": active_symptoms[:10],
        "recentMedication": medications[:10],
        "timeline": _build_health_timeline(
            days,
            metrics,
            medications,
            symptoms,
            stateofminds,
        ),
    }
