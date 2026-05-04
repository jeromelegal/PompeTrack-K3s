from __future__ import annotations

from typing import Any


def format_latest_review(review: dict[str, Any]) -> str:
    structured = review.get("structuredReview") or {}
    features = review.get("features") or {}
    lines = [
        "Dernière revue santé",
        f"ID: {review.get('review_id')}",
        f"Statut: {review.get('status')}",
        f"Date: {review.get('review_date')} | période: {review.get('period_days')} jours",
        "",
        format_counts(features.get("counts") or {}),
        "",
        format_data_confidence(structured.get("dataConfidence") or features.get("dataQuality") or {}),
        "",
        format_watch_items(structured.get("watchItems") or features.get("watchItems") or []),
    ]
    text = "\n".join(line for line in lines if line is not None).strip()
    review_text = (review.get("review_text") or "").strip()
    if review_text:
        text += "\n\nRésumé coach:\n" + compact_text(review_text, max_chars=1800)
    return text


def format_review_result(result: dict[str, Any]) -> str:
    return format_latest_review(
        {
            "review_id": result.get("reviewId"),
            "status": "completed",
            "review_date": result.get("reviewDate"),
            "period_days": result.get("periodDays"),
            "features": result.get("features"),
            "structuredReview": result.get("structuredReview"),
            "review_text": result.get("review"),
        }
    )


def format_features(features: dict[str, Any]) -> str:
    return "\n\n".join(
        part
        for part in [
            "Features santé récentes",
            format_counts(features.get("counts") or {}),
            format_data_confidence(features.get("dataQuality") or {}),
            format_watch_items(features.get("watchItems") or []),
        ]
        if part
    )


def format_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "Comptages: aucun."
    items = ", ".join(f"{key}={value}" for key, value in counts.items())
    return f"Comptages: {items}"


def format_data_confidence(data_quality: dict[str, Any]) -> str:
    if not data_quality:
        return "Qualité données: inconnue."
    missing = data_quality.get("missingSources") or []
    stale = data_quality.get("staleSources") or []
    lines = [
        f"Qualité données: {data_quality.get('level', 'unknown')} (score {data_quality.get('score', 'n/a')})",
    ]
    if missing:
        lines.append("Sources absentes: " + ", ".join(str(item) for item in missing))
    if stale:
        lines.append("Sources anciennes: " + ", ".join(str(item) for item in stale))
    return "\n".join(lines)


def format_watch_items(watch_items: list[dict[str, Any]]) -> str:
    if not watch_items:
        return "Points de vigilance: aucun signal déterministe."
    lines = ["Points de vigilance:"]
    for item in watch_items[:8]:
        label = item.get("label") or item.get("type") or "signal"
        severity = item.get("severity") or "info"
        reason = item.get("reason") or ""
        lines.append(f"- [{severity}] {label}: {reason}".rstrip())
    return "\n".join(lines)


def compact_text(text: str, *, max_chars: int = 1800) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."
