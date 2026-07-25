"""LLM provider for the orchestrator — two OpenAI roles behind one interface.

GPT-5 plans (emits tool calls); GPT-5-mini synthesizes the answer. Kept behind a
small interface so tests inject a mock and the backend never needs a key offline.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache

from app.config import Settings, get_settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


class OpenAIProvider:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set — the copilot needs it (tools work without it).")
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._planner = settings.planner_model
        self._synth = settings.synth_model

    def plan(self, messages: list[dict], tools: list[dict]) -> tuple[list[ToolCall], str | None]:
        resp = self._client.chat.completions.create(
            model=self._planner, messages=messages, tools=tools, tool_choice="auto",
            max_completion_tokens=4000,
        )
        msg = resp.choices[0].message
        calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=_parse_args(tc.function.arguments))
            for tc in (msg.tool_calls or [])
        ]
        return calls, msg.content

    def synthesize(self, messages: list[dict]) -> str:
        # Generous budget: GPT-5-mini spends reasoning tokens first, so a low cap
        # can leave no room for the actual answer text.
        resp = self._client.chat.completions.create(
            model=self._synth, messages=messages, max_completion_tokens=6000,
        )
        return resp.choices[0].message.content or ""

    def synthesize_stream(self, messages: list[dict]) -> Iterator[str]:
        # Same call as synthesize, streamed: yields the answer text deltas as they
        # arrive. Reasoning tokens are consumed internally; only delta.content is text.
        stream = self._client.chat.completions.create(
            model=self._synth, messages=messages, max_completion_tokens=6000, stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def _parse_args(raw: str | None) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


@lru_cache(maxsize=1)
def get_provider() -> OpenAIProvider:
    return OpenAIProvider(get_settings())
