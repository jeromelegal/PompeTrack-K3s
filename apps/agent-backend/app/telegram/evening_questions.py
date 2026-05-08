from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.medplum.health_coach import build_daily_health_features
from app.telegram.client import TelegramClient, parse_chat_ids
from app.telegram.formatters import format_evening_questions

logger = logging.getLogger(__name__)


def send_evening_questions() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("telegram evening questions skipped: TELEGRAM_BOT_TOKEN is missing")
        return

    chat_ids = parse_chat_ids(settings.telegram_notify_chat_ids) or parse_chat_ids(
        settings.telegram_allowed_chat_ids
    )
    if not chat_ids:
        logger.warning("telegram evening questions skipped: no chat id configured")
        return

    features = build_daily_health_features(days=1)
    text = format_evening_questions(features)
    client = TelegramClient(settings.telegram_bot_token)
    for chat_id in chat_ids:
        try:
            client.send_message(chat_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "failed to send telegram evening questions",
                extra={"chat_id": chat_id, "error": str(exc)},
            )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    send_evening_questions()


if __name__ == "__main__":
    main()
