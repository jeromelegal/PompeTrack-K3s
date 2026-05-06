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
    format_features,
    format_latest_review,
    format_medication,
    format_review_brief,
    format_review_result_brief,
    format_reviews_list,
    format_spirometry,
    format_symptoms,
    format_today,
    format_trends,
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
/meds - médicaments récents
/symptoms - symptômes récents
/spirometry - spirométrie récente
/workouts - entraînements récents
/evening - questions ciblées du soir
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
        if command == "/coach":
            self.telegram.send_message(chat_id, "Je lance une nouvelle revue santé. Cela peut prendre un peu de temps.")
            self.telegram.send_chat_action(chat_id)
            result = self.backend.run_daily_review(days=30, history_limit=7)
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


def _parse_limit(raw: str, *, default: int, maximum: int) -> int:
    value = raw.strip()
    if not value:
        return default
    try:
        return max(1, min(int(value), maximum))
    except ValueError:
        return default


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    bot = TelegramHealthBot()
    signal.signal(signal.SIGTERM, bot.stop)
    signal.signal(signal.SIGINT, bot.stop)
    bot.run()


if __name__ == "__main__":
    main()
