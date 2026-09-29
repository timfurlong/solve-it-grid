"""Score a week's completions against the configured goals."""

from collections.abc import Iterable
from dataclasses import dataclass

from solve_it_grid.config import Color, Config, Goal
from solve_it_grid.model import Todo, colors_of
from solve_it_grid.weeks import Week


@dataclass(frozen=True)
class Unit:
    id: str
    goal_id: str
    label: str
    color: Color
    done: bool


@dataclass(frozen=True)
class WeekScore:
    week: Week
    counts: dict[str, int]
    units: tuple[Unit, ...]
    hit: bool
    red_done: int
    uncolored_completed: tuple[str, ...]
    multi_color: tuple[str, ...]


def _unit_specs(goals: tuple[Goal, ...]) -> list[tuple[str, Goal, int]]:
    """(unit id, goal, 1-based index) for every unit of every goal."""
    return [
        (goal.id if goal.target == 1 else f"{goal.id}-{i}", goal, i)
        for goal in goals
        for i in range(1, goal.target + 1)
    ]


def unit_ids(goals: tuple[Goal, ...]) -> list[str]:
    return [uid for uid, _, _ in _unit_specs(goals)]


def _matches_area(goal: Goal, todo: Todo, cfg: Config, area_ids: dict[str, str]) -> bool:
    if goal.area == "any":
        return True
    wanted = area_ids.get(cfg.areas[goal.area])
    return wanted is not None and todo.area_id == wanted


def score_week(todos: Iterable[Todo], cfg: Config, area_ids: dict[str, str], week: Week) -> WeekScore:
    counts = {g.id: 0 for g in cfg.goals}
    red_done = 0
    uncolored: list[str] = []
    multi: list[str] = []
    for t in todos:
        if t.status != "completed" or t.stop is None or not week.contains(t.stop.date()):
            continue
        colors = colors_of(t, cfg.tags)
        if not colors:
            uncolored.append(t.uuid)
            continue
        if len(colors) > 1:
            multi.append(t.uuid)
            continue
        color = colors[0]
        if color == "red":
            red_done += 1
        for goal in cfg.goals:
            if goal.color == color and _matches_area(goal, t, cfg, area_ids):
                counts[goal.id] += 1
    units = tuple(
        Unit(id=uid, goal_id=goal.id, label=goal.label, color=goal.color, done=counts[goal.id] >= i)
        for uid, goal, i in _unit_specs(cfg.goals)
    )
    return WeekScore(
        week=week, counts=counts, units=units, hit=all(u.done for u in units), red_done=red_done,
        uncolored_completed=tuple(uncolored), multi_color=tuple(multi),
    )
