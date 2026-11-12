"""Crash-recoverable local F0 store; no external schema or credentials needed."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SQLiteRunStore:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS frontier_runs (
                run_id TEXT PRIMARY KEY,
                as_of TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS frontier_artifacts (
                run_id TEXT NOT NULL REFERENCES frontier_runs(run_id),
                stage TEXT NOT NULL,
                content TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (run_id, stage)
            );
        """)
        self.conn.commit()

    def __enter__(self) -> "SQLiteRunStore":
        return self

    def __exit__(self, *args: Any) -> None:
        self.conn.close()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def begin(self, run_id: str, as_of: str, input_hash: str) -> None:
        ts = self.now()
        with self.conn:
            row = self.conn.execute(
                "SELECT input_hash FROM frontier_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row and row[0] != input_hash:
                raise ValueError("run id collision with different input")
            self.conn.execute("""
                INSERT OR IGNORE INTO frontier_runs
                    (run_id, as_of, input_hash, status, created_at, updated_at)
                VALUES (?, ?, ?, 'running', ?, ?)
            """, (run_id, as_of, input_hash, ts, ts))

    def get_stage(self, run_id: str, stage: str) -> Any | None:
        row = self.conn.execute(
            "SELECT content FROM frontier_artifacts WHERE run_id=? AND stage=?", (run_id, stage)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_stage(self, run_id: str, stage: str, content: Any) -> None:
        ts = self.now()
        payload = json.dumps(content, ensure_ascii=False, sort_keys=True)
        with self.conn:
            self.conn.execute("""
                INSERT INTO frontier_artifacts (run_id, stage, content, recorded_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id, stage) DO UPDATE SET
                    content=excluded.content, recorded_at=excluded.recorded_at
            """, (run_id, stage, payload, ts))
            self.conn.execute(
                "UPDATE frontier_runs SET updated_at=? WHERE run_id=?", (ts, run_id)
            )

    def finish(self, run_id: str, status: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE frontier_runs SET status=?,updated_at=? WHERE run_id=?",
                (status, self.now(), run_id),
            )

    def status(self, run_id: str) -> str | None:
        row = self.conn.execute("SELECT status FROM frontier_runs WHERE run_id=?", (run_id,)).fetchone()
        return row[0] if row else None
