from rulesminion.models import HackathonBrief, PrizeItem
from rulesminion.snapshots import SnapshotStore, diff_briefs, first_seen_report


def _brief(**overrides) -> HackathonBrief:
    data = dict(
        title="Cortensor Hackathon #5",
        url="https://dorahacks.io/hackathon/2418/detail",
        organizer="Cortensor",
        format="online",
        prize_pool="1,150 USD",
        prizes=[PrizeItem(place="1st", amount="$500", notes="paid in $COR")],
        india_eligible="yes",
        eligibility_summary="Virtual worldwide event",
        submission_checklist=["Public repo", "Demo video"],
    )
    data.update(overrides)
    return HackathonBrief.model_validate(data)


def test_first_then_changed_then_unchanged(tmp_path):
    store = SnapshotStore(tmp_path)
    url = "https://dorahacks.io/hackathon/2418/detail"
    assert store.latest(url) is None
    first = store.save(url, _brief())
    assert first.brief.prize_pool == "1,150 USD"
    second_brief = _brief(prize_pool="1,500 USD", submission_checklist=["Public repo", "Demo video", "PR"])
    report = diff_briefs(first.brief, second_brief, previous_checked_at_ist=first.checked_at_ist)
    assert report.status == "changed"
    assert any(item.path == "prize_pool" for item in report.changed)
    assert any(item.startswith("submission_checklist:") for item in report.added)
    store.save(url, second_brief)
    latest = store.latest(url)
    unchanged = diff_briefs(latest.brief, second_brief)
    assert unchanged.status == "unchanged"
    assert len(store.history(url)) == 2


def test_first_seen_report():
    report = first_seen_report()
    assert report.status == "first_seen"


def test_wording_only_and_money_punctuation_are_unchanged():
    before = _brief(
        prize_pool="$1,150 USD",
        eligibility_summary="Online virtual hackathon open to builders globally.",
        prizes=[PrizeItem(place="1st place", amount="$500 total", notes="old notes")],
        deadlines=[{"label": "Submission deadline", "as_stated": "2026/12/19 07:59 (UTC)", "ist": "2026-12-19 13:29 IST"}],
    )
    after = _brief(
        prize_pool="1,150 USD",
        eligibility_summary="The hackathon is held virtually and open to global participants.",
        prizes=[PrizeItem(place="1st place", amount="$500 total", notes="new notes")],
        deadlines=[{"label": "Submission Deadline", "as_stated": "2026/12/19 07:59 UTC", "ist": "2026-12-19 13:29 IST"}],
    )
    report = diff_briefs(before, after)
    assert report.status == "unchanged"
