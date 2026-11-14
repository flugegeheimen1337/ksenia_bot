"""Прогресс туриста и кэш file_id Telegram. Хватает одного sqlite-файла."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Progress:
    user_id: int
    status: str
    step: int


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    status TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL
                )
                """
            )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure(self, user_id: int) -> Progress:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id, status, step, updated_at) VALUES (?, 'new', 0, ?)",
                (user_id, _now()),
            )
        return self.get(user_id)

    def get(self, user_id: int) -> Progress:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id, status, step FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return self.ensure(user_id)
        return Progress(int(row["user_id"]), str(row["status"]), int(row["step"]))

    def try_begin(self, user_id: int) -> str:
        """new -> active. Возвращает begin, resume или done."""
        self.ensure(user_id)
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT status FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            status = str(row["status"])
            if status == "done":
                return "done"
            if status == "active":
                return "resume"
            conn.execute(
                "UPDATE users SET status = 'active', step = 0, updated_at = ? WHERE user_id = ? AND status = 'new'",
                (_now(), user_id),
            )
            return "begin"

    def advance(self, user_id: int, expected_step: int) -> bool:
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                """
                UPDATE users
                SET step = ?, updated_at = ?
                WHERE user_id = ? AND step = ? AND status = 'active'
                """,
                (expected_step + 1, _now(), user_id, expected_step),
            )
            return cursor.rowcount == 1

    def mark_done(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET status = 'done', updated_at = ? WHERE user_id = ? AND status = 'active'",
                (_now(), user_id),
            )

    def reset(self, user_id: int) -> None:
        self.ensure(user_id)
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET status = 'new', step = 0, updated_at = ? WHERE user_id = ?",
                (_now(), user_id),
            )

    def restart(self, user_id: int) -> None:
        self.ensure(user_id)
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET status = 'active', step = 0, updated_at = ? WHERE user_id = ?",
                (_now(), user_id),
            )

    def get_file_id(self, path: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT file_id FROM files WHERE path = ?", (path,)).fetchone()
        return None if row is None else str(row["file_id"])

    def set_file_id(self, path: str, file_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO files (path, file_id) VALUES (?, ?) ON CONFLICT(path) DO UPDATE SET file_id = excluded.file_id",
                (path, file_id),
            )

    def delete_file_id(self, path: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM files WHERE path = ?", (path,))
