from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings
from app.services.state_store import StateStore
from app.telegram.client import TelegramClient, parse_chat_ids

TIME_RE = re.compile(r"^(?P<hour>[01]?\d|2[0-3])[:h](?P<minute>[0-5]\d)$")


def normalize_time_of_day(value: str) -> str:
    match = TIME_RE.match(value.strip())
    if not match:
        raise ValueError("time_of_day must use HH:MM, for example 19:30")
    return f"{int(match.group('hour')):02d}:{int(match.group('minute')):02d}"


def normalize_timezone(value: str | None) -> str:
    timezone_name = (value or get_settings().reminder_timezone).strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone_name}") from exc
    return timezone_name


def create_daily_reminder(
    *,
    text: str,
    time_of_day: str,
    user_id: str = "telegram:automation",
    chat_id: str | int | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("reminder text is required")
    return _state_store().create_reminder(
        reminder_id=f"rem-{uuid.uuid4().hex[:10]}",
        user_id=user_id.strip() or "telegram:automation",
        chat_id=str(chat_id) if chat_id is not None else None,
        text=clean_text,
        frequency="daily",
        time_of_day=normalize_time_of_day(time_of_day),
        timezone_name=normalize_timezone(timezone_name),
    )


def list_reminders(*, user_id: str | None = None, active_only: bool = True, limit: int = 50) -> list[dict[str, Any]]:
    return _state_store().list_reminders(user_id=user_id, active_only=active_only, limit=limit)


def delete_reminder(reminder_id: str, *, user_id: str | None = None) -> dict[str, Any] | None:
    return _state_store().deactivate_reminder(reminder_id.strip(), user_id=user_id)


def send_due_reminders(now: datetime | None = None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return {"sent": 0, "skipped": 0, "reason": "missing_telegram_bot_token"}

    client = TelegramClient(settings.telegram_bot_token)
    state_store = _state_store()
    reminders = state_store.list_reminders(active_only=True, limit=100)
    fallback_chat_ids = parse_chat_ids(settings.telegram_notify_chat_ids) or parse_chat_ids(
        settings.telegram_allowed_chat_ids
    )
    sent: list[str] = []
    skipped = 0

    for reminder in reminders:
        timezone_name = str(reminder.get("timezone") or settings.reminder_timezone)
        local_now = _now_for_reminder(now, timezone_name)
        today = local_now.date().isoformat()
        due_time = str(reminder.get("time_of_day") or "")
        if str(reminder.get("frequency") or "daily") != "daily":
            skipped += 1
            continue
        if local_now.strftime("%H:%M") < due_time:
            skipped += 1
            continue
        if reminder.get("last_sent_date") == today:
            skipped += 1
            continue

        chat_ids = [reminder["chat_id"]] if reminder.get("chat_id") else [str(item) for item in fallback_chat_ids]
        if not chat_ids:
            skipped += 1
            continue

        text = f"Rappel: {reminder.get('text')}"
        for chat_id in chat_ids:
            client.send_message(chat_id, text)
        state_store.mark_reminder_sent(str(reminder["reminder_id"]), today)
        sent.append(str(reminder["reminder_id"]))

    return {"sent": len(sent), "sentReminderIds": sent, "skipped": skipped}


def _state_store() -> StateStore:
    return StateStore(get_settings())


def _now_for_reminder(now: datetime | None, timezone_name: str) -> datetime:
    tz = ZoneInfo(normalize_timezone(timezone_name))
    if now is None:
        return datetime.now(tz)
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)
