"""Evaluate the daily check-in against live Things data."""

import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime

import holidays

from sig.config import Color, Config
from sig.model import Snapshot, Todo, colors_of
from sig.weeks import week_of

# Steps the user ticks by hand; every other step checks itself against Things.
MANUAL_STEPS = ("today-reviewed", "colors-reviewed", "someday-review")


@dataclass(frozen=True)
class Link:
    label: str
    url: str


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    done: bool
    links: tuple[Link, ...]


@dataclass(frozen=True)
class Checkin:
    workday: bool
    due: bool
    done: bool
    steps: tuple[Step, ...]


def is_workday(day: date, country: str) -> bool:
    return day.weekday() < 5 and day not in holidays.country_holidays(country, years=day.year)


def show_url(**params: str) -> str:
    return "things:///show?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _item_link(uuid: str, title: str) -> Link:
    return Link(title.strip() or "(untitled)", show_url(id=uuid))


def _color_step(color: Color, open_todos: list[Todo], cfg: Config) -> Step:
    tagged = [t for t in open_todos if color in colors_of(t, cfg.tags)]
    in_today = any(t.in_today for t in tagged)
    done = in_today or (color == "red" and not tagged)
    label = f"A {color} is in Today"
    return Step(color, label, done, (Link("Show", show_url(query=cfg.tags[color])),))


def evaluate_checkin(snapshot: Snapshot, cfg: Config, now: datetime, done: bool,
                     ticks: set[str]) -> Checkin:
    today = now.date()
    workday = is_workday(today, cfg.holidays_country)
    due = workday and now.time() >= cfg.checkin_time and not done
    open_todos = [t for t in snapshot.todos if t.status == "incomplete"]
    this_week = week_of(today)

    steps = [
        Step("inbox", "Inbox is empty", snapshot.inbox_count == 0,
             (Link("Show", show_url(id="inbox")),)),
        *(_color_step(c, open_todos, cfg) for c in ("red", "yellow", "green")),
        Step("today-reviewed", "Today's list is reviewed", "today-reviewed" in ticks,
             (Link("Show", show_url(id="today")),)),
        Step("colors-reviewed", "Colors look right", "colors-reviewed" in ticks,
             (Link("Show", show_url(id="today")),)),
    ]

    completed_this_week = [
        t for t in snapshot.todos
        if t.status == "completed" and t.stop is not None and this_week.contains(t.stop.date())
    ]
    needs_area = [_item_link(t.uuid, t.title) for t in open_todos
                  if t.start != "Inbox" and t.area_id is None and t.project_id is None]
    needs_area += [_item_link(t.uuid, t.title) for t in completed_this_week
                   if t.area_id is None and t.project_id is None]
    needs_area += [_item_link(p.uuid, p.title) for p in snapshot.projects if p.area_id is None]
    if needs_area:
        steps.append(Step("areas", f"Give {_plural(len(needs_area), 'item')} an area", False,
                          tuple(needs_area)))

    recent = [t for t in snapshot.todos
              if t.status == "incomplete" or (t.stop is not None and this_week.contains(t.stop.date()))]
    broken = [_item_link(t.uuid, t.title) for t in recent
              if not t.title.strip() or len(colors_of(t, cfg.tags)) > 1]
    if broken:
        steps.append(Step("fix", f"Fix {_plural(len(broken), 'item')}", False, tuple(broken)))

    if today.weekday() == 0:
        steps.append(Step("someday-review", "Review Someday", "someday-review" in ticks,
                          (Link("Show", show_url(id="someday")),)))

    return Checkin(workday=workday, due=due, done=done, steps=tuple(steps))
