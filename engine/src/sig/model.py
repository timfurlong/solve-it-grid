"""Immutable records read from Things."""

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from sig.config import COLORS, Color

Status = Literal["incomplete", "completed", "canceled"]


@dataclass(frozen=True)
class Todo:
    uuid: str
    title: str
    notes: str
    status: Status
    start: str
    start_date: date | None
    deadline: date | None
    stop: datetime | None
    area_id: str | None
    project_id: str | None
    project_title: str | None
    heading_title: str | None
    tags: tuple[str, ...]
    in_today: bool


@dataclass(frozen=True)
class Project:
    uuid: str
    title: str
    notes: str
    area_id: str | None
    status: Status


@dataclass(frozen=True)
class Snapshot:
    todos: tuple[Todo, ...]
    projects: tuple[Project, ...]
    area_ids: dict[str, str]
    tag_names: frozenset[str]
    inbox_count: int
    token_present: bool


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def colors_of(todo: Todo, tags: dict[Color, str]) -> list[Color]:
    """Grid colors whose tag is on the to-do, in COLORS order."""
    present = {_norm(t) for t in todo.tags}
    return [c for c in COLORS if _norm(tags[c]) in present]


def list_name(todo: Todo, today: date) -> str:
    """The Things list a to-do appears in. Things stores scheduled to-dos as Someday + a start date."""
    if todo.start == "Inbox":
        return "Inbox"
    if todo.in_today:
        return "Today"
    if todo.start == "Someday":
        if todo.start_date is None:
            return "Someday"
        return "Upcoming" if todo.start_date > today else "Today"
    return "Anytime"
