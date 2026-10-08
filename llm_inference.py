from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Callable, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from count_tokens import count
from rich import print as rprint
from rich.panel import Panel


class Message(TypedDict):
    role: str
    content: str


@dataclass(frozen=True)
class InferenceConfig:
    model: str = "llama3.2:3b"
    ollama_url: str = "http://127.0.0.1:11434/api/chat"
    tokenize_url: str = "http://127.0.0.1:11434/api/tokenize"
    system_prompt: str = "Answer concisely and accurately. If unsure, say so."
    max_context_tokens: int = 300
    max_response_tokens: int = 150
    temperature: float = 0.7
    keep_alive: str = "30m"
    request_timeout: int = 60

    @property
    def max_input_tokens(self) -> int:
        return self.max_context_tokens - self.max_response_tokens


class LLMInference:
    """Prepare context and generate responses through Ollama."""

    def __init__(
        self,
        config: InferenceConfig | None = None,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        self.config = config or InferenceConfig()
        self._opener = opener
        self.memory_extractions: list[object] = []

    def get_response(self, history: list[Message]) -> str:
        memory = "\n".join(
            extraction.model_dump_json() for extraction in self.memory_extractions
        )
        messages, evicted_messages = self._prepare_messages(history, memory)
        if evicted_messages:
            threading.Thread(
                target=self._extract_memories,
                args=(evicted_messages,),
                daemon=True,
            ).start()
        result = self._post_json(
            self.config.ollama_url,
            {
                "model": self.config.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_response_tokens,
                    "num_ctx": self.config.max_context_tokens,
                },
                "keep_alive": self.config.keep_alive,
            },
        )
        return result["message"]["content"]

    def _prepare_messages(
        self, history: list[Message], memory: str = ""
    ) -> tuple[list[Message], list[Message]]:
        remaining_history = list(history)
        evicted_messages: list[Message] = []

        while True:
            messages = [
                {"role": "system", "content": self.config.system_prompt},
                *([{"role": "system", "content": f"Known memories:\n{memory}"}] if memory else []),
                *remaining_history,
            ]
            prompt = self._render_chat_prompt(messages)

            try:
                result = self._post_json(
                    self.config.tokenize_url,
                    {"model": self.config.model, "prompt": prompt},
                )
                token_count = len(result["tokens"])
            except HTTPError as error:
                if error.code != 404:
                    raise
                token_count = count(text=prompt)
            print(f"Context token count: {token_count}")

            if token_count <= self.config.max_input_tokens:
                return messages, evicted_messages
            if len(remaining_history) < 2:
                raise ValueError(
                    "The latest user message exceeds the available context window."
                )

            evicted_messages.extend(remaining_history[:2])
            del remaining_history[:2]
            print("Context limit exceeded. Evicted the oldest user-assistant interaction.")

    def _extract_memories(self, messages: list[Message]) -> None:
        from memory_extraction import extract_memories

        try:
            extraction = extract_memories(messages, self.config.model)
            self.memory_extractions.append(extraction)
            rprint(
                Panel(
                    extraction.model_dump_json(indent=2),
                    title="Memory Extraction Completed",
                    border_style="green",
                )
            )
        except Exception as error:
            rprint(f"[red]Memory extraction failed:[/red] {error}")

    @staticmethod
    def _render_chat_prompt(messages: list[Message]) -> str:
        prompt = ""
        for index, message in enumerate(messages):
            is_last = index == len(messages) - 1
            prompt += f"<|im_start|>{message['role']}\n{message['content']}"
            if message["role"] != "assistant" or not is_last:
                prompt += "<|im_end|>\n"

        if messages[-1]["role"] != "assistant":
            prompt += "<|im_start|>assistant\n"
        return prompt

    def _post_json(self, url: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.config.request_timeout) as response:
                result = json.load(response)
        except HTTPError:
            # Preserve HTTP errors so callers can handle status-specific fallbacks.
            raise
        except URLError as error:
            raise RuntimeError(f"Could not connect to Ollama at {url}: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Ollama returned invalid JSON from {url}") from error

        if not isinstance(result, dict):
            raise RuntimeError(f"Ollama returned an unexpected response from {url}")
        return result
