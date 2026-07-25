"""Tool — analyze_tickets: the LLM 'why' engine over real ticket content."""

from __future__ import annotations

from app.ai import analyzer
from app.schemas.tools import AnalyzeTicketsParams, FlexResult
from app.tools.base import Tool


class AnalyzeTicketsTool(Tool):
    name = "analyze_tickets"
    description = (
        "Read a sample of the ACTUAL tickets behind a segment (filter by window, queue, client, "
        "priority, or tag) and explain WHY it's happening: themes, likely cause, temporary vs "
        "structural, priority mismatches, and complexity. Use after detecting a spike, to diagnose a "
        "queue or client, or to check whether priorities are set correctly."
    )
    Params = AnalyzeTicketsParams
    Result = FlexResult

    def run(self, params: AnalyzeTicketsParams) -> FlexResult:
        return FlexResult(**analyzer.analyze_tickets(
            window_days=params.window_days,
            queue=params.queue,
            client=params.client,
            priority=params.priority,
            tag=params.tag,
            focus=params.focus,
            sample_size=params.sample_size,
        ))
