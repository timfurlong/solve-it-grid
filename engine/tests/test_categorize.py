import json
from datetime import date, datetime, timedelta

import pytest
from factories import project, snapshot, todo
from fakes import FakeClassifier, FakeThings, LaggyThings

from solve_it_grid.categorize import (
    AlreadyRunning,
    NotReviewed,
    SetupIncomplete,
    run_categorize,
    run_lock,
    select_work,
)
from solve_it_grid.classifier import ClassifierError
from solve_it_grid.config import load_config
from solve_it_grid.paths import repo_root
from solve_it_grid.state import StateStore
from solve_it_grid.things_read import ThingsUnavailable

NOW = datetime(2026, 10, 1, 10, 0).astimezone()
TODAY = NOW.date()
Y = "🟡"


@pytest.fixture
def cfg():
    return load_config(repo_root() / "config.example.toml")


@pytest.fixture
def state(tmp_path):
    s = StateStore(tmp_path / "state.db")
    s.set_meta("review_applied_at", "2026-09-28T10:00:00")
    return s


def run(things, classifier, state, cfg, tmp_path, **kw):
    return run_categorize(read=things.read, writer=things, classifier=classifier, state=state, cfg=cfg,
                          now=NOW, log_path=tmp_path / "log.jsonl", sleep=lambda s: None, **kw)


def work(snap, cfg):
    return {w.uuid: (w.kind, w.needs_color, w.needs_area) for w in select_work(snap, cfg, TODAY)}


def test_select_work_scope(cfg):
    snap = snapshot(
        [
            todo(uuid="open", area_id="A-W"),
            todo(uuid="inbox", start="Inbox"),
            todo(uuid="loose", tags=[Y]),
            todo(uuid="colored", tags=[Y], area_id="A-W"),
            todo(uuid="inproj", project_id="p9"),
            todo(uuid="blank", title="  "),
            todo(uuid="cancel", status="canceled", stop=datetime(2026, 9, 30, 9, 0)),
            todo(uuid="done_prev", status="completed", stop=datetime(2026, 9, 21, 9, 0), area_id="A-H"),
            todo(uuid="done_old", status="completed", stop=datetime(2026, 9, 20, 9, 0)),
            todo(uuid="done_loose", status="completed", start="Inbox", tags=[Y],
                 stop=datetime(2026, 9, 30, 9, 0)),
        ],
        projects=[project(uuid="p1"), project(uuid="p2", area_id="A-W")],
    )
    assert work(snap, cfg) == {
        "open": ("to-do", True, False),
        "inbox": ("to-do", True, False),
        "loose": ("to-do", False, True),
        "inproj": ("to-do", True, False),
        "done_prev": ("to-do", True, False),
        "done_loose": ("to-do", False, True),
        "p1": ("project", False, True),
    }


def test_no_work_skips_claude_and_records_ok(cfg, state, tmp_path):
    things = FakeThings([todo(tags=[Y], area_id="A-W")])
    clf = FakeClassifier()
    result = run(things, clf, state, cfg, tmp_path)
    assert result.requested == 0 and clf.batches == []
    assert state.failure_streak("categorize") == (0, None, None)


def test_batches_by_batch_size(cfg, state, tmp_path):
    things = FakeThings([todo(uuid=f"t{i}", area_id="A-W") for i in range(60)])
    clf = FakeClassifier()
    run(things, clf, state, cfg, tmp_path)
    assert [len(b) for b in clf.batches] == [25, 25, 10]


