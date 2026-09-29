import json
import shutil
from datetime import date, datetime

import pytest
from factories import snapshot

from sig import cli
from sig.paths import app_dir, repo_root
from sig.state import StateStore
from sig.things_read import ThingsUnavailable


@pytest.fixture
def configured():
    shutil.copy(repo_root() / "config.example.toml", app_dir() / "config.toml")


def test_cli_requires_setup(capsys):
    assert cli.main(["status"]) == 2
    assert "Run sig setup first." in capsys.readouterr().err


def test_cli_status_json(configured, monkeypatch, capsys):
    monkeypatch.setattr(cli, "read_snapshot", lambda since: snapshot())
    assert cli.main(["status", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["units"]) == 4


def test_cli_status_text(configured, monkeypatch, capsys):
    monkeypatch.setattr(cli, "read_snapshot", lambda since: snapshot())
    assert cli.main(["status"]) == 0
    assert "Work yellow" in capsys.readouterr().out


def test_cli_status_things_unavailable_exits_1(configured, monkeypatch, capsys):
    def boom(since):
        raise ThingsUnavailable("grant Full Disk Access")
    monkeypatch.setattr(cli, "read_snapshot", boom)
    assert cli.main(["status", "--json"]) == 1
    assert "grant Full Disk Access" in capsys.readouterr().err


def test_cli_chip_ack_all(configured, capsys):
    store = StateStore(app_dir() / "state.db")
    now = datetime(2026, 10, 1, 10, 0).astimezone()
    store.award_chip(date(2026, 9, 28), "yellow-work", "yellow", now)
    store.award_chip(date(2026, 9, 28), "green-1", "green", now)
    assert cli.main(["chip", "ack", "all"]) == 0
    assert StateStore(app_dir() / "state.db").pending_chips() == []
    assert "2" in capsys.readouterr().out


def test_cli_chip_ack_by_id(configured):
    store = StateStore(app_dir() / "state.db")
    chip = store.award_chip(date(2026, 9, 28), "green-1", "green", datetime(2026, 10, 1).astimezone())
    assert cli.main(["chip", "ack", str(chip.id)]) == 0
    assert StateStore(app_dir() / "state.db").total_earned() == 1


def test_cli_checkin_done_and_tick(configured):
    assert cli.main(["checkin", "done"]) == 0
    assert cli.main(["checkin", "tick", "someday-review"]) == 0
    store = StateStore(app_dir() / "state.db")
    today = datetime.now().astimezone().date()
    assert store.checkin_done(today) and store.ticks(today) == {"someday-review"}


def test_cli_checkin_tick_rejects_auto_steps(configured, capsys):
    assert cli.main(["checkin", "tick", "inbox"]) == 2
    assert "someday-review" in capsys.readouterr().err


def test_cli_setup_prints_messages_and_setup_errors(monkeypatch, capsys):
    calls = {}

    def fake_setup(home, repo, now, *, ensure_tags_fn, install_agent):
        calls["install_agent"] = install_agent
        shutil.copy(repo_root() / "config.example.toml", home / "config.toml")
        return ["Wrote config.toml"]

    monkeypatch.setattr(cli, "run_setup", fake_setup)
    monkeypatch.setattr(cli, "read_snapshot", lambda since: snapshot(area_ids={"Home": "A-H"}))
    assert cli.main(["setup", "--no-agent"]) == 0
    out = capsys.readouterr().out
    assert calls == {"install_agent": False}
    assert "Wrote config.toml" in out and "Things area 'Work' not found" in out


def test_cli_categorize_before_review_exits_0(configured, capsys):
    assert cli.main(["categorize"]) == 0
    assert "First review pending" in capsys.readouterr().out


def test_cli_eval_without_golden_exits_2(configured, capsys):
    assert cli.main(["eval"]) == 2
    assert "No golden set yet" in capsys.readouterr().err


def test_cli_dry_run_and_apply_are_exclusive(configured):
    with pytest.raises(SystemExit):
        cli.main(["categorize", "--dry-run", "--apply-review"])


def test_cli_checkin_tick_accepts_review_affirmations(configured):
    assert cli.main(["checkin", "tick", "colors-reviewed"]) == 0
    assert cli.main(["checkin", "tick", "today-reviewed"]) == 0
