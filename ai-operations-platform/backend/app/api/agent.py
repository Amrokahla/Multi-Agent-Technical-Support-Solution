"""Copilot endpoint — natural-language questions to the orchestrator agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agent import orchestrator
from app.schemas.agent import AgentResponse, AskRequest

router = APIRouter()


@router.post("/ask", response_model=AgentResponse)
def ask(request: AskRequest) -> AgentResponse:
    """Plan tools, run them, and synthesize a grounded answer for the question."""
    history = [m.model_dump() for m in request.history[-20:]]  # session memory, capped
    try:
        return orchestrator.answer(request.question, history=history)
    except RuntimeError as exc:  # e.g. missing OPENAI_API_KEY
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001 - surface LLM/tool failures as a clean 502
        raise HTTPException(status_code=502, detail=f"Copilot error: {exc}") from None
