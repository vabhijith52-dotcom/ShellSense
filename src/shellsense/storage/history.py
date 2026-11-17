"""Execution history and undo records backed by SQLite.

Section 13: Stores past operations, results, and undo data for the History screen.
Invariant: A history failure must never suppress an audit write.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import platformdirs

from shellsense.safety.sanitize import sanitize_text


class HistoryStore:
    """Thread-safe SQLite storage for execution history and undo records."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is not None:
            self.db_path = db_path
        else:
            data_dir = Path(platformdirs.user_data_dir("shellsense", appauthor=False))
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "history.sqlite3"

        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        operation TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        risk_level TEXT NOT NULL,
                        plan_id TEXT NOT NULL,
                        plan_hash TEXT NOT NULL,
                        status TEXT NOT NULL,
                        original_text TEXT NOT NULL,
                        undo_data TEXT,
                        undo_status TEXT DEFAULT 'AVAILABLE'
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON history(timestamp DESC)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_operation ON history(operation)")
                conn.commit()
            if os.name == "posix":
                self.db_path.chmod(0o600)

    def record_execution(
        self,
        operation: str,
        summary: str,
        risk_level: str,
        plan_id: str,
        plan_hash: str,
        status: str,
        original_text: str,
        undo_data: dict[str, Any] | None = None,
    ) -> int:
        """Record an operation execution in history."""
        with self._lock:
            undo_json = json.dumps(undo_data) if undo_data else None
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO history (
                        timestamp, operation, summary, risk_level,
                        plan_id, plan_hash, status, original_text, undo_data, undo_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        sanitize_text(operation),
                        sanitize_text(summary),
                        risk_level,
                        plan_id,
                        plan_hash,
                        status,
                        sanitize_text(original_text),
                        undo_json,
                        "AVAILABLE" if undo_data else "NONE",
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid or 0)

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        op_type: str | None = None,
        range_days: int | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve paginated execution history with optional filtering."""
        with self._lock:
            query = "SELECT id, timestamp, operation, summary, risk_level, plan_id, plan_hash, status, original_text, undo_status FROM history WHERE 1=1"
            params: list[Any] = []

            if op_type:
                query += " AND operation = ?"
                params.append(op_type)

            if range_days:
                min_time = time.time() - (range_days * 86400)
                query += " AND timestamp >= ?"
                params.append(min_time)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

    def get_history_item(self, record_id: int) -> dict[str, Any] | None:
        """Fetch a single history record with its undo data."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM history WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            if data.get("undo_data"):
                with contextlib.suppress(Exception):
                    data["undo_data"] = json.loads(data["undo_data"])
            return data

    def mark_undone(self, record_id: int) -> bool:
        """Mark an undo record as consumed."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE history SET undo_status = 'UNDONE' WHERE id = ? AND undo_status = 'AVAILABLE'",
                (record_id,),
            )
            conn.commit()
            return cursor.rowcount > 0


DEFAULT_HISTORY_STORE = HistoryStore()
