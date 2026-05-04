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
    create_health_summary,
    get_health_timeline,
    get_recent_medication,
    get_recent_manual_monthly,
    get_recent_metrics,
    get_recent_spirometry,
    get_recent_stateofminds,
    get_recent_symptoms,
    get_recent_workouts,
)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
        except ValueError:
            return None


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
            }
        )

    return trends


def _top_counts(items: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    counts = Counter(_label(item) for item in items)
    return [{"label": label, "count": count} for label, count in counts.most_common(limit)]


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

    summary = create_health_summary(days=days)
    timeline = get_health_timeline(days=min(days, 30))
    metrics = get_recent_metrics(days=days)
    stateofminds = get_recent_stateofminds(days=days)
    symptoms = get_recent_symptoms(days=days)
    medications = get_recent_medication(days=days)
    workouts = get_recent_workouts(days=days)
    spirometry = get_recent_spirometry(days=days)
    manual_monthly = get_recent_manual_monthly(days=days)

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "period": summary.get("period"),
        "counts": {
            **summary.get("counts", {}),
            "workouts": len(workouts),
            "spirometry": len(spirometry),
            "manualMonthly": len(manual_monthly),
        },
        "metricTrends": _numeric_trends(metrics),
        "stateOfMindTrends": _numeric_trends(stateofminds),
        "spirometryTrends": _numeric_trends(spirometry),
        "manualMonthlyTrends": _numeric_trends(manual_monthly),
        "topSymptoms": _top_counts(symptoms),
        "recentMedication": medications[:10],
        "recentEvents": timeline.get("events", [])[:30],
    }


def _system_prompt() -> str:
    return (
        "Tu es un coach santé prudent, bienveillant et factuel. "
        "Tu analyses des tendances personnelles issues de données FHIR. "
        "Tu ne poses pas de diagnostic médical. "
        "Tu distingues observations, hypothèses et actions raisonnables. "
        "Tu recommandes de contacter un professionnel de santé en cas de symptôme inquiétant, "
        "aggravation nette, effet indésirable ou doute."
    )


def _user_prompt(features: dict[str, Any], review_history: list[dict[str, Any]] | None = None) -> str:
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
            user_prompt=_user_prompt(features, review_history),
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
        )

    return {
        "reviewId": review_id,
        "reviewDate": date.today().isoformat(),
        "periodDays": days,
        "model": model,
        "features": features,
        "history": review_history,
        "review": review_text,
    }


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
