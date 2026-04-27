from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings


class StateStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _connect(self) -> sqlite3.Connection:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.settings.state_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    model TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stop_reason TEXT,
                    final_answer TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                )
                """
            )

    def create_run(self, run_id: str, session_id: str, user_id: str | None, model: str, goal: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, session_id, user_id, model, goal, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, session_id, user_id, model, goal, "running", now, now),
            )

    def add_event(self, run_id: str, node: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO trace_events(run_id, node, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, node, json.dumps(payload, ensure_ascii=False), now),
            )
            conn.execute(
                "UPDATE runs SET updated_at = ? WHERE run_id = ?",
                (now, run_id),
            )

    def finish_run(self, run_id: str, status: str, stop_reason: str, final_answer: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE runs
                SET status = ?, stop_reason = ?, final_answer = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, stop_reason, final_answer, now, run_id),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                return None
            events = conn.execute(
                "SELECT node, payload_json, created_at FROM trace_events WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
        return {
            **dict(run),
            "events": [
                {
                    "node": event["node"],
                    "created_at": event["created_at"],
                    "payload": json.loads(event["payload_json"]),
                }
                for event in events
            ],
        }

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT run_id, session_id, user_id, model, goal, status, stop_reason, created_at, updated_at
                FROM runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
