from __future__ import annotations

import argparse
import asyncio
import re
import json
import math
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.dependencies import get_services
from app.medplum.health_tools import (
    get_recent_medication,
    get_recent_manual_monthly,
    get_recent_metrics,
    get_recent_spirometry,
    get_recent_stateofminds,
    get_recent_symptoms,
    get_recent_workouts,
)
from app.telegram.notifier import notify_daily_health_review


WATCHLIST_DEFINITIONS = [
    {
        "id": "fatigue",
        "label": "Fatigue",
        "categories": ["symptoms"],
        "keywords": ["fatigue", "tired", "tiredness", "exhaust"],
    },
    {
        "id": "low_back_pain",
        "label": "Douleur lombaire",
        "categories": ["symptoms", "manualMonthly"],
        "keywords": ["bas du dos", "lomb", "low back", "back pain", "douleur dos"],
    },
    {
        "id": "spirometry",
        "label": "Spirométrie",
        "categories": ["spirometry"],
        "keywords": ["fev", "fvc", "pef", "vems", "spirom"],
    },
    {
        "id": "mood",
        "label": "Humeur",
        "categories": ["stateofminds"],
        "keywords": ["mood", "humeur", "state", "valence"],
    },
    {
        "id": "medication",
        "label": "Médicaments",
        "categories": ["medications"],
        "keywords": ["medication", "médicament", "traitement", "administration"],
    },
    {
        "id": "post_workout_recovery",
        "label": "Récupération après sport",
        "categories": ["workouts", "symptoms", "metrics"],
        "keywords": ["workout", "entraînement", "marche", "recovery", "fatigue"],
    },
]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _label(item: dict[str, Any]) -> str:
    return str(item.get("display") or item.get("code") or item.get("label") or "unknown")


def _normalized_label(value: str | None) -> str:
    return (value or "").lower()


def _matches_keywords(label: str | None, keywords: list[str]) -> bool:
    normalized = _normalized_label(label)
    return any(keyword in normalized for keyword in keywords)


def _metric_direction(label: str | None) -> str:
    normalized = _normalized_label(label)
    if any(token in normalized for token in ["step", "pas", "distance", "walking", "marche", "active energy"]):
        return "low_is_watch"
    if any(token in normalized for token in ["sleep", "sommeil"]):
        return "low_is_watch"
    if any(token in normalized for token in ["heart rate", "fréquence cardiaque", "resting"]):
        return "high_is_watch"
    return "change_is_watch"


def _severity_for_ratio(ratio: float) -> str:
    if ratio >= 0.4:
        return "high"
    if ratio >= 0.2:
        return "medium"
    return "low"


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.mean(values), 2)


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.median(values), 2)


def _event_date(item: dict[str, Any]) -> str | None:
    return item.get("date") or item.get("effectiveDateTime")


def _sort_by_date_desc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: _parse_date(_event_date(item)) or datetime.min,
        reverse=True,
    )


def _numeric_trends(
    items: list[dict[str, Any]],
    *,
    recent_days: int = 7,
    reference_date: date | None = None,
) -> list[dict[str, Any]]:
    today = reference_date or date.today()
    recent_start = today - timedelta(days=recent_days)

    grouped: dict[str, list[tuple[date, float, str | None]]] = defaultdict(list)
    for item in items:
        item_date = _parse_date(item.get("date"))
        value = _number(item.get("value"))
        if item_date is None or value is None:
            continue
        grouped[_label(item)].append((item_date.date(), value, item.get("unit")))

    trends = []
    for label, values in sorted(grouped.items()):
        values = sorted(values, key=lambda item: item[0])
        recent_values = [value for item_date, value, _ in values if item_date >= recent_start]
        previous_values = [value for item_date, value, _ in values if item_date < recent_start]
        recent_zero_count = sum(1 for value in recent_values if value == 0)

        recent_average = _average(recent_values)
        previous_average = _average(previous_values)
        delta = None
        if recent_average is not None and previous_average is not None:
            delta = round(recent_average - previous_average, 2)

        unit = next((unit for _, _, unit in values if unit), None)
        trends.append(
            {
                "label": label,
                "unit": unit,
                "count": len(values),
                "recentCount": len(recent_values),
                "previousCount": len(previous_values),
                "latest": values[-1][1],
                "recentAverage": recent_average,
                "previousAverage": previous_average,
                "delta": delta,
                "recentZeroCount": recent_zero_count,
                "recentZeroRatio": round(recent_zero_count / len(recent_values), 2)
                if recent_values else None,
                "dataNote": "many_recent_zero_values"
                if len(recent_values) >= 3 and recent_zero_count / len(recent_values) >= 0.5
                else None,
            }
        )

    return trends


