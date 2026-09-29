import json
from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
from factories import DEFAULT_TAGS, snapshot, todo

from solve_it_grid.config import load_config
from solve_it_grid.paths import repo_root
from solve_it_grid.state import StateStore
from solve_it_grid.status import build_status, health_errors, render_text

NOW = datetime(2026, 10, 1, 10, 0).astimezone()
Y = "🟡"


@pytest.fixture
def cfg():
    return replace(load_config(repo_root() / "config.example.toml"), start_week=date(2026, 9, 28))


@pytest.fixture
def state(tmp_path):
    s = StateStore(tmp_path / "state.db")
    s.set_meta("review_applied_at", "2026-09-28T10:00:00")
    return s


def test_status_shape(cfg, state):
    snap = snapshot([todo(uuid="h", status="completed", stop=datetime(2026, 9, 30, 9, 0), tags=[Y],
                          area_id="A-H")])
    st = build_status(snap, state, cfg, NOW)
    json.dumps(st)
    assert set(st) == {"generated_at", "week", "units", "red_done", "chips", "streak", "checkin",
                       "last_week", "history", "health"}
    assert st["week"] == {"start": "2026-09-28", "end": "2026-10-04", "hit": False}
    assert [u["id"] for u in st["units"]] == ["yellow-work", "yellow-home", "green-1", "green-2"]
    assert st["units"][1] == {"id": "yellow-home", "color": "yellow", "label": "Home yellow", "done": True}
    pending = st["chips"]["pending"]
    assert [(c["unit"], c["color"]) for c in pending] == [("yellow-home", "yellow")]
    assert set(pending[0]) == {"id", "week_start", "unit", "color", "awarded_at"}
    assert pending[0]["week_start"] == "2026-09-28"
    assert st["chips"]["total_earned"] == 0
    assert st["streak"] == {"current": 0, "best": 0}
    assert set(st["checkin"]) == {"workday", "due", "done", "steps"}
    assert st["checkin"]["due"] is True
    assert set(st["checkin"]["steps"][0]) == {"id", "label", "done", "manual", "links"}
    manual = {s["id"]: s["manual"] for s in st["checkin"]["steps"]}
    assert manual["inbox"] is False and manual["colors-reviewed"] is True
    assert st["last_week"] is None and st["history"] == []
    assert st["health"] == {"ok": True, "errors": []}


def test_missing_tag_reported(cfg, state):
    snap = snapshot(tag_names=DEFAULT_TAGS - {"🟢"})
    assert health_errors(snap, state, cfg, NOW) == [
        {"source": "setup", "message": "Missing Things tags: 🟢. Run solve-it-grid setup.",
         "since": None}]


def test_missing_area_reported(cfg, state):
    snap = snapshot(area_ids={"👨‍💻 Work": "A-W", "Home": "A-H"})
    assert health_errors(snap, state, cfg, NOW) == [
        {"source": "setup", "message": "Things area 'Work' not found. Check [areas] in config.toml.",
         "since": None}]


def test_token_off_reported(cfg, state):
    errors = health_errors(snapshot(token_present=False), state, cfg, NOW)
    assert [e["message"] for e in errors] == [
        "Things URLs are off. Enable them in Things > Settings > General."]


def test_review_pending_reported(cfg, tmp_path):
    fresh = StateStore(tmp_path / "fresh.db")
    assert [e["message"] for e in health_errors(snapshot(), fresh, cfg, NOW)] == [
        "First review pending. Run solve-it-grid categorize --dry-run, "
        "then solve-it-grid categorize --apply-review."]


def test_categorizer_streak_reported_with_since(cfg, state):
    first = NOW - timedelta(minutes=30)
    for i in range(3):
        state.record_run("categorize", False, f"Not logged in {i}", first + timedelta(minutes=10 * i))
    assert health_errors(snapshot(), state, cfg, NOW) == [
        {"source": "categorizer", "message": "Not logged in 2", "since": first.isoformat()}]


def test_two_failures_are_not_an_error(cfg, state):
    for _ in range(2):
        state.record_run("categorize", False, "boom", NOW)
    assert health_errors(snapshot(), state, cfg, NOW) == []


def test_render_text_mentions_pending_chip(cfg, state):
    snap = snapshot([todo(uuid="h", status="completed", stop=datetime(2026, 9, 30, 9, 0), tags=[Y],
                          area_id="A-H")], token_present=False)
    text = render_text(build_status(snap, state, cfg, NOW))
    assert "Move a yellow chip" in text
    assert "Home yellow" in text
    assert "Things URLs are off" in text
