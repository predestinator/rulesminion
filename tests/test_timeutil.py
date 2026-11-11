from datetime import datetime, timezone

from rulesminion.timeutil import format_ist, from_iso, from_unix, iso_to_ist_label, unix_to_ist_label


def test_unix_timeline_end_is_19_dec_afternoon_ist():
    # DoraHacks timelineEnd for Cortensor #5: 2026-12-19 07:59 UTC
    assert unix_to_ist_label(1797667140) == "2026-12-19 13:29 IST"


def test_iso_zulu_converts_to_ist():
    assert iso_to_ist_label("2026-12-19T07:59:00.000Z") == "2026-12-19 13:29 IST"


def test_est_5pm_is_next_morning_ist():
    # 7 Dec 2026 17:00 EST = 7 Dec 22:00 UTC = 8 Dec 03:30 IST
    from datetime import timedelta, timezone as tz

    est = tz(timedelta(hours=-5))
    source = datetime(2026, 12, 7, 17, 0, tzinfo=est)
    assert format_ist(source) == "2026-12-08 03:30 IST"


def test_from_iso_naive_is_treated_as_utc():
    dt = from_iso("2026-10-16T07:00:00")
    assert dt is not None
    assert format_ist(dt) == "2026-10-16 12:30 IST"


def test_from_unix_matches_from_iso():
    assert format_ist(from_unix(1792134000)) == iso_to_ist_label("2026-10-16T07:00:00.000Z")
