from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from app.api.security import require_api_key
from app.reminders import create_daily_reminder, delete_reminder, list_reminders, send_due_reminders

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


@router.get("", dependencies=[Depends(require_api_key)])
async def get_reminders(user_id: str | None = None, active_only: bool = True, limit: int = 50) -> dict[str, Any]:
    return {"items": list_reminders(user_id=user_id, active_only=active_only, limit=limit)}


@router.post("", dependencies=[Depends(require_api_key)])
async def create_reminder(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        item = create_daily_reminder(
            text=str(payload.get("text") or ""),
            time_of_day=str(payload.get("timeOfDay") or payload.get("time_of_day") or ""),
            user_id=str(payload.get("userId") or payload.get("user_id") or "telegram:automation"),
            chat_id=payload.get("chatId") or payload.get("chat_id"),
            timezone_name=payload.get("timezone"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item}


@router.delete("/{reminder_id}", dependencies=[Depends(require_api_key)])
async def remove_reminder(reminder_id: str, user_id: str | None = None) -> dict[str, Any]:
    item = delete_reminder(reminder_id, user_id=user_id)
    if item is None:
        raise HTTPException(status_code=404, detail="reminder not found")
    return {"item": item}


@router.post("/send-due", dependencies=[Depends(require_api_key)])
async def run_due_reminders() -> dict[str, Any]:
    return send_due_reminders()
