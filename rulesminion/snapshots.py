"""Persist briefs and compute what changed since the last check."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from rulesminion.config import SNAPSHOT_DIR
from rulesminion.models import ChangeItem, ChangeReport, HackathonBrief
from rulesminion.pages import canonical_url
from rulesminion.timeutil import now_ist_label

COMPARE_SCALARS = (
    "title",
    "organizer",
    "format",
    "prize_pool",
    "india_eligible",
    "eligibility_summary",
)
COMPARE_LISTS = (
    "prizes",
    "deadlines",
    "submission_checklist",
)


def url_key(url: str) -> str:
    return sha256(canonical_url(url).encode("utf-8")).hexdigest()[:16]


class SnapshotRecord:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.snapshot_id: str = payload["snapshot_id"]
        self.url: str = payload["url"]
        self.checked_at_ist: str = payload["checked_at_ist"]
        self.brief = HackathonBrief.model_validate(payload["brief"])
        self.path: str = payload.get("path", "")


class SnapshotStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else SNAPSHOT_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir_for(self, url: str) -> Path:
        path = self.root / url_key(url)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _index_path(self, url: str) -> Path:
        return self._dir_for(url) / "index.json"

    def _read_index(self, url: str) -> list[dict[str, Any]]:
        path = self._index_path(url)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_index(self, url: str, rows: list[dict[str, Any]]) -> None:
        self._index_path(url).write_text(
            json.dumps(rows, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )

    def history(self, url: str) -> list[SnapshotRecord]:
        records: list[SnapshotRecord] = []
        for row in self._read_index(url):
            file_path = self._dir_for(url) / row["file"]
            if not file_path.exists():
                continue
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            payload["path"] = str(file_path)
            records.append(SnapshotRecord(payload))
        return records

    def latest(self, url: str) -> SnapshotRecord | None:
        rows = self.history(url)
        return rows[-1] if rows else None

    def save(self, url: str, brief: HackathonBrief) -> SnapshotRecord:
        folder = self._dir_for(url)
        checked = now_ist_label()
        stamp = checked.replace(" ", "_").replace(":", "")
        existing = len(self._read_index(url)) + 1
        snapshot_id = f"{url_key(url)}-{existing:03d}-{stamp}"
        filename = f"{existing:03d}-{stamp}.json"
        payload = {
            "snapshot_id": snapshot_id,
            "url": canonical_url(url),
            "checked_at_ist": checked,
            "brief": json.loads(brief.model_dump_json()),
        }
        file_path = folder / filename
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        rows = self._read_index(url)
        rows.append({"file": filename, "snapshot_id": snapshot_id, "checked_at_ist": checked})
        self._write_index(url, rows)
        payload["path"] = str(file_path)
        return SnapshotRecord(payload)


def first_seen_report() -> ChangeReport:
    return ChangeReport(status="first_seen", summary="First snapshot stored for this URL.")


def diff_briefs(
    previous: HackathonBrief,
    current: HackathonBrief,
    *,
    previous_checked_at_ist: str | None = None,
) -> ChangeReport:
    added: list[str] = []
    removed: list[str] = []
    changed: list[ChangeItem] = []

    prev_dump = json.loads(previous.model_dump_json())
    curr_dump = json.loads(current.model_dump_json())

    for field in COMPARE_SCALARS:
        before = _norm(prev_dump.get(field))
        after = _norm(curr_dump.get(field))
        if before != after:
            changed.append(ChangeItem(path=field, before=before or None, after=after or None))

    for field in COMPARE_LISTS:
        before_items = [_norm(item) for item in prev_dump.get(field) or [] if _norm(item)]
        after_items = [_norm(item) for item in curr_dump.get(field) or [] if _norm(item)]
        for item in after_items:
            if item not in before_items:
                added.append(f"{field}: {item}")
        for item in before_items:
            if item not in after_items:
                removed.append(f"{field}: {item}")

    if not added and not removed and not changed:
        return ChangeReport(
            status="unchanged",
            previous_checked_at_ist=previous_checked_at_ist,
            summary="No material change since the last snapshot.",
        )

    parts = []
    if changed:
        parts.append(f"{len(changed)} field(s) changed")
    if added:
        parts.append(f"{len(added)} item(s) added")
    if removed:
        parts.append(f"{len(removed)} item(s) removed")
    return ChangeReport(
        status="changed",
        previous_checked_at_ist=previous_checked_at_ist,
        added=added,
        removed=removed,
        changed=changed,
        summary="; ".join(parts) + ".",
    )


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return " | ".join(_norm(item) for item in value if _norm(item))
    if isinstance(value, dict):
        return " | ".join(
            f"{key}={_norm(val)}" for key, val in value.items() if _norm(val) and key != "confidence"
        )
    return str(value)
