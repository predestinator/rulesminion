from rulesminion.models import DeadlineItem, HackathonBrief, PrizeItem
from rulesminion.snapshots import SnapshotStore, diff_briefs, first_seen_report


def _brief(**overrides) -> HackathonBrief:
    data = dict(
        title="Cortensor Hackathon #5",
        url="https://dorahacks.io/hackathon/2418/detail",
        organizer="Cortensor",
        format="online",
        prize_pool="1,150 USD",
        prizes=[PrizeItem(place="1st", amount="$500", notes="paid in $COR")],
        deadlines=[
            DeadlineItem(
                label="Submission deadline",
                as_stated="2026/12/19 07:59",
                timezone_as_stated="UTC",
                ist="2026-12-19 13:29 IST",
                confidence="high",
            )
        ],
        india_eligible="yes",
        eligibility_summary="Virtual worldwide hackathon",
        submission_checklist=["Public repo", "Demo video", "What We Learned"],
    )
    data.update(overrides)
    return HackathonBrief.model_validate(data)


def test_first_then_unchanged_then_changed(tmp_path):
    store = SnapshotStore(tmp_path)
    url = "https://dorahacks.io/hackathon/2418/detail"
    assert store.latest(url) is None
    first = store.save(url, _brief())
    assert first.snapshot_id
    assert first_seen_report().status == "first_seen"

    same = diff_briefs(first.brief, _brief(), previous_checked_at_ist=first.checked_at_ist)
    assert same.status == "unchanged"

    updated = _brief(prize_pool="1,250 USD", submission_checklist=["Public repo", "Demo video", "What We Learned", "Wallet"])
    changed = diff_briefs(first.brief, updated)
    assert changed.status == "changed"
    assert any(item.path == "prize_pool" for item in changed.changed)
    assert any(item.startswith("submission_checklist:") for item in changed.added)

    store.save(url, updated)
    assert len(store.history(url)) == 2


def test_string_coercion_in_model():
    brief = HackathonBrief.model_validate(
        {
            "title": "X",
            "url": "https://example.com",
            "india_eligible": "YES",
            "prizes": ["$100"],
            "deadlines": ["Dec 1"],
            "submission_checklist": "Send a demo",
        }
    )
    assert brief.india_eligible == "yes"
    assert brief.prizes[0].amount == "$100"
    assert brief.deadlines[0].as_stated == "Dec 1"
    assert brief.submission_checklist == ["Send a demo"]
