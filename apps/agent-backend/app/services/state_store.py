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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS health_reviews (
                    review_id TEXT PRIMARY KEY,
                    review_date TEXT NOT NULL,
                    period_days INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    features_json TEXT NOT NULL,
                    review_text TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_health_reviews_created_at
                ON health_reviews(created_at DESC)
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

    def create_health_review(
        self,
        *,
        review_id: str,
        review_date: str,
        period_days: int,
        model: str,
        features: dict[str, Any],
        status: str = "running",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO health_reviews(
                    review_id,
                    review_date,
                    period_days,
                    model,
                    status,
                    features_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    review_date,
                    period_days,
                    model,
                    status,
                    json.dumps(features, ensure_ascii=False),
                    now,
                ),
            )

    def finish_health_review(
        self,
        *,
        review_id: str,
        status: str,
        review_text: str | None = None,
        error: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                UPDATE health_reviews
                SET status = ?, review_text = ?, error = ?
                WHERE review_id = ?
                """,
                (status, review_text, error, review_id),
            )

    def get_health_review(self, review_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM health_reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()

        if row is None:
            return None

        item = dict(row)
        item["features"] = json.loads(item.pop("features_json"))
        return item

    def list_health_reviews(self, limit: int = 20) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT review_id, review_date, period_days, model, status, review_text, error, created_at
                FROM health_reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
