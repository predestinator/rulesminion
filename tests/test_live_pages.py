"""Live checks against real hackathon pages. Needs GEMINI_API_KEY and network."""

from __future__ import annotations

import json
import os

import pytest

from rulesminion.agent import check_url
from rulesminion.config import load_env
from rulesminion.pages import fetch_page
from rulesminion.snapshots import SnapshotStore

pytestmark = pytest.mark.live


def _ready() -> None:
    load_env()
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")


def test_live_fetch_cortensor_dora_page():
    page = fetch_page("https://dorahacks.io/hackathon/2418/detail")
    assert page.status_code == 200
    assert "1,150" in page.visible_text or "1150" in page.visible_text
    assert "2026-12-19 13:29 IST" in page.digest


def test_live_fetch_learn_specs_devpost():
    page = fetch_page("https://learn-specs.devpost.com/")
    assert page.status_code == 200
    assert "2,500" in page.visible_text or "2500" in page.visible_text
    assert "EST" in page.visible_text


def test_live_agent_cortensor(tmp_path):
    _ready()
    store = SnapshotStore(tmp_path)
    result = check_url("https://dorahacks.io/hackathon/2418/detail", store=store)
    blob = result.brief.model_dump_json().lower()
    assert result.brief.title
    assert "1150" in blob.replace(",", "") or "1,150" in result.brief.prize_pool
    assert result.brief.india_eligible in {"yes", "no", "unclear"}
    assert any("12-19" in item.ist or "december 19" in item.ist.lower() or "13:29" in item.ist for item in result.brief.deadlines) or any(
        "13:29" in item.as_stated or "12/19" in item.as_stated or "dec" in item.as_stated.lower()
        for item in result.brief.deadlines
    )
    assert result.brief.submission_checklist
    second = check_url("https://dorahacks.io/hackathon/2418/detail", store=store)
    assert second.changes.status in {"unchanged", "changed"}
    assert second.changes.previous_checked_at_ist


def test_live_agent_learn_specs(tmp_path):
    _ready()
    store = SnapshotStore(tmp_path)
    result = check_url("https://learn-specs.devpost.com/", store=store)
    blob = json.dumps(result.brief.model_dump()).lower()
    assert "spec" in result.brief.title.lower() or "learn" in result.brief.title.lower()
    assert "2500" in blob.replace(",", "") or "2,500" in result.brief.prize_pool
    assert result.brief.india_eligible in {"yes", "no", "unclear"}
