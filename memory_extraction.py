from __future__ import annotations

from pathlib import Path

from ollama import chat
from pydantic import BaseModel

from llm_inference import Message


class MemoryExtraction(BaseModel):
    facts: list[str]
    decisions: list[str]
    preferences: list[str]
    constraints: list[str]


PROMPT_PATH = Path(__file__).with_name("prompt.md")


def extract_memories(
    conversation_history: list[Message],
    model: str = "llama3.2:3b",
) -> MemoryExtraction:
    """Extract structured memories from a conversation using Ollama."""
    prompt = PROMPT_PATH.read_text(encoding="utf-8").replace(
        "{conversation_history}", str(conversation_history)
    )
    response = chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        format=MemoryExtraction.model_json_schema(),
        options={"temperature": 0},
    )
    return MemoryExtraction.model_validate_json(response.message.content)
