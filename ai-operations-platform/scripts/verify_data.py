"""Data smoke-test: confirm the frozen Zendesk store is present and complete.

Run from the project root: ``python scripts/verify_data.py``
"""

from __future__ import annotations

import json
from pathlib import Path

STORE = Path(__file__).resolve().parents[1] / "data" / "raw" / "zendesk"
FILES = [
    "tickets.jsonl", "comments.jsonl", "ticket_metrics.jsonl",
    "ticket_audits.jsonl", "ticket_metric_events.jsonl",
]


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def main() -> None:
    print(f"Zendesk store: {STORE}")
    for name in FILES:
        print(f"  {name:28} {count_lines(STORE / name):>9,} lines")
    manifest = json.loads((STORE / "manifest.json").read_text(encoding="utf-8"))
    keys = ("ticket_count", "comment_count", "metric_events", "resolution_hours_by_type", "sla_breach")
    print("manifest:", json.dumps({k: manifest.get(k) for k in keys}, indent=2))


if __name__ == "__main__":
    main()
