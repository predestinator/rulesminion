from pathlib import Path

import pytest

from rulesminion.pages import assert_public_http_url, parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_dora_fixture_digest_includes_prize_and_ist():
    html = (FIXTURES / "sample_dora.html").read_text(encoding="utf-8")
    page = parse_page("https://dorahacks.io/hackathon/2418/detail", html)
    assert page.title.startswith("Cortensor Hackathon #5")
    assert "1,150 USD" in page.visible_text
    assert "2026-12-19 13:29 IST" in page.digest
    assert "2026-10-16 12:30 IST" in page.digest
    assert "ONLINE" in page.digest or "OnlineEventAttendanceMode" in page.digest
    assert "password" not in page.digest.lower() or "password" not in page.digest.split("DoraHacks")[-1].lower()


def test_devpost_fixture_keeps_deadline_and_prize():
    html = (FIXTURES / "sample_devpost.html").read_text(encoding="utf-8")
    page = parse_page("https://learn-specs.devpost.com/", html)
    assert "2,500" in page.digest
    assert "5:00pm EST" in page.digest or "5:00pm EST" in page.visible_text
    assert "Learn AR with SPECS" in page.title


def test_refuses_localhost():
    with pytest.raises(ValueError):
        assert_public_http_url("http://127.0.0.1/secret")
    with pytest.raises(ValueError):
        assert_public_http_url("file:///etc/passwd")
