from __future__ import annotations

import argparse
import asyncio
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


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(statistics.mean(values), 2)


def _event_date(item: dict[str, Any]) -> str | None:
    return item.get("date") or item.get("effectiveDateTime")


def _sort_by_date_desc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: _parse_date(_event_date(item)) or datetime.min,
        reverse=True,
    )


def _numeric_trends(items: list[dict[str, Any]], *, recent_days: int = 7) -> list[dict[str, Any]]:
    today = date.today()
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


def build_health_timeline_from_data(days: int, data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    days = max(1, min(days, 90))
    events = []
    events.extend(_timeline_event("metric", item) for item in data["metrics"])
    events.extend(_timeline_event("medication", item) for item in data["medications"])
    events.extend(_timeline_event("symptom", item) for item in data["symptoms"])
    events.extend(_timeline_event("stateofmind", item) for item in data["stateofminds"])
    events.extend(_timeline_event("workout", item) for item in data["workouts"])
    events.extend(_timeline_event("spirometry", item) for item in data["spirometry"])
    events.extend(_timeline_event("manualMonthly", item) for item in data["manualMonthly"])
    events = _sort_by_date_desc([event for event in events if event.get("date")])

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return {
        "period": {
            "days": days,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
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


def _days_since(value: str | None) -> int | None:
    parsed = _parse_date(value)
    if parsed is None:
        return None
    return (date.today() - parsed.date()).days


def build_data_quality(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    freshness = {
        key: {
            "latestDate": _latest_date(items),
            "daysSinceLatest": _days_since(_latest_date(items)),
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

    return {
        "confirmedTrends": confirmed_trends[:8],
        "newSignals": new_signals[:8],
        "watchItems": watch_items,
        "recommendedActions": [
            "Vérifier la synchronisation des sources absentes ou avec beaucoup de zéros.",
            "Comparer les ressentis subjectifs avec les tendances d'activité et d'humeur.",
            "Contacter un professionnel de santé en cas d'aggravation, symptôme inquiétant ou doute.",
        ],
        "questions": [
            "Y a-t-il eu un changement de routine, de sommeil ou de stress récemment ?",
            "Les données d'activité et de médicaments sont-elles bien synchronisées ?",
            "Les tendances décrites correspondent-elles au ressenti réel ?",
        ],
        "dataConfidence": features.get("dataQuality"),
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
                "reviewSummary": _compact_review_text(review.get("review_text")),
            }
        )

    return context


def build_daily_health_features(days: int = 30) -> dict[str, Any]:
    days = max(1, min(days, 90))

    data = load_health_data(days=days)
    timeline = build_health_timeline_from_data(days=min(days, 30), data=data)

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
    features["watchItems"] = build_watch_items(data=data, features=features)
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
) -> str:
    history = review_history or []
    history_section = (
        "Historique des revues précédentes:\n"
        f"{json.dumps(history, ensure_ascii=False, indent=2)}\n\n"
        if history
        else "Historique des revues précédentes: aucune revue précédente disponible.\n\n"
    )

    return (
        "Produis une revue santé quotidienne en français, concise et actionnable.\n"
        "Compare explicitement les nouvelles données avec l'historique lorsque c'est possible. "
        "Indique si une tendance se confirme, s'améliore, s'inverse ou reste incertaine.\n"
        "Structure attendue:\n"
        "1. Résumé du jour\n"
        "2. Tendances notables\n"
        "3. Points de vigilance\n"
        "4. Conseils concrets pour les prochaines 24-48h\n"
        "5. Questions utiles à poser à l'utilisateur\n\n"
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
) -> dict[str, Any]:
    settings = get_settings()
    services = get_services()
    services.state_store.init_db()

    days = max(1, min(days, 90))
    model = settings.health_coach_model or settings.default_chat_model
    review_id = f"health-review-{uuid.uuid4().hex}"
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
            user_prompt=_user_prompt(features, review_history, structured_review),
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
    args = parser.parse_args()

    result = await generate_daily_health_review(
        days=args.days,
        store=not args.no_store,
        history_limit=args.history_limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
