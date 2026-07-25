"""Tool contract for the copilot.

A Tool wraps one deterministic capability (a statistical/traditional-AI engine)
behind a typed parameter and result schema. The orchestrator LLM chooses which
tools to call and fills their parameters; the tool does the actual computation.
The LLM never produces numbers itself — they always come from a tool result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    Params: ClassVar[type[BaseModel]]
    Result: ClassVar[type[BaseModel]]

    @abstractmethod
    def run(self, params: BaseModel) -> BaseModel:
        """Execute the tool on validated parameters and return a typed result."""

    def invoke(self, raw_params: dict | None = None) -> dict:
        """Validate raw params, run, and return a plain-dict result (LLM-facing)."""
        params = self.Params.model_validate(raw_params or {})
        return self.run(params).model_dump()

    @classmethod
    def openai_schema(cls) -> dict:
        """The OpenAI function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.Params.model_json_schema(),
            },
        }
