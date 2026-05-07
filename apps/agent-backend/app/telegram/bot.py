from __future__ import annotations

import logging
import signal
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.telegram.backend import BackendClient
from app.telegram.client import TelegramClient, parse_chat_ids
from app.telegram.formatters import (
    format_evening_questions,
    format_alerts,
    format_feedback_result,
    format_features,
    format_guided_actions,
    format_latest_review,
    format_medication,
    format_preferences,
    format_review_brief,
    format_review_result_brief,
    format_reviews_list,
    format_spirometry,
    format_structured_note,
    format_symptoms,
    format_today,
    format_trends,
    format_watchlist,
    format_week,
    format_workouts,
)

logger = logging.getLogger(__name__)

HELP_TEXT = """Commandes disponibles:
/id - affiche l'ID du chat Telegram
/latest - dernière revue santé, version courte
/details - dernière revue santé complète
/reviews 7 - historique des revues
/review YYYY-MM-DD - détail d'une revue
/today - synthèse déterministe des dernières 24h
/week - synthèse déterministe des 7 derniers jours
/trends - tendances récentes
/watchlist - suivi personnalisé
/meds - médicaments récents
/symptoms - symptômes récents
/spirometry - spirométrie récente
/workouts - entraînements récents
/evening - questions ciblées du soir
/alerts - évalue les alertes configurables
/weekly-review - lance un bilan hebdomadaire maintenant
/prefs - affiche la mémoire utilisateur
/setpref <clé> <valeur> - modifie une préférence
/addsymptom <nom> - ajoute un symptôme prioritaire
/delsymptom <nom> - retire un symptôme prioritaire
/feedback useful|long|false-positive [commentaire]
/actions - propose des actions guidées
/note symptom|medication <texte> - prépare une note structurée
/why <question> - réponse clinique prudente sans diagnostic
/features - synthèse déterministe des données récentes
/coach - lance une nouvelle revue santé maintenant
/ask <question> - pose une question libre au LLM

Tu peux aussi envoyer directement une question sans commande."""


