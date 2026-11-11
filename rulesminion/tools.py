"""OpenMinion tools used by the RulesMinion agent."""

from __future__ import annotations

import json

from openminion import tool

from rulesminion.pages import fetch_page
from rulesminion.snapshots import SnapshotStore


@tool(name="fetch_hackathon_page", min_scope="READ_ONLY", idempotent=True)
def fetch_hackathon_page(url: str) -> str:
    """Fetch a public hackathon page and return a cleaned digest.

    The digest includes visible text plus any JSON-LD or DoraHacks timestamps,
    already converted to IST (Asia/Kolkata) when the page exposes structured dates.
    """
    page = fetch_page(url)
    prefix = []
    if page.title:
        prefix.append(f"Fetched title: {page.title}")
    prefix.append(f"HTTP status: {page.status_code}")
    if page.warnings:
        prefix.append("Warnings: " + "; ".join(page.warnings))
    return "\n".join(prefix) + "\n\n" + page.digest


@tool(name="recall_previous_snapshot", min_scope="READ_ONLY", idempotent=True)
def recall_previous_snapshot(url: str) -> str:
    """Return the most recent saved RulesMinion snapshot for this URL, if any."""
    record = SnapshotStore().latest(url)
    if record is None:
        return "No previous snapshot is stored for this URL."
    payload = {
        "snapshot_id": record.snapshot_id,
        "checked_at_ist": record.checked_at_ist,
        "brief": json.loads(record.brief.model_dump_json()),
    }
    return json.dumps(payload, indent=2)
