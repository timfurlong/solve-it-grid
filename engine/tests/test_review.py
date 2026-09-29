import json
from datetime import datetime

import pytest
from factories import todo
from fakes import FakeClassifier, FakeThings

from solve_it_grid.config import load_config
from solve_it_grid.paths import repo_root
from solve_it_grid.review import apply_review, dry_run, read_review, render_eval, run_eval
from solve_it_grid.state import StateStore

NOW = datetime(2026, 10, 1, 10, 0).astimezone()
Y = "🟡"


@pytest.fixture
def cfg():
    return load_config(repo_root() / "config.example.toml")


@pytest.fixture
def state(tmp_path):
    return StateStore(tmp_path / "state.db")


def _dry(things, cfg, home, color="yellow"):
    return dry_run(read=things.read, classifier=FakeClassifier(color, "home"), cfg=cfg, now=NOW, home=home)


def _apply(things, state, cfg, home, path=None):
    return apply_review(path or home / "review.tsv", read=things.read, writer=things, state=state, cfg=cfg,
                        now=NOW, golden_path=home / "golden.jsonl", log_path=home / "log.jsonl",
                        sleep=lambda s: None)


def test_dry_run_writes_review_and_never_writes_things(cfg, tmp_path):
    things = FakeThings([todo(uuid="t1", title="Book dentist", area_id="A-H")])
    path, assignments, skipped = _dry(things, cfg, tmp_path)
    assert things.calls == [] and skipped == []
    lines = path.read_text().splitlines()
    assert lines[0] == "uuid\tkind\tneeds\ttitle\tcolor\tarea\treason"
    assert lines[1].split("\t")[:6] == ["t1", "to-do", "color", "Book dentist", "yellow", ""]
    payloads = [json.loads(x) for x in (tmp_path / "review.items.jsonl").read_text().splitlines()]
    assert payloads[0]["uuid"] == "t1"


def test_apply_review_uses_edited_color(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", title="Play guitar", area_id="A-H")])
    path, _, _ = _dry(things, cfg, tmp_path)
    path.write_text(path.read_text().replace("\tyellow\t", "\tgreen\t"))
    result = _apply(things, state, cfg, tmp_path)
    assert things.calls == [("add_tag", "t1", "🟢")]
    assert [a.color for a in result.applied] == ["green"] and result.unverified == []


def test_apply_review_skips_items_colored_since_dry_run(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", area_id="A-H")])
    _dry(things, cfg, tmp_path)
    things.add_tag("t1", Y)
    things.calls.clear()
    result = _apply(things, state, cfg, tmp_path)
    assert things.calls == [] and result.skipped == [("t1", "already handled")]


def test_apply_review_appends_golden_and_sets_meta(cfg, state, tmp_path):
    things = FakeThings([todo(uuid="t1", title="Renew registration", area_id="A-H")])
    _dry(things, cfg, tmp_path)
    _apply(things, state, cfg, tmp_path)
    golden = [json.loads(x) for x in (tmp_path / "golden.jsonl").read_text().splitlines()]
    assert golden == [{"item": golden[0]["item"], "color": "yellow", "area": None}]
    assert golden[0]["item"]["title"] == "Renew registration"
    assert state.get_meta("review_applied_at") == NOW.isoformat(timespec="seconds")


def test_read_review_reports_bad_line(tmp_path):
    path = tmp_path / "review.tsv"
    path.write_text("uuid\tkind\tneeds\ttitle\tcolor\tarea\treason\n"
                    "t1\tto-do\tcolor\tA\tyellow\t\tok\n"
                    "t2\tto-do\tcolor\tB\tpurple\t\t?\n")
    with pytest.raises(ValueError, match="line 3: invalid color 'purple'"):
        read_review(path)


def test_eval_agreement_math(tmp_path):
    golden = tmp_path / "golden.jsonl"
    rows = [("a", "green"), ("b", "green"), ("c", "green"), ("d", "yellow")]
    golden.write_text("".join(json.dumps({"item": {"uuid": u, "kind": "to-do", "title": u.upper(),
                                                   "needs": ["color"]}, "color": c, "area": None}) + "\n"
                              for u, c in rows))
    report = run_eval(FakeClassifier("green", None), golden, batch_size=25)
    assert (report.total, report.agree) == (4, 3)
    assert report.per_color == {"green": (3, 3), "yellow": (0, 1)}
    assert report.disagreements == [{"title": "D", "expected": "yellow", "got": "green", "reason": "r"}]
    assert "3/4" in render_eval(report)


def test_eval_uses_latest_golden_row_per_item(tmp_path):
    golden = tmp_path / "golden.jsonl"
    item = {"uuid": "a", "kind": "to-do", "title": "A", "needs": ["color"]}
    golden.write_text(json.dumps({"item": item, "color": "yellow", "area": None}) + "\n"
                      + json.dumps({"item": item, "color": "green", "area": None}) + "\n")
    assert run_eval(FakeClassifier("green", None), golden, batch_size=25).agree == 1
