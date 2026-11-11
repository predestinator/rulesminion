from pathlib import Path

import pytest

from rulesminion.pages import assert_public_http_url, canonical_url, looks_blocked, parse_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_canonical_url_strips_slash_and_fragment():
    assert (
        canonical_url("https://DoraHacks.io/hackathon/2418/detail/")
        == "https://dorahacks.io/hackathon/2418/detail"
    )


def test_refuses_localhost():
    with pytest.raises(ValueError):
        assert_public_http_url("http://127.0.0.1:8066/")


def test_dora_fixture_digest_includes_prize_and_ist():
    html = (FIXTURES / "sample_dora.html").read_text(encoding="utf-8")
    page = parse_page("https://dorahacks.io/hackathon/2418/detail", html)
    assert "Cortensor Hackathon #5" in page.title
    assert "1,150 USD" in page.visible_text
    assert "2026-12-19 13:29 IST" in page.digest
    assert "OpenMinion" in page.digest


def test_devpost_fixture_keeps_deadline_and_prize():
    html = (FIXTURES / "sample_devpost.html").read_text(encoding="utf-8")
    page = parse_page("https://learn-specs.devpost.com/", html)
    assert "2,500" in page.digest
    assert "5:00pm EST" in page.digest
    assert "Deadline" in page.digest


def test_looks_blocked_on_interstitial():
    page = parse_page(
        "https://example.com/challenge",
        "<html><title>Just a moment...</title><body>Checking your browser</body></html>",
    )
    assert looks_blocked(page)
    ok = parse_page(
        "https://dorahacks.io/hackathon/2418/detail",
        (FIXTURES / "sample_dora.html").read_text(encoding="utf-8"),
    )
    assert not looks_blocked(ok)
