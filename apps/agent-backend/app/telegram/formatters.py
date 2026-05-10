from __future__ import annotations

from datetime import date
from typing import Any


SOURCE_LABELS = {
    "metrics": "mesures",
    "medications": "médicaments",
    "symptoms": "symptômes",
    "stateofminds": "humeur",
    "workouts": "entraînements",
    "spirometry": "spirométrie",
    "manualMonthly": "manuel",
}


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


def format_review_brief(review: dict[str, Any]) -> str:
    structured = review.get("structuredReview") or {}
    features = review.get("features") or {}
    review_text = (review.get("review_text") or "").strip()
    lines = [
        "Dernière revue santé",
        f"Date: {review.get('review_date')} | période: {review.get('period_days')} jours",
        format_data_confidence(structured.get("dataConfidence") or features.get("dataQuality") or {}),
        format_personal_watchlist(structured.get("personalWatchlist") or features.get("personalWatchlist") or []),
        format_anomalies(structured.get("anomalies") or features.get("anomalies") or []),
        format_watch_items(structured.get("watchItems") or features.get("watchItems") or []),
    ]
    if review_text:
        lines.extend(["", "Résumé coach:", compact_text(review_text, max_chars=900)])
    lines.extend(["", "Détail complet: /details", "Feedback: /feedback useful|long|false-positive"])
    return "\n".join(line for line in lines if line is not None).strip()


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


def format_review_result_brief(result: dict[str, Any]) -> str:
    return format_review_brief(_review_result_to_stored_shape(result))


def _review_result_to_stored_shape(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "review_id": result.get("reviewId"),
        "status": "completed",
        "review_date": result.get("reviewDate"),
        "period_days": result.get("periodDays"),
        "features": result.get("features"),
        "structuredReview": result.get("structuredReview"),
        "review_text": result.get("review"),
    }


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
    level = str(data_quality.get("level", "unknown"))
    level_label = {
        "high": "haute",
        "medium": "moyenne",
        "low": "faible",
        "unknown": "inconnue",
    }.get(level, level)
    lines = [
        f"Confiance données: {level_label} (score {data_quality.get('score', 'n/a')})",
    ]
    if missing:
        lines.append("Raisons: sources absentes: " + ", ".join(_source_label(item) for item in missing))
    if stale:
        prefix = "Raisons: " if not missing else "Sources anciennes: "
        lines.append(prefix + ", ".join(_source_label(item) for item in stale))
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


def format_alerts(result: dict[str, Any]) -> str:
    alerts = result.get("alerts") or []
    if not alerts:
        return "Alertes configurables: aucune alerte déterministe."
    lines = ["Alertes configurables"]
    for alert in alerts[:8]:
        severity = alert.get("severity") or "info"
        label = alert.get("label") or alert.get("ruleId") or "alerte"
        reason = alert.get("reason") or ""
        lines.append(f"- [{severity}] {label}: {reason}".rstrip())
    lines.append("")
    lines.append("Notification douce: à vérifier dans le contexte réel, sans diagnostic automatique.")
    return "\n".join(lines)


def format_anomalies(anomalies: list[dict[str, Any]]) -> str:
    if not anomalies:
        return "Anomalies personnelles: aucun signal déterministe."
    lines = ["Anomalies personnelles:"]
    for item in anomalies[:8]:
        label = item.get("label") or "signal"
        severity = item.get("severity") or "info"
        reason = item.get("reason") or ""
        lines.append(f"- [{severity}] {label}: {reason}".rstrip())
    return "\n".join(lines)


