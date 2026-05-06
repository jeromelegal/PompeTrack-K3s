from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.telegram.client import TelegramClient, parse_chat_ids
from app.telegram.formatters import format_review_result_brief

logger = logging.getLogger(__name__)


async def notify_daily_health_review(result: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.telegram_daily_review_enabled:
        return
    if not settings.telegram_bot_token:
        logger.warning("telegram daily review enabled but TELEGRAM_BOT_TOKEN is missing")
        return

    chat_ids = parse_chat_ids(settings.telegram_notify_chat_ids) or parse_chat_ids(
        settings.telegram_allowed_chat_ids
    )
    if not chat_ids:
        logger.warning("telegram daily review enabled but no notify chat id is configured")
        return

    client = TelegramClient(settings.telegram_bot_token)
    text = format_review_result_brief(result)
    for chat_id in chat_ids:
        try:
            client.send_message(chat_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to send telegram health review", extra={"chat_id": chat_id, "error": str(exc)})
