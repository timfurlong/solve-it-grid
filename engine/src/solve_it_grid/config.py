"""Load config.toml into typed settings."""

import tomllib
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Literal, get_args

from solve_it_grid.paths import app_dir

Color = Literal["red", "yellow", "green", "blue", "unscored"]
COLORS: tuple[Color, ...] = get_args(Color)
GOAL_AREAS = ("work", "home", "any")


@dataclass(frozen=True)
class Goal:
    id: str
    label: str
    color: Color
    area: str
    target: int


@dataclass(frozen=True)
class Config:
    start_week: date | None
    rubric_path: Path | None
    claude_path: Path | None
    tags: dict[Color, str]
    areas: dict[str, str]
    goals: tuple[Goal, ...]
    checkin_time: time
    holidays_country: str
    model: str
    batch_size: int
    timeout_seconds: int
    failure_threshold: int


def config_path() -> Path:
    return app_dir() / "config.toml"


def _optional(value: str) -> str | None:
    return value or None


def _goal(raw: dict) -> Goal:
    goal = Goal(id=raw["id"], label=raw["label"], color=raw["color"], area=raw["area"],
                target=int(raw["target"]))
    if goal.color not in COLORS:
        raise ValueError(f"goal {goal.id!r}: unknown color {goal.color!r}")
    if goal.area not in GOAL_AREAS:
        raise ValueError(f"goal {goal.id!r}: area must be one of {GOAL_AREAS}, got {goal.area!r}")
    if goal.target < 1:
        raise ValueError(f"goal {goal.id!r}: target must be at least 1")
    return goal


def load_config(path: Path) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    start = _optional(raw.get("start_week", ""))
    paths = raw.get("paths", {})
    rubric = _optional(paths.get("rubric", ""))
    claude = _optional(paths.get("claude", ""))
    tags = raw["tags"]
    missing = [c for c in COLORS if c not in tags]
    if missing:
        raise ValueError(f"[tags] is missing {', '.join(missing)}")
    checkin = raw["checkin"]
    categorizer = raw["categorizer"]
    return Config(
        start_week=date.fromisoformat(start) if start else None,
        rubric_path=Path(rubric) if rubric else None,
        claude_path=Path(claude) if claude else None,
        tags={c: tags[c] for c in COLORS},
        areas=dict(raw["areas"]),
        goals=tuple(_goal(g) for g in raw["goals"]),
        checkin_time=time.fromisoformat(checkin["time"]),
        holidays_country=checkin["holidays"],
        model=categorizer["model"],
        batch_size=int(categorizer["batch_size"]),
        timeout_seconds=int(categorizer["timeout_seconds"]),
        failure_threshold=int(categorizer["failure_threshold"]),
    )
