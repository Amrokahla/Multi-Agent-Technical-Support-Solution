"""Copilot tools — deterministic capabilities the orchestrator agent can call.

Each tool wraps a statistical/traditional-AI engine behind a typed schema. The
formal registry (LLM-facing schemas + dispatch) lives in app/agent/registry.py;
ALL_TOOLS lists the wrapped capabilities.
"""

from app.tools.allocation import AllocateResourcesTool
from app.tools.analyze_tickets import AnalyzeTicketsTool
from app.tools.forecasting import ForecastDemandTool
from app.tools.insights import OperationalInsightsTool
from app.tools.scenarios import (
    CapacityImpactTool,
    ClientLoadTool,
    DetectSpikeTool,
    TeamCompareTool,
    WhatifSimulateTool,
)
from app.tools.sla_risk import PredictSlaRiskTool

ALL_TOOLS = [
    ForecastDemandTool(),
    PredictSlaRiskTool(),
    AllocateResourcesTool(),
    OperationalInsightsTool(),
    ClientLoadTool(),
    DetectSpikeTool(),
    CapacityImpactTool(),
    WhatifSimulateTool(),
    TeamCompareTool(),
    AnalyzeTicketsTool(),
]

__all__ = [
    "ForecastDemandTool",
    "PredictSlaRiskTool",
    "AllocateResourcesTool",
    "OperationalInsightsTool",
    "ClientLoadTool",
    "DetectSpikeTool",
    "CapacityImpactTool",
    "WhatifSimulateTool",
    "TeamCompareTool",
    "AnalyzeTicketsTool",
    "ALL_TOOLS",
]
