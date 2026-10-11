from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Literal

from schemas.conversations import CONVERSATIONS_SCHEMA_SQL
from schemas.memories import MEMORIES_SCHEMA_SQL
from schemas.messages import (
    ADD_MESSAGE_ACTIVITY_COLUMN_SQL,
    MESSAGE_ACTIVITY_INDEX_SQL,
    MESSAGES_SCHEMA_SQL,
)


Role = Literal["system", "user", "assistant"]


class ConversationStore:
    """SQLite-backed storage for conversations and their ordered messages."""

    def __init__(self, database_path: str | Path = "data/contextos.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(CONVERSATIONS_SCHEMA_SQL)
            connection.executescript(MESSAGES_SCHEMA_SQL)
            self._add_message_activity_column_if_missing(connection)
            connection.executescript(MESSAGE_ACTIVITY_INDEX_SQL)
            connection.executescript(MEMORIES_SCHEMA_SQL)

    def create_conversation(self) -> str:
        conversation_id = str(uuid.uuid4())
        now_ms = _now_ms()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (id, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?)
                """,
                (conversation_id, now_ms, now_ms),
            )
        return conversation_id

    def add_message(
        self,
        conversation_id: str,
        turn_id: str,
        role: Role,
        content: str,
    ) -> int:
        if not content:
            raise ValueError("Message content cannot be empty.")

        now_ms = _now_ms()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence_no), 0) + 1 AS next_sequence_no
                FROM messages
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            next_sequence_no = row["next_sequence_no"]
            cursor = connection.execute(
                """
                INSERT INTO messages
                    (conversation_id, turn_id, sequence_no, role, content, created_at_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, turn_id, next_sequence_no, role, content, now_ms),
            )
            connection.execute(
                """
                UPDATE conversations
                SET updated_at_ms = ?
                WHERE id = ?
                """,
                (now_ms, conversation_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Could not persist message.")
            return int(cursor.lastrowid)

    def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        """Return one conversation in its authoritative insertion order."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY sequence_no ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def get_active_messages(self, conversation_id: str) -> list[dict[str, object]]:
        """Return active messages in order, including their persistent IDs."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, role, content
                FROM messages
                WHERE conversation_id = ? AND is_active = 1
                ORDER BY sequence_no ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [
            {"id": int(row["id"]), "role": row["role"], "content": row["content"]}
            for row in rows
        ]

    def mark_messages_inactive(
        self, conversation_id: str, message_ids: list[int]
    ) -> int:
        """Mark the specified active messages inactive within one conversation."""
        if not message_ids:
            return 0

        placeholders = ", ".join("?" for _ in message_ids)
        now_ms = _now_ms()
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE messages
                SET is_active = 0
                WHERE conversation_id = ?
                  AND is_active = 1
                  AND id IN ({placeholders})
                """,
                (conversation_id, *message_ids),
            )
            if cursor.rowcount:
                connection.execute(
                    """
                    UPDATE conversations
                    SET updated_at_ms = ?
                    WHERE id = ?
                    """,
                    (now_ms, conversation_id),
                )
            return cursor.rowcount

    @staticmethod
    def _add_message_activity_column_if_missing(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(messages)")
        }
        if "is_active" not in columns:
            connection.execute(ADD_MESSAGE_ACTIVITY_COLUMN_SQL)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def new_turn_id() -> str:
    return str(uuid.uuid4())


def _now_ms() -> int:
    return time.time_ns() // 1_000_000
