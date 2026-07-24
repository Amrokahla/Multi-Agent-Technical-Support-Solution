"""Access to the frozen Zendesk store.

The store is read-only and file-backed. ``get_connector`` returns a cached
``ZendeskConnector`` (loaded lazily on first use) that feature services use to
read tickets, comments, metrics, audits and metric events exactly like the live
Zendesk API. ``read_manifest`` is a cheap summary used by the health endpoint.
"""

from __future__ import annotations

import json
from functools import lru_cache

from app.config import get_settings
from app.repositories.zendesk_connector import ZendeskConnector


@lru_cache
def get_connector() -> ZendeskConnector:
    return ZendeskConnector(str(get_settings().data_dir))


def read_manifest() -> dict:
    path = get_settings().data_dir / "manifest.json"
    if not path.exists():
        return {"error": "dataset not found", "expected_at": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))
