"""Server-Sent-Events wire framing for the streaming copilot endpoint."""

from __future__ import annotations

import json

# A comment frame — keeps the connection warm through proxies/idle timeouts during
# silent stretches (e.g. GPT-5 planning) without emitting a real event.
PING = ": keep-alive\n\n"


def frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