def test_applies_tag_and_area_names(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1")], projects=[project(uuid="p1")])
    result = run(things, FakeClassifier("green", "work"), state, cfg, tmp_path)
    assert ("add_tag", "t1", "🟢") in things.calls
    assert ("set_todo_area", "t1", "A-W") in things.calls
    assert ("set_project_area", "p1", "A-W") in things.calls
    assert [a.uuid for a in result.applied] == ["t1", "p1"] and result.unverified == []


def test_area_left_unset_when_model_unsure(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", tags=[Y])])
    result = run(things, FakeClassifier(area=None), state, cfg, tmp_path)
    assert things.calls == [] and result.applied == []


def test_classifier_error_records_failed_run_and_writes_nothing(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", area_id="A-W")])
    with pytest.raises(ClassifierError):
        run(things, FakeClassifier(error="Not logged in"), state, cfg, tmp_path)
    assert things.calls == []
    count, _, last = state.failure_streak("categorize")
    assert (count, last) == (1, "Not logged in")


def test_things_unavailable_records_failed_run_with_fda_hint(cfg, state, tmp_path):
    def read(since):
        raise ThingsUnavailable("Cannot read the Things database. ... grant Full Disk Access ...")
    with pytest.raises(ThingsUnavailable):
        run_categorize(read=read, writer=FakeThings(), classifier=FakeClassifier(), state=state, cfg=cfg,
                       now=NOW, log_path=tmp_path / "log.jsonl", sleep=lambda s: None)
    assert "Full Disk Access" in state.failure_streak("categorize")[2]


def test_write_error_skips_item_and_continues(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="bad", area_id="A-W"), todo(uuid="good", area_id="A-W")], fail_on={"bad"})
    result = run(things, FakeClassifier(), state, cfg, tmp_path)
    assert [a.uuid for a in result.applied] == ["good"]
    assert result.skipped == [("bad", "things:///update failed for bad (exit 1)")]


def test_unverified_writes_reported(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", area_id="A-W")], apply_writes=False)
    result = run(things, FakeClassifier(), state, cfg, tmp_path)
    assert result.unverified == ["t1"]


def test_log_line_per_applied(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", title="Play guitar", area_id="A-W")])
    run(things, FakeClassifier(), state, cfg, tmp_path)
    lines = (tmp_path / "log.jsonl").read_text().splitlines()
    entry = json.loads(lines[0])
    assert len(lines) == 1
    assert {k: entry[k] for k in ("uuid", "title", "color", "area", "reason", "model")} == {
        "uuid": "t1", "title": "Play guitar", "color": "green", "area": None, "reason": "r",
        "model": "sonnet"}
    assert entry["ts"] == NOW.isoformat(timespec="seconds")


def test_refuses_before_first_review(cfg, tmp_path):
    fresh = StateStore(tmp_path / "fresh.db")
    clf = FakeClassifier()
    with pytest.raises(NotReviewed):
        run(FakeThings([todo(area_id="A-W")]), clf, fresh, cfg, tmp_path)
    assert clf.batches == []


def test_lock_prevents_overlap(tmp_path):
    with run_lock(tmp_path / "c.lock"), pytest.raises(AlreadyRunning), run_lock(tmp_path / "c.lock"):
        pass
    with run_lock(tmp_path / "c.lock"):
        pass


def test_window_uses_previous_week_start(cfg):
    snap = snapshot([todo(uuid="d", status="completed", stop=datetime(2026, 9, 21, 0, 0), area_id="A-W")])
    assert "d" in work(snap, cfg)
    assert select_work(snap, cfg, date(2026, 10, 5)) == []


def test_verification_retries_while_things_catches_up(cfg, state, tmp_path):
    things = LaggyThings([todo(uuid="t1", area_id="A-W")], lag_reads=2)
    sleeps = []
    result = run_categorize(read=things.read, writer=things, classifier=FakeClassifier(), state=state,
                            cfg=cfg, now=NOW, log_path=tmp_path / "log.jsonl", sleep=sleeps.append)
    assert result.unverified == [] and len(sleeps) >= 2


def test_verification_gives_up_after_retries(cfg, state, tmp_path):
    things = LaggyThings([todo(uuid="t1", area_id="A-W")], lag_reads=100)
    result = run_categorize(read=things.read, writer=things, classifier=FakeClassifier(), state=state,
                            cfg=cfg, now=NOW, log_path=tmp_path / "log.jsonl", sleep=lambda s: None)
    assert result.unverified == ["t1"]


def test_area_left_unsure_is_not_asked_again_for_a_day(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", tags=[Y])])
    clf = FakeClassifier(area=None)
    run(things, clf, state, cfg, tmp_path)
    run(things, clf, state, cfg, tmp_path)
    assert clf.batches == [["t1"]]
    later = NOW + timedelta(hours=25)
    run_categorize(read=things.read, writer=things, classifier=clf, state=state, cfg=cfg, now=later,
                   log_path=tmp_path / "log.jsonl", sleep=lambda s: None)
    assert clf.batches == [["t1"], ["t1"]]


def test_setup_problem_stops_categorizing(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", area_id="A-W")])
    snap_without_green = snapshot(things.todos.values(), tag_names=frozenset({"🔴", "🟡"}))
    clf = FakeClassifier()
    with pytest.raises(SetupIncomplete, match="Missing Things tags"):
        run_categorize(read=lambda since: snap_without_green, writer=things, classifier=clf, state=state,
                       cfg=cfg, now=NOW, log_path=tmp_path / "log.jsonl", sleep=lambda s: None)
    assert clf.batches == [] and things.calls == []
    assert "Missing Things tags" in state.failure_streak("categorize")[2]


def test_unexpected_error_is_recorded_as_failed_run(cfg, state, tmp_path):
    class Boom(FakeClassifier):
        def classify(self, items):
            raise RuntimeError("kaboom")
    with pytest.raises(RuntimeError):
        run(FakeThings([todo(uuid="t1", area_id="A-W")]), Boom(), state, cfg, tmp_path)
    assert state.failure_streak("categorize")[2] == "RuntimeError: kaboom"
