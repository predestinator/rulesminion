from rulesminion.models import HackathonBrief
from rulesminion.agent import repair_brief


def test_coerces_string_prizes_and_india_yes():
    brief = HackathonBrief.model_validate(
        {
            "title": "Demo",
            "url": "https://example.com",
            "prizes": ["$500 first"],
            "deadlines": ["Dec 19 2026 07:59 UTC = 2026-12-19 13:29 IST"],
            "india_eligible": "Yes",
            "submission_checklist": "Public repo",
        }
    )
    assert brief.india_eligible == "yes"
    assert brief.prizes[0].amount == "$500 first"
    assert "13:29 IST" in brief.deadlines[0].as_stated
    assert brief.submission_checklist == ["Public repo"]


def test_repair_extracts_fenced_json():
    raw = """openminion: here you go\n```json\n{"title": "X", "url": "https://x.test", "india_eligible": "unclear"}\n```\n"""
    brief = repair_brief(raw, "https://fallback.test")
    assert brief.title == "X"
    assert brief.url == "https://x.test"
