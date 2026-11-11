from rulesminion.timeutil import format_ist, from_iso, from_unix, iso_to_ist_label, unix_to_ist_label


def test_unix_deadline_converts_to_ist():
    # 2026-12-19 07:59 UTC == 2026-12-19 13:29 IST
    assert unix_to_ist_label(1797667140) == "2026-12-19 13:29 IST"
    assert format_ist(from_unix(1797667140)) == "2026-12-19 13:29 IST"


def test_iso_utc_converts_to_ist():
    assert iso_to_ist_label("2026-12-19T07:59:00.000Z") == "2026-12-19 13:29 IST"
    assert from_iso("2026-12-19T07:59:00.000Z") is not None


def test_est_afternoon_is_next_morning_ist():
    # 5:00pm EST = 22:00 UTC = 03:30 IST next day
    assert iso_to_ist_label("2026-12-07T17:00:00-05:00") == "2026-12-08 03:30 IST"
