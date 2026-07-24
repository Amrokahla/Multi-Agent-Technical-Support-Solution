"""A Zendesk connector that mimics the real Incremental Exports API.

In production this class would call
``GET /api/v2/incremental/tickets/cursor.json``. Here it is backed by the
generated local store, but the retrieval semantics are identical: cursor-based
pagination, up to 1000 tickets per page, an ``end_of_stream`` flag, incremental
filtering by ``start_time``, and sideloading of referenced users, organizations
and groups. Downstream code can therefore treat it exactly like the live API.

Reference: developer.zendesk.com/documentation/ticketing/managing-tickets/
using-the-incremental-export-api
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Iterator

PAGE_SIZE = 1000
CURSOR_PREFIX = "offset:"


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(f"{CURSOR_PREFIX}{offset}".encode()).decode()


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
    return int(decoded.removeprefix(CURSOR_PREFIX))


def _to_epoch(iso_timestamp: str) -> int:
    return int(datetime.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%SZ").timestamp())


class ZendeskConnector:
    """Reads the generated store and serves it like Zendesk's export endpoint."""

    def __init__(self, store_dir: str | Path, subdomain: str = "acmecloud"):
        self.store_dir = Path(store_dir)
        self.subdomain = subdomain
        self._tickets = self._load_tickets()
        self._users = {record["id"]: record for record in self._load_json("users.json")}
        self._orgs = {record["id"]: record for record in self._load_json("organizations.json")}
        self._groups = {record["id"]: record for record in self._load_json("groups.json")}
        self._comments = self._load_comments()
        self._metrics = {record["ticket_id"]: record for record in self._load_jsonl("ticket_metrics.jsonl")}
        self._audits = {record["ticket_id"]: record["audits"]
                        for record in self._load_jsonl("ticket_audits.jsonl")}
        self._metric_events = sorted(self._load_jsonl("ticket_metric_events.jsonl"),
                                     key=lambda event: event["time"])

    def _load_json(self, name: str) -> list[dict]:
        with open(self.store_dir / name, encoding="utf-8") as handle:
            return json.load(handle)

    def _load_jsonl(self, name: str) -> list[dict]:
        path = self.store_dir / name
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def _load_tickets(self) -> list[dict]:
        # Sorted by updated_at so incremental start_time filtering is monotonic.
        tickets = []
        with open(self.store_dir / "tickets.jsonl", encoding="utf-8") as handle:
            for line in handle:
                tickets.append(json.loads(line))
        tickets.sort(key=lambda ticket: ticket["updated_at"])
        return tickets

    def _load_comments(self) -> dict[int, list[dict]]:
        index: dict[int, list[dict]] = {}
        path = self.store_dir / "comments.jsonl"
        if not path.exists():
            return index
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                index[record["ticket_id"]] = record["comments"]
        return index

    def incremental_tickets(
        self,
        start_time: int = 0,
        include: list[str] | None = None,
        cursor: str | None = None,
    ) -> Iterator[dict]:
        """Yield export pages exactly like the cursor-based incremental endpoint."""
        include = include or []
        window = [ticket for ticket in self._tickets if _to_epoch(ticket["updated_at"]) >= start_time]
        offset = _decode_cursor(cursor)

        while True:
            page = window[offset:offset + PAGE_SIZE]
            offset += len(page)
            end_of_stream = offset >= len(window)
            payload = {
                "tickets": page,
                "count": len(window),
                "end_of_stream": end_of_stream,
                "after_cursor": None if end_of_stream else _encode_cursor(offset),
                "after_url": None if end_of_stream else self._after_url(offset),
            }
            payload.update(self._sideloads(page, include))
            yield payload
            if end_of_stream:
                return

    def _after_url(self, offset: int) -> str:
        cursor = _encode_cursor(offset)
        return (
            f"https://{self.subdomain}.zendesk.com/api/v2/incremental/"
            f"tickets/cursor.json?cursor={cursor}"
        )

    def _sideloads(self, page: list[dict], include: list[str]) -> dict:
        """Attach only the referenced records for this page, as Zendesk does."""
        sideloads: dict[str, list[dict]] = {}
        if "users" in include:
            user_ids = set()
            for ticket in page:
                user_ids.update(
                    identifier for identifier in
                    (ticket["requester_id"], ticket["submitter_id"], ticket["assignee_id"])
                    if identifier is not None
                )
            sideloads["users"] = [self._users[uid] for uid in sorted(user_ids) if uid in self._users]
        if "organizations" in include:
            org_ids = {ticket["organization_id"] for ticket in page if ticket["organization_id"]}
            sideloads["organizations"] = [self._orgs[oid] for oid in sorted(org_ids) if oid in self._orgs]
        if "groups" in include:
            group_ids = {ticket["group_id"] for ticket in page if ticket["group_id"]}
            sideloads["groups"] = [self._groups[gid] for gid in sorted(group_ids) if gid in self._groups]
        return sideloads

    def iter_all_tickets(self, start_time: int = 0) -> Iterator[dict]:
        """Convenience walker: page through the export and yield every ticket."""
        for page in self.incremental_tickets(start_time=start_time):
            yield from page["tickets"]

    def ticket_comments(self, ticket_id: int) -> dict:
        """Mimic GET /api/v2/tickets/{id}/comments.json."""
        return {"comments": self._comments.get(ticket_id, [])}

    def ticket_metrics(self, ticket_id: int) -> dict:
        """Mimic GET /api/v2/tickets/{id}/metrics.json (solved_at + SLA actuals)."""
        return {"ticket_metric": self._metrics.get(ticket_id)}

    def ticket_audits(self, ticket_id: int) -> dict:
        """Mimic GET /api/v2/tickets/{id}/audits.json (status/assignee history)."""
        audits = self._audits.get(ticket_id, [])
        return {"audits": audits, "count": len(audits)}

    def sla_policies(self) -> dict:
        """Mimic GET /api/v2/slas/policies.json."""
        return {"sla_policies": self._load_json("sla_policies.json")}

    def incremental_ticket_metric_events(self, start_time: int = 0) -> Iterator[dict]:
        """Mimic the cursor-paged GET /api/v2/incremental/ticket_metric_events.json."""
        window = [event for event in self._metric_events if _to_epoch(event["time"]) >= start_time]
        for offset in range(0, len(window), PAGE_SIZE):
            page = window[offset:offset + PAGE_SIZE]
            end_of_stream = offset + PAGE_SIZE >= len(window)
            yield {
                "ticket_metric_events": page,
                "count": len(window),
                "end_of_stream": end_of_stream,
                "after_cursor": None if end_of_stream else _encode_cursor(offset + PAGE_SIZE),
            }
