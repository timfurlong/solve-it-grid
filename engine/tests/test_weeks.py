from datetime import date, datetime

from sig.weeks import Week, ended_at, week_of


def test_week_of_sunday_and_monday():
    assert week_of(date(2026, 10, 4)).start == date(2026, 9, 28)
    assert week_of(date(2026, 10, 5)).start == date(2026, 10, 5)


def test_week_navigation_and_contains():
    w = Week(date(2026, 9, 28))
    assert w.end == date(2026, 10, 5)
    assert w.prev().start == date(2026, 9, 21) and w.next().start == date(2026, 10, 5)
    assert w.contains(date(2026, 10, 4)) and not w.contains(date(2026, 10, 5))


def test_ended_at_is_local_midnight_after_sunday():
    end = ended_at(Week(date(2026, 9, 28)))
    assert end.tzinfo is not None
    assert end.replace(tzinfo=None) == datetime(2026, 10, 5, 0, 0)