def _top_counts(items: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts = Counter(_label(item) for item in items)
    return [{"label": label, "count": count} for label, count in counts.most_common(limit)]


def load_health_data(days: int = 30) -> dict[str, list[dict[str, Any]]]:
    days = max(1, min(days, 90))
    return {
        "metrics": get_recent_metrics(days=days),
        "medications": get_recent_medication(days=days),
        "symptoms": get_recent_symptoms(days=days),
        "stateofminds": get_recent_stateofminds(days=days),
        "workouts": get_recent_workouts(days=days),
        "spirometry": get_recent_spirometry(days=days),
        "manualMonthly": get_recent_manual_monthly(days=days),
    }


def _filter_items_to_period(items: list[dict[str, Any]], *, days: int, end_date: date) -> list[dict[str, Any]]:
    start_date = end_date - timedelta(days=days)
    filtered = []
    for item in items:
        parsed = _parse_date(_event_date(item))
        if parsed is None:
            continue
        item_date = parsed.date()
        if start_date <= item_date <= end_date:
            filtered.append(item)
    return filtered


def _filter_data_to_period(
    data: dict[str, list[dict[str, Any]]],
    *,
    days: int,
    end_date: date,
) -> dict[str, list[dict[str, Any]]]:
    return {
        key: _filter_items_to_period(items, days=days, end_date=end_date)
        for key, items in data.items()
    }


def _timeline_event(event_type: str, item: dict[str, Any]) -> dict[str, Any]:
    event = {
        "type": event_type,
        "date": _event_date(item),
        "id": item.get("id"),
        "label": item.get("display") or item.get("code") or item.get("medication"),
    }

    if event_type in {"metric", "stateofmind", "spirometry", "manualMonthly", "workout"}:
        event.update({
            "value": item.get("value"),
            "unit": item.get("unit"),
            "interpretation": item.get("interpretation"),
            "components": item.get("components"),
        })
    elif event_type == "medication":
        event.update({
            "status": item.get("status"),
            "dosage": item.get("dosage"),
        })
    elif event_type == "symptom":
        event.update({
            "severity": item.get("severity"),
            "clinicalStatus": item.get("clinicalStatus"),
            "source": item.get("source"),
        })

    return event


def build_health_timeline_from_data(
    days: int,
    data: dict[str, list[dict[str, Any]]],
    *,
    end_date: date | None = None,
) -> dict[str, Any]:
    days = max(1, min(days, 90))
    period_end = end_date or date.today()
    events = []
    events.extend(_timeline_event("metric", item) for item in data["metrics"])
    events.extend(_timeline_event("medication", item) for item in data["medications"])
    events.extend(_timeline_event("symptom", item) for item in data["symptoms"])
    events.extend(_timeline_event("stateofmind", item) for item in data["stateofminds"])
    events.extend(_timeline_event("workout", item) for item in data["workouts"])
    events.extend(_timeline_event("spirometry", item) for item in data["spirometry"])
    events.extend(_timeline_event("manualMonthly", item) for item in data["manualMonthly"])
    events = _sort_by_date_desc([event for event in events if event.get("date")])

    start_date = period_end - timedelta(days=days)
    return {
        "period": {
            "days": days,
            "startDate": start_date.isoformat(),
            "endDate": period_end.isoformat(),
        },
        "counts": {key: len(value) for key, value in data.items()},
        "events": events,
    }


def _latest_date(items: list[dict[str, Any]]) -> str | None:
    dates = [_parse_date(_event_date(item)) for item in items]
    valid_dates = [item_date for item_date in dates if item_date is not None]
    if not valid_dates:
        return None
    return max(valid_dates).isoformat()


def _days_since(value: str | None, *, reference_date: date | None = None) -> int | None:
    parsed = _parse_date(value)
    if parsed is None:
        return None
    return ((reference_date or date.today()) - parsed.date()).days


def build_data_quality(
    data: dict[str, list[dict[str, Any]]],
    *,
    reference_date: date | None = None,
) -> dict[str, Any]:
    freshness = {
        key: {
            "latestDate": _latest_date(items),
            "daysSinceLatest": _days_since(_latest_date(items), reference_date=reference_date),
        }
        for key, items in data.items()
    }
    missing_sources = [key for key, items in data.items() if not items]
    stale_sources = [
        key
        for key, info in freshness.items()
        if info["daysSinceLatest"] is not None and info["daysSinceLatest"] > 14
    ]

    score = 1.0
    score -= 0.08 * len(missing_sources)
    score -= 0.05 * len(stale_sources)
    score = max(0.0, round(score, 2))

    if score >= 0.8:
        level = "high"
    elif score >= 0.55:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "score": score,
        "freshness": freshness,
        "missingSources": missing_sources,
        "staleSources": stale_sources,
    }


def build_watch_items(
    *,
    data: dict[str, list[dict[str, Any]]],
    features: dict[str, Any],
) -> list[dict[str, Any]]:
    watch_items = []
    quality = features.get("dataQuality", {})

    if quality.get("level") != "high":
        watch_items.append({
            "type": "data_quality",
            "severity": "medium",
            "label": "Qualité ou fraîcheur des données limitée",
            "reason": "Certaines sources sont absentes ou anciennes.",
            "sources": quality.get("missingSources", []),
        })

    for trend in features.get("metricTrends", []):
        if trend.get("dataNote") == "many_recent_zero_values":
            watch_items.append({
                "type": "possible_missing_data",
                "severity": "medium",
                "label": trend.get("label"),
                "reason": "Beaucoup de valeurs récentes sont à zéro; cela peut refléter une absence de synchronisation plutôt qu'une vraie baisse.",
            })

    mood_trends = features.get("stateOfMindTrends", [])
    for trend in mood_trends:
        latest = _number(trend.get("latest"))
        if latest is not None and latest <= -0.5:
            watch_items.append({
                "type": "mood",
                "severity": "medium",
                "label": trend.get("label"),
                "reason": "Valence émotionnelle récente basse.",
            })

    if not data["medications"]:
        watch_items.append({
            "type": "medication",
            "severity": "low",
            "label": "Aucune administration médicamenteuse récente",
            "reason": "À vérifier: absence réelle, données non synchronisées ou arrêt prévu.",
        })

    return watch_items[:12]


