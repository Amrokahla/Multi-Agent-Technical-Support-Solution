"""Copilot endpoint — natural-language questions to the orchestrator agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agent import orchestrator, sse
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


@router.post("/ask/stream")
def ask_stream(request: AskRequest) -> StreamingResponse:
    """Same turn as /ask, streamed as SSE: plan/tool/token events, then a final `done`.

    Streaming keeps the connection active, so long multi-round turns never hit the
    platform's idle request timeout. Once the stream is open the HTTP status can't
    change, so failures surface as an `error` event rather than a 5xx. The sync
    generator is iterated in Starlette's threadpool, so blocking OpenAI reads don't
    stall the event loop.
    """
    history = [m.model_dump() for m in request.history[-20:]]

    def gen():
        try:
            for event, payload in orchestrator.answer_stream(request.question, history=history):
                yield sse.frame(event, payload)
                if event == "plan":  # keep the connection warm during silent planning
                    yield sse.PING
        except RuntimeError as exc:  # e.g. missing OPENAI_API_KEY
            yield sse.frame("error", {"status": 503, "message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            yield sse.frame("error", {"status": 502, "message": f"Copilot error: {exc}"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
