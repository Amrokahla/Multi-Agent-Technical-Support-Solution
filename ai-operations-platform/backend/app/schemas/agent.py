"""Response schema for the copilot orchestrator."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The manager's question.")
    history: list[Message] = Field(default_factory=list, description="Prior turns for session memory.")


class ToolTraceEntry(BaseModel):
    tool: str
    arguments: dict
    ok: bool
    result: dict | None = None
    error: str | None = None


class AnalyticsLink(BaseModel):
    label: str
    href: str


class AgentResponse(BaseModel):
    question: str
    answer: str
    tool_trace: list[ToolTraceEntry]
    analytics_links: list[AnalyticsLink]
    caveats: list[str]
    models_used: dict
    grounding_ok: bool
