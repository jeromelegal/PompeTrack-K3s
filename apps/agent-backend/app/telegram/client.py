from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramClient:
    def __init__(self, token: str, *, timeout_seconds: int = 30) -> None:
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.base_url = f"https://api.telegram.org/bot{token}"

    def get_updates(self, *, offset: int | None = None, timeout_seconds: int = 25) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout_seconds,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset

        data = self._request("getUpdates", payload=payload, timeout_seconds=timeout_seconds + 10)
        return data.get("result", [])

    def send_message(self, chat_id: int | str, text: str, *, disable_notification: bool = False) -> None:
        for part in split_telegram_text(text):
            self._request(
                "sendMessage",
                payload={
                    "chat_id": chat_id,
                    "text": part,
                    "disable_notification": disable_notification,
                },
            )

    def send_chat_action(self, chat_id: int | str, action: str = "typing") -> None:
        self._request("sendChatAction", payload={"chat_id": chat_id, "action": action})

    def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        self._request("setMyCommands", payload={"commands": commands})

    def _request(
        self,
        method: str,
        *,
        payload: dict[str, Any],
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds or self.timeout_seconds,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            logger.warning("telegram http error", extra={"method": method, "status": exc.code, "body": raw})
            raise RuntimeError(f"Telegram HTTP {exc.code}: {raw}") from exc
        except urllib.error.URLError as exc:
            logger.warning("telegram request failed", extra={"method": method, "error": str(exc)})
            raise RuntimeError(f"Telegram request failed: {exc}") from exc

        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data


def split_telegram_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    cleaned = text.strip() or "(message vide)"
    if len(cleaned) <= limit:
        return [cleaned]

    parts: list[str] = []
    remaining = cleaned
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def parse_chat_ids(value: str | None) -> list[int]:
    if not value:
        return []
    chat_ids = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        try:
            chat_ids.append(int(item))
        except ValueError:
            logger.warning("invalid telegram chat id ignored", extra={"chat_id": item})
    return chat_ids
