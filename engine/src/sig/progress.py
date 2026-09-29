"""Award chips, freeze finished weeks, and compute streaks and history."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sig.config import Config
from sig.model import Snapshot
from sig.scoring import WeekScore, score_week
from sig.setup_check import setup_problems
from sig.state import Chip, FrozenWeek, StateStore
from sig.weeks import Week, ended_at, week_of

# Phone completions sync when the Mac wakes, so a finished week stays open this long.
FREEZE_GRACE = timedelta(hours=48)
HISTORY_WEEKS = 12


@dataclass(frozen=True)
class Progress:
    current: WeekScore
    new_chips: list[Chip]
    streak: int
    best_streak: int
    history: list[FrozenWeek]
    last_week: FrozenWeek | None


def _first_week(cfg: Config, today: date) -> Week:
    return week_of(cfg.start_week or today)


def scoring_cutoff(state: StateStore, cfg: Config, today: date) -> date:
    """Start of the earliest week that still needs scoring (for read_snapshot)."""
    current = week_of(today)
    w = _first_week(cfg, today)
    while w < current and state.is_frozen(w.start):
        w = w.next()
    return min(w.start, current.start)


def _as_frozen(score: WeekScore, chips: int) -> FrozenWeek:
    return FrozenWeek(score.week.start, sum(u.done for u in score.units), len(score.units), score.hit, chips)


def _runs(hits: list[bool]) -> tuple[int, int]:
    """(trailing run of True, longest run of True)."""
    best = run = 0
    for hit in hits:
        run = run + 1 if hit else 0
        best = max(best, run)
    return run, best


def refresh(snapshot: Snapshot, state: StateStore, cfg: Config, now: datetime) -> Progress:
    today = now.date()
    current = week_of(today)
    first = _first_week(cfg, today)
    # A broken setup (renamed tag or area) under-counts, so never lock in a week while it lasts.
    can_freeze = not setup_problems(snapshot, cfg)
    new_chips: list[Chip] = []
    live: dict[date, WeekScore] = {}
    current_score: WeekScore | None = None

    w = first
    while w <= current:
        if state.is_frozen(w.start):
            w = w.next()
            continue
        score = score_week(snapshot.todos, cfg, snapshot.area_ids, w)
        for unit in score.units:
            if unit.done and (chip := state.award_chip(w.start, unit.id, unit.color, now)):
                new_chips.append(chip)
        if w == current:
            current_score = score
        elif can_freeze and now >= ended_at(w) + FREEZE_GRACE:
            state.freeze_week(_as_frozen(score, len(state.chips_for_week(w.start))), now)
        else:
            live[w.start] = score
        w = w.next()

    if current_score is None:  # start_week lies in the future
        current_score = score_week(snapshot.todos, cfg, snapshot.area_ids, current)

    frozen = {fw.week_start: fw for fw in state.frozen_weeks() if fw.week_start >= first.start}
    hits: list[bool] = []
    w = first
    while w < current:
        if w.start in frozen:
            hits.append(frozen[w.start].hit)
        else:
            hits.append(live[w.start].hit if w.start in live else False)
        w = w.next()
    if current_score.hit:
        hits.append(True)
    streak, best = _runs(hits)

    prev = current.prev().start
    if prev in frozen:
        last_week = frozen[prev]
    elif prev in live:
        last_week = _as_frozen(live[prev], len(state.chips_for_week(prev)))
    else:
        last_week = None

    past = dict(frozen)
    past.update({start: _as_frozen(score, len(state.chips_for_week(start))) for start, score in live.items()})
    history = [past[start] for start in sorted(past)][-HISTORY_WEEKS:]
    return Progress(
        current=current_score, new_chips=new_chips, streak=streak, best_streak=best,
        history=history, last_week=last_week,
    )
