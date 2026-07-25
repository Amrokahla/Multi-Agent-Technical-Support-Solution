"""Tool registry — the LLM's view of the tools, plus safe dispatch.

`schemas()` produces the OpenAI function-calling tool list. `dispatch()` validates
and runs a single tool call, returning either the tool result or a structured
``{"error": ...}`` — never raising — so a bad LLM call becomes feedback the model
can recover from rather than a crashed request.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import ValidationError

from app.tools import ALL_TOOLS
from app.tools.base import Tool


def _format_validation(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "(arguments)"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        """OpenAI function-calling tool schemas for every registered tool."""
        return [t.openai_schema() for t in self._tools.values()]

    def dispatch(self, name: str, arguments: dict | None = None) -> dict:
        """Run one tool call. Returns the result dict or ``{"error": ...}``."""
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"Unknown tool '{name}'. Available tools: {', '.join(self._tools)}."}
        try:
            return tool.invoke(arguments)
        except ValidationError as exc:
            return {"error": f"Invalid arguments for '{name}': {_format_validation(exc)}"}
        except Exception as exc:  # noqa: BLE001 - engine failure must not crash the loop
            return {"error": f"Tool '{name}' failed: {exc}"}


@lru_cache(maxsize=1)
def get_registry() -> ToolRegistry:
    return ToolRegistry(ALL_TOOLS)
