"""Schema definition for durable, extracted conversation memories.

This module deliberately contains schema only. Extraction, retrieval, and
database-store methods will be added separately.
"""

MEMORIES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL
        REFERENCES conversations(id) ON DELETE CASCADE,

    -- Inclusive message sequence range that produced this extracted memory.
    source_start_sequence_no INTEGER NOT NULL CHECK (source_start_sequence_no >= 1),
    source_end_sequence_no INTEGER NOT NULL CHECK (
        source_end_sequence_no >= source_start_sequence_no
    ),

    category TEXT NOT NULL
        CHECK (category IN ('fact', 'decision', 'preference', 'constraint')),
    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
    created_at_ms INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_memories_conversation_active
    ON memories(conversation_id, is_active, created_at_ms DESC);

CREATE INDEX IF NOT EXISTS idx_memories_conversation_source_range
    ON memories(conversation_id, source_start_sequence_no, source_end_sequence_no);
"""
