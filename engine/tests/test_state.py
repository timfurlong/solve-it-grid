from datetime import date, datetime, timedelta

import pytest

from sig.state import FrozenWeek, StateStore

NOW = datetime(2026, 10, 1, 10, 0).astimezone()
WK = date(2026, 9, 28)


@pytest.fixture
def store(tmp_path):
    return StateStore(tmp_path / "state.db")


def test_award_is_idempotent(store):
    chip = store.award_chip(WK, "yellow-home", "yellow", NOW)
    assert chip is not None and chip.unit == "yellow-home" and chip.acked_at is None
    assert store.award_chip(WK, "yellow-home", "yellow", NOW + timedelta(minutes=1)) is None
    assert len(store.chips_for_week(WK)) == 1


def test_ack_all_and_some(store):
    a = store.award_chip(WK, "yellow-work", "yellow", NOW)
    store.award_chip(WK, "green-1", "green", NOW)
    store.award_chip(WK, "green-2", "green", NOW)
    assert store.ack_chips([a.id], NOW) == 1
    assert [c.unit for c in store.pending_chips()] == ["green-1", "green-2"]
    assert store.ack_chips(None, NOW) == 2
    assert store.pending_chips() == []
    assert store.ack_chips(None, NOW) == 0


def test_total_earned_counts_acked_only(store):
    a = store.award_chip(WK, "yellow-work", "yellow", NOW)
    store.award_chip(WK, "green-1", "green", NOW)
    assert store.total_earned() == 0
    store.ack_chips([a.id], NOW)
    assert store.total_earned() == 1


def test_freeze_roundtrip_and_order(store):
    later = FrozenWeek(date(2026, 9, 28), 4, 4, True, 4)
    earlier = FrozenWeek(date(2026, 9, 21), 2, 4, False, 2)
    store.freeze_week(later, NOW)
    store.freeze_week(earlier, NOW)
    assert store.frozen_weeks() == [earlier, later]
    assert store.is_frozen(date(2026, 9, 21)) and not store.is_frozen(date(2026, 9, 14))


def test_checkin_done_and_ticks_are_per_day(store):
    d1, d2 = date(2026, 9, 28), date(2026, 9, 29)
    store.set_checkin_done(d1, NOW)
    store.tick(d1, "someday-review", NOW)
    assert store.checkin_done(d1) and not store.checkin_done(d2)
    assert store.ticks(d1) == {"someday-review"} and store.ticks(d2) == set()


def test_failure_streak_resets_on_success(store):
    t = [NOW + timedelta(minutes=10 * i) for i in range(4)]
    store.record_run("categorize", False, "boom 1", t[0])
    store.record_run("categorize", False, "boom 2", t[1])
    assert store.failure_streak("categorize") == (2, t[0], "boom 2")
    store.record_run("categorize", True, None, t[2])
    assert store.failure_streak("categorize") == (0, None, None)
    store.record_run("categorize", False, "boom 3", t[3])
    assert store.failure_streak("categorize") == (1, t[3], "boom 3")
    assert store.failure_streak("other") == (0, None, None)


def test_meta_roundtrip(store):
    assert store.get_meta("review_applied_at") is None
    store.set_meta("review_applied_at", "x")
    store.set_meta("review_applied_at", "y")
    assert store.get_meta("review_applied_at") == "y"


def test_persists_across_instances(tmp_path):
    StateStore(tmp_path / "s.db").award_chip(WK, "green-1", "green", NOW)
    assert len(StateStore(tmp_path / "s.db").pending_chips()) == 1