class TelegramHealthBot:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
        if not self.settings.backend_api_key:
            raise RuntimeError("BACKEND_API_KEY is required")

        self.telegram = TelegramClient(
            self.settings.telegram_bot_token,
            timeout_seconds=self.settings.telegram_command_timeout_seconds,
        )
        self.backend = BackendClient(
            base_url=self.settings.agent_backend_base_url,
            api_key=self.settings.backend_api_key,
            timeout_seconds=self.settings.telegram_command_timeout_seconds,
        )
        self.allowed_chat_ids = set(parse_chat_ids(self.settings.telegram_allowed_chat_ids))
        self.running = True

    def run(self) -> None:
        offset: int | None = None
        logger.info("telegram bot polling started")

        while self.running:
            try:
                updates = self.telegram.get_updates(
                    offset=offset,
                    timeout_seconds=self.settings.telegram_poll_timeout_seconds,
                )
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    self._handle_update(update)
            except Exception as exc:  # noqa: BLE001
                logger.warning("telegram bot polling error", extra={"error": str(exc)})
                time.sleep(5)

        logger.info("telegram bot stopped")

    def stop(self, *_args: Any) -> None:
        self.running = False

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        user = message.get("from") or {}
        user_id = user.get("id")

        if not chat_id or not text:
            return

        if not self._is_allowed(int(chat_id)):
            self.telegram.send_message(
                chat_id,
                f"Accès refusé. Chat ID à autoriser: {chat_id}",
                disable_notification=True,
            )
            return

        try:
            self._dispatch(text=text, chat_id=int(chat_id), user_id=str(user_id or chat_id))
        except Exception as exc:  # noqa: BLE001
            logger.exception("telegram command failed")
            self.telegram.send_message(chat_id, f"Erreur pendant la commande: {exc}")

    def _is_allowed(self, chat_id: int) -> bool:
        return not self.allowed_chat_ids or chat_id in self.allowed_chat_ids

    def _dispatch(self, *, text: str, chat_id: int, user_id: str) -> None:
        command, _, rest = text.partition(" ")
        command = command.lower()

        if command in {"/start", "/help"}:
            self.telegram.send_message(chat_id, HELP_TEXT)
            return
        if command == "/id":
            self.telegram.send_message(chat_id, f"Chat ID: {chat_id}")
            return
        if command == "/latest":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_review_brief(self.backend.latest_review()))
            return
        if command == "/details":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_latest_review(self.backend.latest_review()))
            return
        if command == "/reviews":
            self.telegram.send_chat_action(chat_id)
            limit = _parse_limit(rest, default=7, maximum=30)
            self.telegram.send_message(chat_id, format_reviews_list(self.backend.list_reviews(limit=limit), limit=limit))
            return
        if command == "/review":
            query = rest.strip()
            if not query:
                self.telegram.send_message(chat_id, "Utilisation: /review YYYY-MM-DD ou /review <review_id>")
                return
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_latest_review(self.backend.review_by_date_or_id(query)))
            return
        if command == "/features":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_features(self.backend.health_features(days=30)))
            return
        if command == "/prefs":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_preferences(self.backend.preferences(_pref_user_id(chat_id))))
            return
        if command == "/setpref":
            self._set_preference(chat_id=chat_id, rest=rest)
            return
        if command == "/addsymptom":
            self._edit_priority_symptom(chat_id=chat_id, symptom=rest, add=True)
            return
        if command == "/delsymptom":
            self._edit_priority_symptom(chat_id=chat_id, symptom=rest, add=False)
            return
        if command == "/feedback":
            self._feedback(chat_id=chat_id, rest=rest)
            return
        if command == "/actions":
            self.telegram.send_chat_action(chat_id)
            features = self.backend.health_features(days=30)
            prefs = self.backend.preferences(_pref_user_id(chat_id))
            self.telegram.send_message(chat_id, format_guided_actions(features, prefs))
            return
        if command == "/alerts":
            self.telegram.send_chat_action(chat_id)
            notify = rest.strip().lower() in {"notify", "send", "telegram"}
            self.telegram.send_message(chat_id, format_alerts(self.backend.alerts(days=30, notify=notify)))
            return
        if command == "/note":
            kind, _, note_text = rest.strip().partition(" ")
            if kind not in {"symptom", "medication"} or not note_text.strip():
                self.telegram.send_message(chat_id, "Utilisation: /note symptom fatigue intensité 6/10 après effort")
                return
            self.telegram.send_message(chat_id, format_structured_note(kind, note_text.strip()))
            return
        if command == "/why":
            prompt = rest.strip()
            if not prompt:
                self.telegram.send_message(chat_id, "Utilisation: /why pourquoi je suis fatigué ?")
                return
            self._ask_clinical(chat_id=chat_id, user_id=user_id, prompt=prompt)
            return
        if command == "/coach":
            self.telegram.send_message(chat_id, "Je lance une nouvelle revue santé. Cela peut prendre un peu de temps.")
            self.telegram.send_chat_action(chat_id)
            result = self.backend.run_daily_review(days=30, history_limit=7)
            self.telegram.send_message(chat_id, format_review_result_brief(result))
            return
        if command == "/weekly-review":
            self.telegram.send_message(chat_id, "Je lance un bilan hebdomadaire. Cela peut prendre un peu de temps.")
            self.telegram.send_chat_action(chat_id)
            result = self.backend.run_weekly_review(days=90, history_limit=7)
            self.telegram.send_message(chat_id, format_review_result_brief(result))
            return
        if command == "/ask":
            prompt = rest.strip()
            if not prompt:
                self.telegram.send_message(chat_id, "Utilisation: /ask ta question")
                return
            self._ask_llm(chat_id=chat_id, user_id=user_id, prompt=prompt)
            return
        if command == "/today":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_today(self.backend.health_features(days=1)))
            return
        if command == "/week":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_week(self.backend.health_features(days=7)))
            return
        if command == "/trends":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_trends(self.backend.health_features(days=30)))
            return
        if command == "/watchlist":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_watchlist(self.backend.health_features(days=30)))
            return
        if command == "/meds":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_medication(self.backend.health_features(days=30)))
            return
        if command == "/symptoms":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_symptoms(self.backend.health_features(days=30)))
            return
        if command == "/spirometry":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_spirometry(self.backend.health_features(days=30)))
            return
        if command == "/workouts":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_workouts(self.backend.health_features(days=30)))
            return
        if command == "/evening":
            self.telegram.send_chat_action(chat_id)
            self.telegram.send_message(chat_id, format_evening_questions(self.backend.health_features(days=1)))
            return
        if text.startswith("/"):
            self.telegram.send_message(chat_id, "Commande inconnue.\n\n" + HELP_TEXT)
            return

        if _looks_clinical_question(text):
            self._ask_clinical(chat_id=chat_id, user_id=user_id, prompt=text)
            return
        self._ask_llm(chat_id=chat_id, user_id=user_id, prompt=text)

    def _ask_llm(self, *, chat_id: int, user_id: str, prompt: str) -> None:
        self.telegram.send_chat_action(chat_id)
        answer = self.backend.chat(
            prompt=prompt,
            session_id=f"telegram-{chat_id}",
            user_id=f"telegram-{user_id}",
            model=self.settings.default_chat_model,
        )
        self.telegram.send_message(chat_id, answer)

    def _ask_clinical(self, *, chat_id: int, user_id: str, prompt: str) -> None:
        self.telegram.send_chat_action(chat_id)
        features = self.backend.health_features(days=30)
        prefs = self.backend.preferences(_pref_user_id(chat_id))
        clinical_prompt = (
            "Réponds en mode conversation clinique prudente, sans diagnostic médical. "
            "Structure la réponse en français avec: 1) observations disponibles, "
            "2) hypothèses prudentes non causales, 3) données manquantes, "
            "4) signaux d'alerte qui justifient un avis médical, 5) questions utiles. "
            "Tiens compte des préférences utilisateur suivantes, surtout les sujets sensibles et symptômes prioritaires:\n"
            f"{prefs}\n\n"
            "Données santé déterministes récentes:\n"
            f"{features}\n\n"
            f"Question utilisateur: {prompt}"
        )
        answer = self.backend.chat(
            prompt=clinical_prompt,
            session_id=f"telegram-clinical-{chat_id}",
            user_id=f"telegram-{user_id}",
            model=self.settings.default_chat_model,
        )
        self.telegram.send_message(chat_id, answer)

    def _set_preference(self, *, chat_id: int, rest: str) -> None:
        key, _, value = rest.strip().partition(" ")
        if not key or not value:
            self.telegram.send_message(
                chat_id,
                "Utilisation: /setpref tone bienveillant_concis\n"
                "Clés: tone, answerStyle, alertSensitivity, daily, evening, weekly, sensitiveTopics",
            )
            return
        patch: dict[str, Any]
        if key in {"daily", "evening", "weekly"}:
            prefs = self.backend.preferences(_pref_user_id(chat_id))
            notification_times = dict(prefs.get("notificationTimes") or {})
            notification_times[key] = value.strip()
            patch = {"notificationTimes": notification_times}
        elif key in {"sensitiveTopics", "activeGoals"}:
            patch = {key: _split_list(value)}
        elif key in {"tone", "answerStyle", "alertSensitivity"}:
            patch = {key: value.strip()}
        else:
            self.telegram.send_message(chat_id, "Clé inconnue. Essaie /prefs pour voir la mémoire actuelle.")
            return
        prefs = self.backend.update_preferences(_pref_user_id(chat_id), patch)
        self.telegram.send_message(chat_id, format_preferences(prefs))

    def _edit_priority_symptom(self, *, chat_id: int, symptom: str, add: bool) -> None:
        item = symptom.strip().lower()
        if not item:
            self.telegram.send_message(chat_id, "Utilisation: /addsymptom fatigue ou /delsymptom fatigue")
            return
        prefs = self.backend.preferences(_pref_user_id(chat_id))
        symptoms = [str(value).lower() for value in prefs.get("prioritySymptoms") or []]
        if add and item not in symptoms:
            symptoms.append(item)
        if not add:
            symptoms = [value for value in symptoms if value != item]
        prefs = self.backend.update_preferences(_pref_user_id(chat_id), {"prioritySymptoms": symptoms})
        self.telegram.send_message(chat_id, format_preferences(prefs))

    def _feedback(self, *, chat_id: int, rest: str) -> None:
        raw_type, _, comment = rest.strip().partition(" ")
        mapping = {
            "useful": "useful",
            "utile": "useful",
            "long": "too_long",
            "too_long": "too_long",
            "false-positive": "false_positive",
            "false_positive": "false_positive",
            "faux-positif": "false_positive",
        }
        feedback_type = mapping.get(raw_type.lower())
        if not feedback_type:
            self.telegram.send_message(chat_id, "Utilisation: /feedback useful|long|false-positive [commentaire]")
            return
        latest = None
        try:
            latest = self.backend.latest_review().get("review_id")
        except Exception:  # noqa: BLE001
            latest = None
        result = self.backend.submit_feedback(
            user_id=_pref_user_id(chat_id),
            feedback_type=feedback_type,
            review_id=latest,
            comment=comment.strip() or None,
        )
        self.telegram.send_message(chat_id, format_feedback_result(result))


def _parse_limit(raw: str, *, default: int, maximum: int) -> int:
    value = raw.strip()
    if not value:
        return default
    try:
        return max(1, min(int(value), maximum))
    except ValueError:
        return default


def _pref_user_id(chat_id: int) -> str:
    return f"telegram:{chat_id}"


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _looks_clinical_question(text: str) -> bool:
    normalized = text.lower()
    question_markers = ["pourquoi", "est-ce que", "que faire", "comment expliquer", "?"]
    health_terms = [
        "fatigu",
        "douleur",
        "souffle",
        "respir",
        "humeur",
        "médicament",
        "medicament",
        "sympt",
        "coeur",
        "cardiaque",
        "sommeil",
    ]
    return any(marker in normalized for marker in question_markers) and any(
        term in normalized for term in health_terms
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot = TelegramHealthBot()
    signal.signal(signal.SIGTERM, bot.stop)
    signal.signal(signal.SIGINT, bot.stop)
    bot.run()


if __name__ == "__main__":
    main()