def build_personal_anomalies(features: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []

    for group_key, source, default_direction in [
        ("metricTrends", "metrics", None),
        ("stateOfMindTrends", "stateofminds", "low_is_watch"),
        ("spirometryTrends", "spirometry", "low_is_watch"),
        ("manualMonthlyTrends", "manualMonthly", None),
    ]:
        for trend in features.get(group_key, []):
            label = trend.get("label")
            recent = _number(trend.get("recentAverage"))
            previous = _number(trend.get("previousAverage"))
            delta = _number(trend.get("delta"))
            if label is None or recent is None or previous is None or delta is None:
                continue
            if trend.get("recentCount", 0) < 2 or trend.get("previousCount", 0) < 2:
                continue

            baseline = abs(previous) if previous else 1.0
            ratio = abs(delta) / baseline
            if ratio < 0.18:
                continue

            direction = default_direction or _metric_direction(label)
            should_watch = (
                direction == "change_is_watch"
                or (direction == "low_is_watch" and delta < 0)
                or (direction == "high_is_watch" and delta > 0)
            )
            if not should_watch:
                continue

            anomalies.append({
                "type": "personal_baseline",
                "source": source,
                "severity": _severity_for_ratio(ratio),
                "label": label,
                "direction": "up" if delta > 0 else "down",
                "delta": delta,
                "unit": trend.get("unit"),
                "recentAverage": recent,
                "baselineAverage": previous,
                "reason": (
                    f"Moyenne récente {recent} vs baseline personnelle {previous} "
                    f"(delta {delta})."
                ),
            })

    for symptom in features.get("topSymptoms", []):
        count = int(symptom.get("count") or 0)
        if count >= 3:
            anomalies.append({
                "type": "recurrent_symptom",
                "source": "symptoms",
                "severity": "medium" if count < 5 else "high",
                "label": symptom.get("label"),
                "count": count,
                "reason": f"Symptôme présent {count} fois sur la période récente.",
            })

    return anomalies[:12]


def build_personal_watchlist(
    *,
    data: dict[str, list[dict[str, Any]]],
    features: dict[str, Any],
) -> list[dict[str, Any]]:
    watchlist = []
    anomalies = features.get("anomalies") or []
    watch_items = features.get("watchItems") or []

    for definition in WATCHLIST_DEFINITIONS:
        categories = definition["categories"]
        keywords = definition["keywords"]
        related_items = []

        for category in categories:
            for item in data.get(category, []):
                if _matches_keywords(_label(item), keywords):
                    related_items.append(item)

        related_anomalies = [
            item for item in anomalies
            if _matches_keywords(str(item.get("label")), keywords)
            or (
                item.get("source") in categories
                and definition["id"] in {"spirometry", "mood", "medication"}
            )
        ]
        related_watch_items = [
            item for item in watch_items
            if _matches_keywords(str(item.get("label")), keywords)
            or item.get("type") == definition["id"]
            or item.get("source") in categories
        ]

        latest_date = _latest_date(related_items)
        status = "quiet"
        severity = "info"
        reason = "Aucun signal notable sur la période."
        if related_anomalies:
            top_anomaly = related_anomalies[0]
            status = "watch"
            severity = top_anomaly.get("severity") or "medium"
            reason = top_anomaly.get("reason") or "Signal inhabituel par rapport à la baseline personnelle."
        elif related_watch_items:
            top_watch = related_watch_items[0]
            status = "watch"
            severity = top_watch.get("severity") or "medium"
            reason = top_watch.get("reason") or "Point de vigilance détecté."
        elif related_items:
            reason = f"{len(related_items)} événement(s) récent(s), sans anomalie déterministe."

        watchlist.append({
            "id": definition["id"],
            "label": definition["label"],
            "status": status,
            "severity": severity,
            "recentCount": len(related_items),
            "latestDate": latest_date,
            "reason": reason,
        })

    return watchlist


def _values_by_day(items: list[dict[str, Any]], keywords: list[str]) -> dict[date, list[float]]:
    grouped: dict[date, list[float]] = defaultdict(list)
    for item in items:
        item_date = _parse_date(item.get("date"))
        value = _number(item.get("value"))
        if item_date is None or value is None:
            continue
        if _matches_keywords(_label(item), keywords):
            grouped[item_date.date()].append(value)
    return grouped


def _presence_days(items: list[dict[str, Any]], keywords: list[str]) -> set[date]:
    days = set()
    for item in items:
        item_date = _parse_date(item.get("date"))
        if item_date is None:
            continue
        if _matches_keywords(_label(item), keywords):
            days.add(item_date.date())
    return days


def build_cautious_correlations(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    correlations = []
    fatigue_days = _presence_days(data["symptoms"], ["fatigue", "tired", "exhaust"])
    pain_days = _presence_days(data["symptoms"], ["douleur", "pain", "lomb", "dos"])
    sleep_by_day = _values_by_day(data["metrics"], ["sleep", "sommeil"])
    activity_by_day = _values_by_day(data["metrics"], ["step", "pas", "distance", "active energy"])
    workout_days = _presence_days(data["workouts"], ["workout", "entraînement", "marche", "yoga"])

    def compare_signal_days(
        *,
        signal_days: set[date],
        values_by_day: dict[date, list[float]],
        signal_label: str,
        value_label: str,
        lower_wording: str,
    ) -> None:
        if len(signal_days) < 2 or len(values_by_day) < 5:
            return
        signal_values = [
            statistics.mean(values)
            for day, values in values_by_day.items()
            if day in signal_days
        ]
        other_values = [
            statistics.mean(values)
            for day, values in values_by_day.items()
            if day not in signal_days
        ]
        if len(signal_values) < 2 or len(other_values) < 2:
            return
        signal_avg = _average(signal_values)
        other_avg = _average(other_values)
        if signal_avg is None or other_avg is None:
            return
        if signal_avg < other_avg * 0.85:
            correlations.append({
                "type": "cooccurrence",
                "confidence": "low",
                "signal": signal_label,
                "context": value_label,
                "reason": (
                    f"Les jours avec {signal_label}, le signal {value_label} semble plus bas "
                    f"({signal_avg} vs {other_avg}). Hypothèse prudente: {lower_wording}."
                ),
            })

    compare_signal_days(
        signal_days=fatigue_days,
        values_by_day=sleep_by_day,
        signal_label="fatigue",
        value_label="sommeil",
        lower_wording="moins de sommeil pourrait coïncider avec plus de fatigue",
    )
    compare_signal_days(
        signal_days=fatigue_days,
        values_by_day=activity_by_day,
        signal_label="fatigue",
        value_label="activité",
        lower_wording="les journées moins actives pourraient coïncider avec la fatigue",
    )

    if len(workout_days & fatigue_days) >= 2:
        correlations.append({
            "type": "cooccurrence",
            "confidence": "low",
            "signal": "fatigue",
            "context": "entraînement",
            "reason": "Fatigue et entraînement apparaissent parfois le même jour; à lire comme une piste de récupération, pas une causalité.",
        })
    if len(workout_days & pain_days) >= 2:
        correlations.append({
            "type": "cooccurrence",
            "confidence": "low",
            "signal": "douleur",
            "context": "entraînement",
            "reason": "Douleur et entraînement apparaissent parfois le même jour; vérifier le contexte réel avant d'en conclure quoi que ce soit.",
        })

    return correlations[:8]


def _event_days(items: list[dict[str, Any]], keywords: list[str] | None = None) -> set[date]:
    days = set()
    for item in items:
        item_date = _parse_date(item.get("date"))
        if item_date is None:
            continue
        if keywords is None or _matches_keywords(_label(item), keywords):
            days.add(item_date.date())
    return days


def build_light_goals(data: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    today = date.today()
    week_start = today - timedelta(days=6)

    def recent_count(days: set[date]) -> int:
        return len([day for day in days if day >= week_start])

    workout_count = recent_count(_event_days(data["workouts"]))
    symptom_log_count = recent_count(_event_days(data["symptoms"]))
    spirometry_count = recent_count(_event_days(data["spirometry"]))
    medication_count = recent_count(_event_days(data["medications"]))

    goals = [
        {
            "id": "movement_3_days",
            "label": "Bouger 3 jours dans la semaine",
            "target": 3,
            "current": workout_count,
            "unit": "jours",
            "status": "done" if workout_count >= 3 else "active",
            "note": "Objectif léger, adaptable selon fatigue et récupération.",
        },
        {
            "id": "symptom_log_5_days",
            "label": "Renseigner symptômes ou ressenti 5 jours sur 7",
            "target": 5,
            "current": symptom_log_count,
            "unit": "jours",
            "status": "done" if symptom_log_count >= 5 else "active",
            "note": "Le but est d'améliorer le suivi, pas de créer une contrainte.",
        },
    ]
    if data["spirometry"]:
        goals.append({
            "id": "spirometry_3_days",
            "label": "Surveiller le souffle 3 fois dans la semaine",
            "target": 3,
            "current": spirometry_count,
            "unit": "mesures",
            "status": "done" if spirometry_count >= 3 else "active",
            "note": "Utile surtout si la respiration ou la récupération varie.",
        })
    if data["medications"]:
        goals.append({
            "id": "medication_trace_7_days",
            "label": "Tracer les prises de médicament chaque jour",
            "target": 7,
            "current": medication_count,
            "unit": "jours",
            "status": "done" if medication_count >= 7 else "active",
            "note": "À adapter si le traitement n'est pas quotidien.",
        })
    return goals


def build_structured_review(
    *,
    features: dict[str, Any],
    review_history: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_trends = {}
    if review_history:
        for trend in review_history[0].get("metricTrends", []):
            label = trend.get("label")
            if label:
                previous_trends[label] = trend

    confirmed_trends = []
    new_signals = []
    for trend in features.get("metricTrends", []):
        label = trend.get("label")
        delta = _number(trend.get("delta"))
        previous_delta = _number(previous_trends.get(label, {}).get("delta"))
        if not label or delta is None:
            continue
        signal = {
            "label": label,
            "delta": delta,
            "unit": trend.get("unit"),
            "recentAverage": trend.get("recentAverage"),
            "previousAverage": trend.get("previousAverage"),
        }
        if previous_delta is not None and (delta > 0) == (previous_delta > 0):
            signal["previousDelta"] = previous_delta
            confirmed_trends.append(signal)
        elif previous_delta is None:
            new_signals.append(signal)

    watch_items = features.get("watchItems", [])

    structured = {
        "confirmedTrends": confirmed_trends[:8],
        "newSignals": new_signals[:8],
        "watchItems": watch_items,
        "anomalies": features.get("anomalies", []),
        "personalWatchlist": features.get("personalWatchlist", []),
        "cautiousCorrelations": features.get("cautiousCorrelations", []),
        "goals": features.get("goals", []),
        "recommendedActions": [
            "Vérifier la synchronisation des sources absentes ou avec beaucoup de zéros.",
            "Comparer les ressentis subjectifs avec les tendances d'activité et d'humeur.",
            "Prioriser les éléments de la watchlist personnalisée plutôt que tout surveiller à la fois.",
            "Contacter un professionnel de santé en cas d'aggravation, symptôme inquiétant ou doute.",
        ],
        "questions": [
            "Y a-t-il eu un changement de routine, de sommeil ou de stress récemment ?",
            "Les données d'activité et de médicaments sont-elles bien synchronisées ?",
            "Les tendances décrites correspondent-elles au ressenti réel ?",
        ],
        "dataConfidence": features.get("dataQuality"),
    }
    structured["traceability"] = build_conclusion_traces(features, structured)
    structured["specializedAgents"] = build_specialized_agent_summary(features, structured)
    return structured


def build_conclusion_traces(
    features: dict[str, Any],
    structured_review: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    structured = structured_review or {}
    traces: list[dict[str, Any]] = []

    def add_trace(
        *,
        conclusion_id: str,
        conclusion: str,
        source: str,
        count: int | None,
        days: int | None,
        evidence: list[dict[str, Any]],
    ) -> None:
        traces.append({
            "id": conclusion_id,
            "conclusion": conclusion,
            "source": source,
            "count": count,
            "periodDays": days,
            "evidence": evidence[:6],
            "wording": f"Cette observation vient de {count if count is not None else 'n'} mesure(s) sur {days or '?'} jours.",
        })

    period_days = ((features.get("period") or {}).get("days"))
    for index, trend in enumerate(features.get("metricTrends", [])[:8], start=1):
        add_trace(
            conclusion_id=f"metric-trend-{index}",
            conclusion=str(trend.get("label") or "Tendance mesure"),
            source="metricTrends",
            count=trend.get("count"),
            days=period_days,
            evidence=[trend],
        )
    for index, trend in enumerate(features.get("spirometryTrends", [])[:6], start=1):
        add_trace(
            conclusion_id=f"spirometry-trend-{index}",
            conclusion=str(trend.get("label") or "Tendance spirométrie"),
            source="spirometryTrends",
            count=trend.get("count"),
            days=period_days,
            evidence=[trend],
        )
    for index, item in enumerate(structured.get("anomalies") or features.get("anomalies") or [], start=1):
        add_trace(
            conclusion_id=f"anomaly-{index}",
            conclusion=str(item.get("label") or item.get("type") or "Anomalie"),
            source=str(item.get("source") or item.get("type") or "anomalies"),
            count=item.get("count") or item.get("recentCount"),
            days=period_days,
            evidence=[item],
        )
    for index, item in enumerate(structured.get("watchItems") or features.get("watchItems") or [], start=1):
        add_trace(
            conclusion_id=f"watch-{index}",
            conclusion=str(item.get("label") or item.get("type") or "Point de vigilance"),
            source=str(item.get("type") or "watchItems"),
            count=len(item.get("sources") or []) if item.get("sources") else None,
            days=period_days,
            evidence=[item],
        )
    return traces[:24]


def build_specialized_agent_summary(
    features: dict[str, Any],
    structured_review: dict[str, Any],
) -> dict[str, Any]:
    safety_items = [
        item for item in (structured_review.get("anomalies") or []) + (structured_review.get("watchItems") or [])
        if item.get("severity") in {"high", "medium"}
    ]
    return {
        "dataAnalyst": {
            "role": "analyste_donnees",
            "output": {
                "trends": {
                    "metrics": features.get("metricTrends", [])[:6],
                    "spirometry": features.get("spirometryTrends", [])[:6],
                    "stateOfMind": features.get("stateOfMindTrends", [])[:4],
                },
                "dataQuality": features.get("dataQuality"),
            },
        },
        "dailyCoach": {
            "role": "coach_quotidien",
            "output": {
                "goals": structured_review.get("goals", [])[:6],
                "questions": structured_review.get("questions", [])[:6],
            },
        },
        "medicalSafetyChecker": {
            "role": "verificateur_securite_medicale",
            "output": {
                "needsCaution": bool(safety_items),
                "signals": safety_items[:8],
                "guardrail": "Pas de diagnostic; avis médical si aggravation, symptôme inquiétant, effet indésirable ou doute.",
            },
        },
        "telegramWriter": {
            "role": "redacteur_telegram",
            "output": {
                "priority": (structured_review.get("watchItems") or structured_review.get("anomalies") or [])[:4],
                "style": "notification douce, concise, factuelle",
            },
        },
    }


DEFAULT_ALERT_RULES = [
    {"id": "spirometry_drop", "enabled": True, "type": "spirometry_drop", "days": 7, "threshold": -0.12},
    {"id": "severe_symptom", "enabled": True, "type": "severe_symptom"},
    {"id": "missing_data_3_days", "enabled": True, "type": "missing_data", "days": 3},
    {"id": "medication_missing", "enabled": True, "type": "medication_missing", "days": 3},
]


def evaluate_alert_rules(
    features: dict[str, Any],
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_rules = [rule for rule in (rules or DEFAULT_ALERT_RULES) if rule.get("enabled", True)]
    alerts: list[dict[str, Any]] = []
    quality = features.get("dataQuality") or {}

    for rule in active_rules:
        rule_type = rule.get("type")
        if rule_type == "spirometry_drop":
            threshold = float(rule.get("threshold", -0.12))
            for trend in features.get("spirometryTrends", []):
                previous = _number(trend.get("previousAverage"))
                delta = _number(trend.get("delta"))
                if previous in (None, 0) or delta is None:
                    continue
                ratio = delta / abs(previous)
                if ratio <= threshold:
                    alerts.append({
                        "ruleId": rule.get("id"),
                        "severity": "medium" if ratio > threshold * 1.8 else "high",
                        "label": f"Spirométrie en baisse: {trend.get('label')}",
                        "reason": f"Variation {round(ratio * 100, 1)}% vs baseline récente.",
                        "trace": build_conclusion_traces(features, {"anomalies": [trend]})[:1],
                    })
        elif rule_type == "severe_symptom":
            for event in features.get("recentEvents", []):
                if event.get("type") != "symptom":
                    continue
                severity = str(event.get("severity") or "").lower()
                if severity in {"severe", "high", "grave", "sévère", "8", "9", "10"}:
                    alerts.append({
                        "ruleId": rule.get("id"),
                        "severity": "high",
                        "label": f"Symptôme sévère: {event.get('label')}",
                        "reason": "Un symptôme récent est marqué comme sévère.",
                        "trace": [{"source": "recentEvents", "evidence": [event]}],
                    })
        elif rule_type == "missing_data":
            max_days = int(rule.get("days", 3))
            stale = []
            for source, info in (quality.get("freshness") or {}).items():
                days_since = info.get("daysSinceLatest")
                if days_since is None or days_since >= max_days:
                    stale.append(source)
            if stale:
                alerts.append({
                    "ruleId": rule.get("id"),
                    "severity": "low",
                    "label": "Données absentes ou anciennes",
                    "reason": f"Aucune donnée récente pour: {', '.join(stale)}.",
                    "sources": stale,
                })
        elif rule_type == "medication_missing":
            max_days = int(rule.get("days", 3))
            freshness = (quality.get("freshness") or {}).get("medications") or {}
            days_since = freshness.get("daysSinceLatest")
            if days_since is None or days_since >= max_days:
                alerts.append({
                    "ruleId": rule.get("id"),
                    "severity": "low",
                    "label": "Médicament non vu récemment",
                    "reason": "À vérifier: oubli, arrêt prévu ou donnée non synchronisée.",
                    "daysSinceLatest": days_since,
                })

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rules": active_rules,
        "alerts": alerts[:12],
        "telegramText": format_soft_alerts(alerts),
    }


def format_soft_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return "Point doux du coach: aucune alerte déterministe sur les règles configurées."
    lines = ["Point doux du coach"]
    for alert in alerts[:5]:
        lines.append(f"- [{alert.get('severity', 'info')}] {alert.get('label')}: {alert.get('reason')}")
    lines.append("À lire comme un rappel de suivi, pas comme un diagnostic.")
    return "\n".join(lines)


def build_medical_export_markdown(features: dict[str, Any], *, days: int) -> str:
    structured = build_structured_review(features=features, review_history=[])
    sections = [
        f"# Résumé santé pour rendez-vous médical - {date.today().isoformat()}",
        f"Période couverte: {days} jours.",
        "Note: document de suivi personnel, sans diagnostic automatique.",
        "## Qualité des données",
        json.dumps(features.get("dataQuality") or {}, ensure_ascii=False, indent=2),
        "## Symptômes",
        _markdown_items(features.get("topSymptoms") or [], ["label", "count"]),
        "## Médicaments",
        _markdown_items(features.get("recentMedication") or [], ["date", "medication", "status", "dosage"]),
        "## Spirométrie",
        _markdown_items(features.get("spirometryTrends") or [], ["label", "recentAverage", "previousAverage", "delta", "unit", "count"]),
        "## Tendances",
        _markdown_items(features.get("metricTrends") or [], ["label", "recentAverage", "previousAverage", "delta", "unit", "count"]),
        "## Watchlist et anomalies",
        _markdown_items((features.get("watchItems") or []) + (features.get("anomalies") or []), ["severity", "label", "reason"]),
        "## Questions à poser",
        "\n".join(f"- {item}" for item in structured.get("questions", [])),
        "## Traçabilité",
        _markdown_items(structured.get("traceability") or [], ["id", "conclusion", "source", "count", "periodDays", "wording"]),
    ]
    return "\n\n".join(section for section in sections if section).strip() + "\n"


def _markdown_items(items: list[dict[str, Any]], keys: list[str]) -> str:
    if not items:
        return "- Aucun élément récent."
    lines = []
    for item in items[:20]:
        values = [f"{key}: {item.get(key)}" for key in keys if item.get(key) is not None]
        lines.append("- " + "; ".join(values))
    return "\n".join(lines)


def build_medical_export_pdf_bytes(markdown_text: str) -> bytes:
    plain_lines = []
    for line in markdown_text.splitlines():
        cleaned = re.sub(r"^#+\s*", "", line).replace("•", "-")
        plain_lines.append(cleaned[:110])
    text = "\n".join(plain_lines[:120])
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream_lines = ["BT", "/F1 10 Tf", "50 790 Td"]
    first = True
    for line in escaped.splitlines():
        if first:
            stream_lines.append(f"({line}) Tj")
            first = False
        else:
            stream_lines.append("0 -13 Td")
            stream_lines.append(f"({line}) Tj")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def run_synthetic_coach_evaluation() -> dict[str, Any]:
    today = date.today()

    def metric(label: str, days_ago: int, value: float) -> dict[str, Any]:
        return {"date": (today - timedelta(days=days_ago)).isoformat(), "display": label, "value": value}

    scenarios = {
        "donnees_absentes": {"metrics": [], "medications": [], "symptoms": [], "stateofminds": [], "workouts": [], "spirometry": [], "manualMonthly": []},
        "tendance_positive": {"metrics": [metric("step count", 1, 7000), metric("step count", 2, 6500), metric("step count", 14, 3000), metric("step count", 15, 3200)], "medications": [metric("med", 1, 1)], "symptoms": [], "stateofminds": [], "workouts": [], "spirometry": [], "manualMonthly": []},
        "tendance_negative": {"metrics": [metric("resting heart rate", 1, 88), metric("resting heart rate", 2, 86), metric("resting heart rate", 14, 70), metric("resting heart rate", 15, 71)], "medications": [metric("med", 1, 1)], "symptoms": [], "stateofminds": [], "workouts": [], "spirometry": [], "manualMonthly": []},
        "medicament_manquant": {"metrics": [], "medications": [], "symptoms": [], "stateofminds": [], "workouts": [], "spirometry": [], "manualMonthly": []},
        "symptome_inquietant": {"metrics": [], "medications": [metric("med", 1, 1)], "symptoms": [{"date": today.isoformat(), "display": "douleur thoracique", "severity": "high"}], "stateofminds": [], "workouts": [], "spirometry": [], "manualMonthly": []},
    }

    results = []
    for name, data in scenarios.items():
        timeline = build_health_timeline_from_data(days=30, data=data)
        features = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "period": timeline.get("period"),
            "counts": timeline.get("counts"),
            "metricTrends": _numeric_trends(data["metrics"]),
            "stateOfMindTrends": _numeric_trends(data["stateofminds"]),
            "spirometryTrends": _numeric_trends(data["spirometry"]),
            "manualMonthlyTrends": _numeric_trends(data["manualMonthly"]),
            "topSymptoms": _top_counts(data["symptoms"]),
            "recentMedication": data["medications"][:10],
            "recentEvents": timeline.get("events", [])[:30],
        }
        features["dataQuality"] = build_data_quality(data)
        features["anomalies"] = build_personal_anomalies(features)
        features["watchItems"] = build_watch_items(data=data, features=features)
        alerts = evaluate_alert_rules(features)
        risky_assertions = []
        for text in json.dumps({"features": features, "alerts": alerts}, ensure_ascii=False).lower().split("."):
            if any(safe in text for safe in ["sans diagnostic", "pas comme un diagnostic", "pas de diagnostic"]):
                continue
            if any(token in text for token in ["diagnostic", "certainement", "guérit", "maladie confirmée"]):
                risky_assertions.append(text)
        passed = not risky_assertions
        if name in {"donnees_absentes", "medicament_manquant"}:
            passed = passed and bool(alerts.get("alerts") or features.get("watchItems"))
        if name == "symptome_inquietant":
            passed = passed and any(alert.get("severity") == "high" for alert in alerts.get("alerts", []))
        results.append({
            "scenario": name,
            "passed": passed,
            "alerts": alerts.get("alerts", []),
            "watchItems": features.get("watchItems", []),
            "riskyAssertions": risky_assertions,
        })

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "passed": all(item["passed"] for item in results),
        "results": results,
        "objective": "Réduire hallucinations, conseils trop affirmatifs et oublis de signaux déterministes.",
    }


def _trend_snapshot(features: dict[str, Any], key: str, limit: int = 8) -> list[dict[str, Any]]:
    trends = features.get(key)
    if not isinstance(trends, list):
        return []

    snapshot = []
    for trend in trends[:limit]:
        if not isinstance(trend, dict):
            continue
        snapshot.append(
            {
                "label": trend.get("label"),
                "recentAverage": trend.get("recentAverage"),
                "previousAverage": trend.get("previousAverage"),
                "delta": trend.get("delta"),
                "unit": trend.get("unit"),
            }
        )

    return snapshot


def _compact_review_text(text: str | None, max_chars: int = 900) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def build_review_history_context(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    context = []
    for review in history:
        features = review.get("features") or {}
        context.append(
            {
                "reviewId": review.get("review_id"),
                "reviewDate": review.get("review_date"),
                "createdAt": review.get("created_at"),
                "periodDays": review.get("period_days"),
                "counts": features.get("counts"),
                "metricTrends": _trend_snapshot(features, "metricTrends"),
                "stateOfMindTrends": _trend_snapshot(features, "stateOfMindTrends"),
                "topSymptoms": features.get("topSymptoms", [])[:5],
                "anomalies": features.get("anomalies", [])[:5],
                "personalWatchlist": features.get("personalWatchlist", [])[:6],
                "goals": features.get("goals", [])[:5],
                "reviewSummary": _compact_review_text(review.get("review_text")),
            }
        )

    return context


def build_daily_health_features(days: int = 30, *, end_date: date | None = None) -> dict[str, Any]:
    days = max(1, min(days, 90))
    period_end = end_date or date.today()

    data = _filter_data_to_period(
        load_health_data(days=days + 1),
        days=days,
        end_date=period_end,
    )
    timeline = build_health_timeline_from_data(days=min(days, 30), data=data, end_date=period_end)

    features = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "period": timeline.get("period"),
        "counts": timeline.get("counts"),
        "metricTrends": _numeric_trends(data["metrics"], reference_date=period_end),
        "stateOfMindTrends": _numeric_trends(data["stateofminds"], reference_date=period_end),
        "spirometryTrends": _numeric_trends(data["spirometry"], reference_date=period_end),
        "manualMonthlyTrends": _numeric_trends(data["manualMonthly"], reference_date=period_end),
        "topSymptoms": _top_counts(data["symptoms"]),
        "recentMedication": data["medications"][:10],
        "recentEvents": timeline.get("events", [])[:30],
    }
    features["dataQuality"] = build_data_quality(data, reference_date=period_end)
    features["anomalies"] = build_personal_anomalies(features)
    features["watchItems"] = build_watch_items(data=data, features=features)
    features["personalWatchlist"] = build_personal_watchlist(data=data, features=features)
    features["cautiousCorrelations"] = build_cautious_correlations(data)
    features["goals"] = build_light_goals(data)
    return features


def _system_prompt() -> str:
    return (
        "Tu es un coach santé prudent, bienveillant et factuel. "
        "Tu analyses des tendances personnelles issues de données FHIR. "
        "Tu ne poses pas de diagnostic médical. "
        "Tu distingues observations, hypothèses et actions raisonnables. "
        "Tu recommandes de contacter un professionnel de santé en cas de symptôme inquiétant, "
        "aggravation nette, effet indésirable ou doute."
    )


def _user_prompt(
    features: dict[str, Any],
    review_history: list[dict[str, Any]] | None = None,
    structured_review: dict[str, Any] | None = None,
    *,
    previous_day: bool = False,
) -> str:
    history = review_history or []
    history_section = (
        "Historique des revues précédentes:\n"
        f"{json.dumps(history, ensure_ascii=False, indent=2)}\n\n"
        if history
        else "Historique des revues précédentes: aucune revue précédente disponible.\n\n"
    )

    intro = (
        "Produis un bilan matinal en français de la journée précédente, concis et actionnable. "
        "Le bilan doit expliquer ce qui ressort d'hier et proposer des conseils prudents pour la journée qui démarre.\n"
        if previous_day
        else "Produis une revue santé quotidienne en français, concise et actionnable.\n"
    )

    return (
        intro +
        "Compare explicitement les nouvelles données avec l'historique lorsque c'est possible. "
        "Indique si une tendance se confirme, s'améliore, s'inverse ou reste incertaine.\n"
        "Priorise la watchlist personnalisée, les anomalies personnelles et les corrélations prudentes. "
        "Pour les corrélations, parle toujours d'hypothèses ou de coïncidences possibles, jamais de causalité.\n"
        "Structure attendue:\n"
        f"1. {'Bilan de la journée précédente' if previous_day else 'Résumé du jour'}\n"
        "2. Tendances notables\n"
        "3. Watchlist et anomalies personnelles\n"
        "4. Hypothèses prudentes / corrélations possibles\n"
        "5. Conseils et objectifs légers pour les prochaines 24-48h\n"
        "6. Questions utiles à poser à l'utilisateur\n\n"
        "Synthèse structurée déterministe à utiliser comme garde-fou:\n"
        f"{json.dumps(structured_review or {}, ensure_ascii=False, indent=2)}\n\n"
        f"{history_section}"
        "Données structurées:\n"
        f"{json.dumps(features, ensure_ascii=False, indent=2)}"
    )


def _weekly_user_prompt(
    features: dict[str, Any],
    review_history: list[dict[str, Any]] | None = None,
    structured_review: dict[str, Any] | None = None,
) -> str:
    history = review_history or []
    history_section = (
        "Historique des revues précédentes:\n"
        f"{json.dumps(history, ensure_ascii=False, indent=2)}\n\n"
        if history
        else "Historique des revues précédentes: aucune revue précédente disponible.\n\n"
    )

    return (
        "Produis un bilan santé hebdomadaire en français, factuel, prudent et actionnable.\n"
        "Ce bilan doit se concentrer sur les tendances lentes: humeur, poids ou morphologie, douleur, "
        "spirométrie, adhérence médicament, activité et récupération.\n"
        "Priorise la watchlist personnalisée, les anomalies par rapport à la baseline personnelle, "
        "les objectifs légers et les corrélations prudentes. "
        "Ne présente jamais une corrélation comme une causalité.\n"
        "Structure attendue:\n"
        "1. Vue d'ensemble de la semaine\n"
        "2. Tendances qui se confirment ou changent\n"
        "3. Watchlist personnalisée\n"
        "4. Corrélations possibles à vérifier\n"
        "5. Objectifs doux pour la semaine prochaine\n"
        "6. Questions à garder en tête\n\n"
        "Synthèse structurée déterministe à utiliser comme garde-fou:\n"
        f"{json.dumps(structured_review or {}, ensure_ascii=False, indent=2)}\n\n"
        f"{history_section}"
        "Données structurées:\n"
        f"{json.dumps(features, ensure_ascii=False, indent=2)}"
    )


async def generate_daily_health_review(
    days: int = 30,
    *,
    store: bool = True,
    history_limit: int = 7,
    target_date: date | None = None,
    previous_day: bool = False,
    respect_schedule_toggle: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    services = get_services()
    services.state_store.init_db()

    if respect_schedule_toggle and not services.state_store.are_scheduled_health_reviews_enabled():
        skipped_date = target_date or (date.today() - timedelta(days=1) if previous_day else date.today())
        return {
            "skipped": True,
            "reason": "scheduled_health_reviews_disabled",
            "reviewDate": skipped_date.isoformat(),
        }

    days = max(1, min(days, 90))
    period_end = target_date or (date.today() - timedelta(days=1) if previous_day else date.today())
    model = settings.health_coach_model or settings.default_chat_model
    review_id = f"health-review-{uuid.uuid4().hex}"
    features = build_daily_health_features(days=days, end_date=period_end)
    review_history = build_review_history_context(
        services.state_store.list_health_review_context(limit=max(0, min(history_limit, 14)))
    )
    structured_review = build_structured_review(
        features=features,
        review_history=review_history,
    )

    if store:
        services.state_store.create_health_review(
            review_id=review_id,
            review_date=period_end.isoformat(),
            period_days=days,
            model=model,
            features=features,
        )

    try:
        review_text = await services.ollama.plain_invoke(
            model_name=model,
            system_prompt=_system_prompt(),
            user_prompt=_user_prompt(
                features,
                review_history,
                structured_review,
                previous_day=previous_day,
            ),
        )
    except Exception as exc:
        if store:
            services.state_store.finish_health_review(
                review_id=review_id,
                status="error",
                error=str(exc),
            )
        raise

    if store:
        services.state_store.finish_health_review(
            review_id=review_id,
            status="completed",
            review_text=review_text,
            structured_review=structured_review,
        )

    result = {
        "reviewId": review_id,
        "reviewDate": period_end.isoformat(),
        "periodDays": days,
        "model": model,
        "features": features,
        "history": review_history,
        "structuredReview": structured_review,
        "review": review_text,
    }
    if store:
        await notify_daily_health_review(result)
    return result


async def generate_weekly_health_review(
    days: int = 90,
    *,
    store: bool = True,
    history_limit: int = 7,
    respect_schedule_toggle: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    services = get_services()
    services.state_store.init_db()

    if respect_schedule_toggle and not services.state_store.are_scheduled_health_reviews_enabled():
        return {
            "skipped": True,
            "reason": "scheduled_health_reviews_disabled",
            "reviewDate": date.today().isoformat(),
        }

    days = max(7, min(days, 90))
    model = settings.health_coach_model or settings.default_chat_model
    review_id = f"weekly-health-review-{uuid.uuid4().hex}"
    features = build_daily_health_features(days=days)
    review_history = build_review_history_context(
        services.state_store.list_health_review_context(limit=max(0, min(history_limit, 14)))
    )
    structured_review = build_structured_review(
        features=features,
        review_history=review_history,
    )

    if store:
        services.state_store.create_health_review(
            review_id=review_id,
            review_date=date.today().isoformat(),
            period_days=days,
            model=model,
            features=features,
        )

    try:
        review_text = await services.ollama.plain_invoke(
            model_name=model,
            system_prompt=_system_prompt(),
            user_prompt=_weekly_user_prompt(features, review_history, structured_review),
        )
    except Exception as exc:
        if store:
            services.state_store.finish_health_review(
                review_id=review_id,
                status="error",
                error=str(exc),
            )
        raise

    if store:
        services.state_store.finish_health_review(
            review_id=review_id,
            status="completed",
            review_text=review_text,
            structured_review=structured_review,
        )

    result = {
        "reviewId": review_id,
        "reviewDate": date.today().isoformat(),
        "periodDays": days,
        "model": model,
        "features": features,
        "history": review_history,
        "structuredReview": structured_review,
        "review": review_text,
    }
    if store:
        await notify_daily_health_review(result)
    return result


async def _async_main() -> None:
    parser = argparse.ArgumentParser(description="Generate the daily PompeTrack health coach review.")
    parser.add_argument("--days", type=int, default=get_settings().health_coach_days)
    parser.add_argument("--history-limit", type=int, default=7)
    parser.add_argument("--no-store", action="store_true")
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--previous-day", action="store_true")
    parser.add_argument("--respect-schedule-toggle", action="store_true")
    args = parser.parse_args()

    if args.weekly:
        result = await generate_weekly_health_review(
            days=args.days,
            store=not args.no_store,
            history_limit=args.history_limit,
            respect_schedule_toggle=args.respect_schedule_toggle,
        )
    else:
        result = await generate_daily_health_review(
            days=args.days,
            store=not args.no_store,
            history_limit=args.history_limit,
            previous_day=args.previous_day,
            respect_schedule_toggle=args.respect_schedule_toggle,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
