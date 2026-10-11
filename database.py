from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Literal


Role = Literal["system", "user", "assistant"]


class ConversationStore:
    """SQLite-backed storage for conversations and their ordered messages."""

    def __init__(self, database_path: str | Path = "data/contextos.db") -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    conversation_id TEXT NOT NULL
                        REFERENCES conversations(id) ON DELETE CASCADE,
                    turn_id TEXT NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    role TEXT NOT NULL
                        CHECK (role IN ('system', 'user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    UNIQUE (conversation_id, sequence_no)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation_sequence
                    ON messages(conversation_id, sequence_no);

                CREATE INDEX IF NOT EXISTS idx_messages_conversation_turn
                    ON messages(conversation_id, turn_id);
                """
            )

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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def new_turn_id() -> str:
    return str(uuid.uuid4())


def _now_ms() -> int:
    return time.time_ns() // 1_000_000
