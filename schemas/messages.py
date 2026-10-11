"""Schema definition for ordered conversational messages."""

MESSAGES_SCHEMA_SQL = """
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
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    UNIQUE (conversation_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_sequence
    ON messages(conversation_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_turn
    ON messages(conversation_id, turn_id);

"""


MESSAGE_ACTIVITY_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_messages_active_sequence
    ON messages(conversation_id, is_active, sequence_no);
"""


ADD_MESSAGE_ACTIVITY_COLUMN_SQL = """
ALTER TABLE messages
ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1
    CHECK (is_active IN (0, 1))
"""
