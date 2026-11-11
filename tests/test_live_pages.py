"""Live checks against real hackathon pages. Requires GEMINI_API_KEY."""

from __future__ import annotations

import json

import pytest

from rulesminion.agent import check_url
from rulesminion.config import gemini_key_loaded, load_env
from rulesminion.snapshots import SnapshotStore

pytestmark = pytest.mark.live

PAGES = [
    {
        "url": "https://dorahacks.io/hackathon/2418/detail",
        "title_bit": "Cortensor",
        "prize_bits": ("1,150", "1150", "1.150"),
        "month_bits": ("2026-12", "December", "Dec"),
    },
    {
        "url": "https://learn-specs.devpost.com/",
        "title_bit": "SPECS",
        "prize_bits": ("2,500", "2500", "$2,500"),
        "month_bits": ("2026-12", "December", "Dec"),
    },
    {
        "url": "https://docs.cortensor.network/community-and-ecosystem/hackathon/hackathon-5",
        "title_bit": "Hackathon",
        "prize_bits": ("1,150", "1150", "$500"),
        "month_bits": ("December", "2026-12", "Dec"),
    },
]


@pytest.fixture(scope="module")
def ready():
    load_env()
    if not gemini_key_loaded():
        pytest.skip("GEMINI_API_KEY is not loaded")


def _blob(result) -> str:
    return json.dumps(json.loads(result.model_dump_json())).lower()


@pytest.mark.parametrize("spec", PAGES, ids=[item["url"] for item in PAGES])
def test_live_page_extracts_core_fields(ready, tmp_path, spec):
    store = SnapshotStore(tmp_path)
    result = check_url(spec["url"], store=store)
    assert result.brief.title
    assert spec["title_bit"].lower() in result.brief.title.lower() or spec["title_bit"].lower() in result.brief.url.lower()
    blob = _blob(result)
    assert any(bit.lower() in blob for bit in spec["prize_bits"]), blob[:1500]
    assert any(bit.lower() in blob for bit in spec["month_bits"]), blob[:1500]
    assert result.brief.india_eligible in {"yes", "no", "unclear"}
    assert result.changes.status == "first_seen"
    again = check_url(spec["url"], store=store)
    assert again.changes.status in {"unchanged", "changed"}
    if spec["url"].endswith("/2418/detail"):
        assert result.brief.submission_checklist
