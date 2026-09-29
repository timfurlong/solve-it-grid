from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
from factories import snapshot, todo

from sig.config import load_config
from sig.paths import repo_root
from sig.progress import refresh, scoring_cutoff
from sig.state import FrozenWeek, StateStore

Y, G = "🟡 Yellow", "🟢 Green"


def local(*args):
    return datetime(*args).astimezone()


@pytest.fixture
def cfg():
    return replace(load_config(repo_root() / "config.example.toml"), start_week=date(2026, 9, 21))


@pytest.fixture
def state(tmp_path):
    return StateStore(tmp_path / "state.db")


def done(uuid, stop, tags=(Y,), area_id="A-W"):
    return todo(uuid=uuid, status="completed", stop=stop, tags=tags, area_id=area_id)


THU = datetime(2026, 10, 1, 9, 0)


def test_chip_awarded_once_when_unit_fills(cfg, state):
    snap = snapshot([done("w", THU)])
    first = refresh(snap, state, cfg, local(2026, 10, 1, 10, 0))
    second = refresh(snap, state, cfg, local(2026, 10, 1, 10, 1))
    assert [c.unit for c in first.new_chips] == ["yellow-work"]
    assert second.new_chips == [] and len(state.pending_chips()) == 1


def test_green_units_award_in_order(cfg, state):
    p = refresh(snapshot([done("g", THU, tags=(G,))]), state, cfg, local(2026, 10, 1, 10, 0))
    assert [c.unit for c in p.new_chips] == ["green-1"]


def test_chip_not_revoked_when_completion_disappears(cfg, state):
    refresh(snapshot([done("w", THU)]), state, cfg, local(2026, 10, 1, 10, 0))
    p = refresh(snapshot([]), state, cfg, local(2026, 10, 1, 11, 0))
    assert len(state.pending_chips()) == 1 and not p.current.units[0].done


def test_late_colored_completion_awards_past_unfrozen_week(cfg, state):
    uncolored = done("w", THU, tags=())
    monday = local(2026, 10, 5, 10, 0)
    refresh(snapshot([uncolored]), state, cfg, monday)
    assert state.chips_for_week(date(2026, 9, 28)) == [] and not state.is_frozen(date(2026, 9, 28))
    p = refresh(snapshot([done("w", THU)]), state, cfg, monday + timedelta(minutes=10))
    assert [(c.week_start, c.unit) for c in p.new_chips] == [(date(2026, 9, 28), "yellow-work")]


def test_monday_sync_still_counts_before_grace_ends(cfg, state):
    """A completion that syncs from the phone after the week ended still counts for 48 hours."""
    refresh(snapshot([done("w", datetime(2026, 9, 23, 9, 0))]), state, cfg, local(2026, 9, 28, 8, 0))
    assert not state.is_frozen(date(2026, 9, 21))
    synced = [done("w", datetime(2026, 9, 23, 9, 0)), done("g", datetime(2026, 9, 27, 20, 0), tags=(G,))]
    p = refresh(snapshot(synced), state, cfg, local(2026, 9, 28, 9, 0))
    assert [c.unit for c in p.new_chips] == ["green-1"]


def test_freezes_only_after_48h(cfg, state):
    snap = snapshot([done("w", datetime(2026, 9, 23, 9, 0))])
    refresh(snap, state, cfg, local(2026, 9, 29, 23, 59))
    assert not state.is_frozen(date(2026, 9, 21))
    refresh(snap, state, cfg, local(2026, 9, 30, 0, 0))
    assert state.frozen_weeks() == [FrozenWeek(date(2026, 9, 21), 1, 4, False, 1)]


def test_no_freeze_while_setup_is_broken(cfg, state):
    snap = snapshot([done("h", datetime(2026, 9, 22, 9, 0), area_id="A-H")], area_ids={"Work": "A-W"})
    refresh(snap, state, cfg, local(2026, 10, 1, 8, 0))
    assert state.frozen_weeks() == []


def test_history_includes_unfrozen_past_week(cfg, state):
    p = refresh(snapshot([done("w", datetime(2026, 9, 23, 9, 0))]), state, cfg, local(2026, 9, 28, 8, 0))
    assert [(fw.week_start, fw.units_done) for fw in p.history] == [(date(2026, 9, 21), 1)]


def test_frozen_week_ignores_late_synced_completion(cfg, state):
    two = [done("w", datetime(2026, 9, 22, 9, 0)), done("h", datetime(2026, 9, 22, 9, 0), area_id="A-H")]
    refresh(snapshot(two), state, cfg, local(2026, 9, 30, 8, 0))
    frozen = state.frozen_weeks()
    late = done("g", datetime(2026, 9, 24, 9, 0), tags=(G,))
    p = refresh(snapshot([*two, late]), state, cfg, local(2026, 10, 1, 8, 0))
    assert p.new_chips == [] and state.frozen_weeks() == frozen
    assert frozen == [FrozenWeek(date(2026, 9, 21), 2, 4, False, 2)]


def test_weeks_before_start_week_ignored(cfg, state):
    p = refresh(snapshot([done("w", datetime(2026, 9, 15, 9, 0))]), state, cfg, local(2026, 9, 22, 8, 0))
    assert p.new_chips == [] and state.frozen_weeks() == []


def _freeze(state, start, hit):
    state.freeze_week(FrozenWeek(start, 4 if hit else 1, 4, hit, 4 if hit else 1), local(2026, 1, 1, 0, 0))


def _full_week(stop):
    return [done("w", stop), done("h", stop, area_id="A-H"),
            done("g1", stop, tags=(G,)), done("g2", stop, tags=(G,))]


def test_streak_and_best(cfg, state):
    cfg = replace(cfg, start_week=date(2026, 8, 24))
    for start, hit in [(date(2026, 8, 24), True), (date(2026, 8, 31), True), (date(2026, 9, 7), False),
                       (date(2026, 9, 14), True), (date(2026, 9, 21), True)]:
        _freeze(state, start, hit)
    p = refresh(snapshot(_full_week(THU)), state, cfg, local(2026, 10, 1, 10, 0))
    assert (p.streak, p.best_streak) == (3, 3)
    assert p.last_week == FrozenWeek(date(2026, 9, 21), 4, 4, True, 4)


def test_current_week_not_hit_does_not_break_streak(cfg, state):
    cfg = replace(cfg, start_week=date(2026, 9, 14))
    _freeze(state, date(2026, 9, 14), True)
    _freeze(state, date(2026, 9, 21), True)
    p = refresh(snapshot([]), state, cfg, local(2026, 10, 1, 10, 0))
    assert (p.streak, p.best_streak) == (2, 2)


def test_history_is_last_12_frozen_weeks(cfg, state):
    starts = [date(2026, 6, 22) + timedelta(weeks=i) for i in range(14)]
    cfg = replace(cfg, start_week=starts[0])
    for s in starts:
        _freeze(state, s, True)
    p = refresh(snapshot([]), state, cfg, local(2026, 10, 1, 10, 0))
    assert [fw.week_start for fw in p.history] == starts[2:]


def test_scoring_cutoff(cfg, state):
    assert scoring_cutoff(state, cfg, date(2026, 10, 1)) == date(2026, 9, 21)
    _freeze(state, date(2026, 9, 21), True)
    assert scoring_cutoff(state, cfg, date(2026, 10, 1)) == date(2026, 9, 28)
    assert scoring_cutoff(state, replace(cfg, start_week=None), date(2026, 10, 1)) == date(2026, 9, 28)
