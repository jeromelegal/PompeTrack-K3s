from datetime import date, datetime, timedelta, timezone

from serializers import get_recent_metrics as fetch_recent_metrics
from serializers import get_recent_symptoms as fetch_recent_symptoms
from serializers import get_medication_intake_history
from serializers import simplify_observation



def tool_get_recent_metrics(days: int = 30) -> list[dict]:
    observations = fetch_recent_metrics(days=days)
    return [simplify_observation(obs) for obs in observations]


def tool_get_recent_medication(days: int = 30) -> list[dict]:
    return get_medication_intake_history(days=days)


def get_recent_symptoms(days: int = 30) -> list[dict]:
    return fetch_recent_symptoms(days=days)


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
) -> dict:
    events = []
    events.extend(_timeline_event("metric", metric) for metric in metrics)
    events.extend(_timeline_event("medication", medication) for medication in medications)
    events.extend(_timeline_event("symptom", symptom) for symptom in symptoms)
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
            "events": len(events),
        },
        "events": events,
    }


def get_health_timeline(days: int = 14) -> dict:
    days = max(1, min(days, 90))

    metrics = tool_get_recent_metrics(days=days)
    medications = tool_get_recent_medication(days=days)
    symptoms = get_recent_symptoms(days=days)

    return _build_health_timeline(days, metrics, medications, symptoms)


def create_health_summary(days: int = 30) -> dict:
    days = max(1, min(days, 90))

    metrics = _sort_by_date_desc(tool_get_recent_metrics(days=days))
    medications = _sort_by_date_desc(tool_get_recent_medication(days=days))
    symptoms = _sort_by_date_desc(get_recent_symptoms(days=days))

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
            "activeSymptoms": len(active_symptoms),
        },
        "latestMetrics": list(latest_metrics_by_code.values()),
        "recentSymptoms": symptoms[:10],
        "activeSymptoms": active_symptoms[:10],
        "recentMedication": medications[:10],
        "timeline": _build_health_timeline(days, metrics, medications, symptoms),
    }