def format_personal_watchlist(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Watchlist personnalisée: vide."
    lines = ["Watchlist personnalisée:"]
    for item in items[:8]:
        label = item.get("label") or item.get("id") or "signal"
        status = item.get("status") or "unknown"
        reason = item.get("reason") or ""
        lines.append(f"- [{status}] {label}: {reason}".rstrip())
    return "\n".join(lines)


def format_correlations(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Corrélations prudentes: aucune piste déterministe."
    lines = ["Corrélations prudentes:"]
    for item in items[:6]:
        confidence = item.get("confidence") or "low"
        reason = item.get("reason") or ""
        lines.append(f"- [{confidence}] {reason}".rstrip())
    return "\n".join(lines)


def format_goals(goals: list[dict[str, Any]]) -> str:
    if not goals:
        return "Objectifs légers: aucun."
    lines = ["Objectifs légers:"]
    for goal in goals[:6]:
        label = goal.get("label") or goal.get("id") or "objectif"
        current = goal.get("current")
        target = goal.get("target")
        unit = goal.get("unit") or ""
        status = goal.get("status") or "active"
        lines.append(f"- [{status}] {label}: {current}/{target} {unit}".rstrip())
    return "\n".join(lines)


def format_preferences(prefs: dict[str, Any]) -> str:
    lines = [
        "Mémoire utilisateur explicite",
        f"Ton: {prefs.get('tone')}",
        f"Style de réponse: {prefs.get('answerStyle')}",
        f"Sensibilité alertes: {prefs.get('alertSensitivity')}",
        "Bilans automatiques: "
        + ("activés" if prefs.get("scheduledHealthReviewsEnabled", True) else "désactivés"),
        "",
        "Horaires:",
    ]
    for key, value in (prefs.get("notificationTimes") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Objectifs actifs:")
    for goal in prefs.get("activeGoals") or []:
        lines.append(f"- {goal}")
    lines.append("")
    lines.append("Symptômes prioritaires:")
    for symptom in prefs.get("prioritySymptoms") or []:
        lines.append(f"- {symptom}")
    sensitive = prefs.get("sensitiveTopics") or []
    lines.append("")
    lines.append("Sujets sensibles: " + (", ".join(str(item) for item in sensitive) if sensitive else "aucun"))
    lines.append("")
    lines.append("Modifier: /setpref <clé> <valeur>")
    lines.append("Listes: /addsymptom fatigue, /delsymptom fatigue")
    return "\n".join(lines)


def format_feedback_result(result: dict[str, Any]) -> str:
    feedback_type = result.get("feedbackType")
    lines = [f"Feedback enregistré: {feedback_type}"]
    prefs = result.get("preferences") or {}
    if feedback_type == "too_long":
        lines.append("J'ai ajusté le style vers des réponses plus concises.")
    elif feedback_type == "false_positive":
        lines.append("J'ai abaissé la sensibilité des alertes pour limiter les faux positifs.")
    elif feedback_type == "useful":
        lines.append("Parfait, je garde ce niveau de détail comme référence.")
    if prefs:
        lines.append("")
        lines.append(f"Style actuel: {prefs.get('answerStyle')} | sensibilité: {prefs.get('alertSensitivity')}")
    return "\n".join(lines)


def format_reminder(reminder: dict[str, Any]) -> str:
    status = "actif" if reminder.get("active") else "supprimé"
    return (
        f"Rappel {reminder.get('reminder_id')} ({status})\n"
        f"- Tous les jours à {reminder.get('time_of_day')} ({reminder.get('timezone')})\n"
        f"- {reminder.get('text')}"
    )


def format_reminders(reminders: list[dict[str, Any]]) -> str:
    if not reminders:
        return "Aucun rappel actif."
    lines = ["Rappels actifs"]
    for reminder in reminders:
        lines.append(
            f"- {reminder.get('reminder_id')} | {reminder.get('time_of_day')} "
            f"({reminder.get('timezone')}) | {reminder.get('text')}"
        )
    lines.append("")
    lines.append("Supprimer: /delreminder <id>")
    return "\n".join(lines)


def format_guided_actions(features: dict[str, Any], prefs: dict[str, Any]) -> str:
    counts = features.get("counts") or {}
    watch_items = features.get("watchItems") or []
    anomalies = features.get("anomalies") or []
    actions = [
        {
            "label": "Lancer une revue longue sur 90 jours",
            "command": "/weekly-review",
            "reason": "Utile pour les tendances lentes et la baseline personnelle.",
        },
        {
            "label": "Poser une question clinique prudente",
            "command": "/why pourquoi je suis fatigué ?",
            "reason": "Réponse structurée: observations, hypothèses, données manquantes, signaux d'alerte.",
        },
    ]
    if counts.get("symptoms") or any(item.get("source") == "symptoms" for item in anomalies):
        actions.append({
            "label": "Créer une note symptôme",
            "command": "/note symptom fatigue intensité ? contexte ?",
            "reason": "Je prépare une note structurée à valider, sans écrire automatiquement dans Medplum.",
        })
    if any(item.get("type") == "medication" for item in watch_items):
        actions.append({
            "label": "Clarifier une prise médicament",
            "command": "/note medication prise confirmée ? heure ?",
            "reason": "Utile si le suivi médicament semble incomplet.",
        })
    if prefs.get("prioritySymptoms"):
        actions.append({
            "label": "Voir la watchlist personnalisée",
            "command": "/watchlist",
            "reason": "Se concentrer sur les signaux prioritaires plutôt que tout surveiller.",
        })

    lines = ["Actions guidées:"]
    for action in actions[:6]:
        lines.append(f"- {action['label']}: {action['command']}")
        lines.append(f"  {action['reason']}")
    return "\n".join(lines)


def format_structured_note(kind: str, text: str) -> str:
    kind_label = {
        "symptom": "note symptôme",
        "medication": "note médicament",
    }.get(kind, "note")
    return "\n".join([
        f"Brouillon de {kind_label}",
        compact_text(text, max_chars=1200),
        "",
        "Je ne l'écris pas automatiquement dans Medplum pour l'instant.",
        "Validation future possible: confirmer, compléter l'heure, intensité, contexte.",
    ])


def compact_text(text: str, *, max_chars: int = 1800) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def format_today(features: dict[str, Any]) -> str:
    counts = features.get("counts") or {}
    events = features.get("recentEvents") or []
    watch_items = features.get("watchItems") or []
    data_quality = features.get("dataQuality") or {}

    parts = [
        f"Aujourd'hui - {date.today().isoformat()}",
        format_today_counts(counts),
        format_today_events(events),
        format_watch_items(watch_items[:4]),
        format_anomalies(features.get("anomalies") or []),
        format_data_confidence(data_quality),
    ]
    return "\n\n".join(part for part in parts if part).strip()


def format_today_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "Données reçues: aucune donnée récente."

    items = [
        f"{label}: {counts[key]}"
        for key, label in SOURCE_LABELS.items()
        if counts.get(key)
    ]
    if not items:
        return "Données reçues: aucune donnée récente."
    return "Données reçues: " + ", ".join(items)


def format_today_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "Derniers événements: aucun événement récent."

    lines = ["Derniers événements:"]
    for event in events[:8]:
        lines.append("- " + format_event(event))
    return "\n".join(lines)


def format_event(event: dict[str, Any]) -> str:
    event_type = event.get("type") or "event"
    label = event.get("label") or event.get("id") or "sans libellé"
    value = event.get("value")
    unit = event.get("unit")
    status = event.get("status")
    severity = event.get("severity")
    event_date = event.get("date")

    details = []
    if value is not None:
        details.append(str(value) + (f" {unit}" if unit else ""))
    if status:
        details.append(f"statut {status}")
    if severity:
        details.append(f"sévérité {severity}")

    suffix = f" ({', '.join(details)})" if details else ""
    when = f" - {event_date}" if event_date else ""
    return f"{event_type}: {label}{suffix}{when}"


def format_week(features: dict[str, Any]) -> str:
    return "\n\n".join(
        part
        for part in [
            "Semaine santé",
            format_today_counts(features.get("counts") or {}),
            format_top_items("Symptômes fréquents", features.get("topSymptoms") or []),
            format_personal_watchlist(features.get("personalWatchlist") or []),
            format_anomalies(features.get("anomalies") or []),
            format_correlations(features.get("cautiousCorrelations") or []),
            format_goals(features.get("goals") or []),
            format_trend_group("Tendances mesures", features.get("metricTrends") or [], limit=6),
            format_trend_group("Tendances humeur", features.get("stateOfMindTrends") or [], limit=4),
            format_watch_items(features.get("watchItems") or []),
            format_data_confidence(features.get("dataQuality") or {}),
        ]
        if part
    )


def format_trends(features: dict[str, Any]) -> str:
    return "\n\n".join(
        part
        for part in [
            "Tendances récentes",
            format_trend_group("Mesures", features.get("metricTrends") or [], limit=8),
            format_trend_group("Humeur", features.get("stateOfMindTrends") or [], limit=6),
            format_trend_group("Spirométrie", features.get("spirometryTrends") or [], limit=6),
            format_trend_group("Mesures manuelles", features.get("manualMonthlyTrends") or [], limit=6),
            format_anomalies(features.get("anomalies") or []),
            format_correlations(features.get("cautiousCorrelations") or []),
            format_data_confidence(features.get("dataQuality") or {}),
        ]
        if part
    )


def format_watchlist(features: dict[str, Any]) -> str:
    return "\n\n".join(
        part
        for part in [
            "Suivi personnalisé",
            format_personal_watchlist(features.get("personalWatchlist") or []),
            format_anomalies(features.get("anomalies") or []),
            format_correlations(features.get("cautiousCorrelations") or []),
            format_goals(features.get("goals") or []),
        ]
        if part
    )


def format_medication(features: dict[str, Any]) -> str:
    medications = features.get("recentMedication") or []
    lines = ["Médicaments récents"]
    if not medications:
        lines.append("Aucune administration récente trouvée.")
    for item in medications[:10]:
        label = item.get("medication") or item.get("label") or item.get("display") or "médicament"
        status = item.get("status")
        dosage = item.get("dosage")
        item_date = item.get("date") or item.get("effectiveDateTime")
        details = ", ".join(str(value) for value in [status, dosage] if value)
        suffix = f" ({details})" if details else ""
        when = f" - {item_date}" if item_date else ""
        lines.append(f"- {label}{suffix}{when}")
    return "\n".join(lines)


def format_symptoms(features: dict[str, Any]) -> str:
    symptom_events = [event for event in features.get("recentEvents") or [] if event.get("type") == "symptom"]
    return "\n\n".join(
        part
        for part in [
            "Symptômes récents",
            format_top_items("Fréquence", features.get("topSymptoms") or []),
            format_today_events(symptom_events[:10]) if symptom_events else "Derniers événements: aucun symptôme récent.",
        ]
        if part
    )


def format_spirometry(features: dict[str, Any]) -> str:
    spirometry_events = [event for event in features.get("recentEvents") or [] if event.get("type") == "spirometry"]
    return "\n\n".join(
        part
        for part in [
            "Spirométrie récente",
            format_trend_group("Tendances", features.get("spirometryTrends") or [], limit=8),
            format_today_events(spirometry_events[:10]) if spirometry_events else "Derniers événements: aucune spirométrie récente.",
        ]
        if part
    )


def format_workouts(features: dict[str, Any]) -> str:
    workout_events = [event for event in features.get("recentEvents") or [] if event.get("type") == "workout"]
    lines = ["Entraînements récents"]
    if not workout_events:
        lines.append("Aucun entraînement récent trouvé.")
    for event in workout_events[:10]:
        lines.append("- " + format_event(event))
    return "\n".join(lines)


def format_reviews_list(reviews: list[dict[str, Any]], *, limit: int = 7) -> str:
    if not reviews:
        return "Aucune revue santé persistée."
    lines = ["Historique des revues:"]
    for review in reviews[:limit]:
        status = review.get("status") or "unknown"
        review_date = review.get("review_date")
        review_id = review.get("review_id")
        lines.append(f"- {review_date} [{status}] {review_id}")
    lines.append("")
    lines.append("Détail: /review YYYY-MM-DD ou /review <review_id>")
    return "\n".join(lines)


def format_evening_questions(features: dict[str, Any]) -> str:
    questions = build_evening_questions(features)
    lines = ["Questions du soir"]
    if not questions:
        lines.append("Rien d'évident à te demander ce soir. Tu peux juste noter un ressenti libre si utile.")
    for index, question in enumerate(questions, start=1):
        lines.append(f"{index}. {question}")
    lines.append("")
    lines.append("Tu peux répondre directement ici, ou utiliser /ask si tu veux une analyse.")
    return "\n".join(lines)


def build_evening_questions(features: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    watch_items = features.get("watchItems") or []
    counts = features.get("counts") or {}
    top_symptoms = features.get("topSymptoms") or []
    mood_trends = features.get("stateOfMindTrends") or []

    for item in watch_items:
        item_type = item.get("type")
        label = item.get("label") or "signal"
        if item_type == "medication":
            questions.append("Pas de prise médicament enregistrée aujourd'hui: oubli, arrêt prévu ou donnée manquante ?")
        elif item_type == "mood":
            questions.append(f"Humeur basse détectée ({label}): tu veux noter ce qui a pesé aujourd'hui ?")
        elif item_type == "possible_missing_data":
            questions.append(f"{label}: beaucoup de zéros récents. Synchro absente ou vraie baisse ?")
        elif item_type == "data_quality":
            questions.append("Certaines sources semblent absentes ou anciennes: tu veux vérifier la synchro ?")

    if counts.get("symptoms") and top_symptoms:
        questions.append(f"Symptôme le plus présent: {top_symptoms[0].get('label')}. Intensité stable, meilleure ou pire ce soir ?")
    if counts.get("workouts"):
        questions.append("Après l'entraînement du jour: récupération correcte ou fatigue inhabituelle ?")
    if not counts.get("stateofminds") and mood_trends:
        questions.append("Pas de note d'humeur aujourd'hui: tu veux ajouter un ressenti rapide ?")

    deduped = []
    for question in questions:
        if question not in deduped:
            deduped.append(question)
    return deduped[:3]


def format_trend_group(title: str, trends: list[dict[str, Any]], *, limit: int = 8) -> str:
    if not trends:
        return f"{title}: aucune tendance exploitable."

    lines = [f"{title}:"]
    for trend in trends[:limit]:
        label = trend.get("label") or "mesure"
        latest = trend.get("latest")
        delta = trend.get("delta")
        unit = trend.get("unit")
        details = []
        if latest is not None:
            details.append("dernier " + str(latest) + (f" {unit}" if unit else ""))
        if delta is not None:
            sign = "+" if isinstance(delta, (int, float)) and delta > 0 else ""
            details.append(f"delta {sign}{delta}" + (f" {unit}" if unit else ""))
        if trend.get("dataNote"):
            details.append(str(trend["dataNote"]))
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"- {label}{suffix}")
    return "\n".join(lines)


def format_top_items(title: str, items: list[dict[str, Any]], *, limit: int = 8) -> str:
    if not items:
        return f"{title}: aucun."
    lines = [f"{title}:"]
    for item in items[:limit]:
        lines.append(f"- {item.get('label', 'item')}: {item.get('count', 0)}")
    return "\n".join(lines)


def _source_label(source: Any) -> str:
    return SOURCE_LABELS.get(str(source), str(source))
