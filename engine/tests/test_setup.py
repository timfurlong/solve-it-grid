from datetime import datetime
from unittest.mock import Mock

import pytest

from solve_it_grid.config import load_config
from solve_it_grid.paths import repo_root
from solve_it_grid.setup_cmd import LABEL, run_setup

NOW = datetime(2026, 10, 1, 10, 0).astimezone()


@pytest.fixture
def ensure():
    return Mock(return_value=["🟢"])


def _setup(tmp_path, ensure, install_agent=False, run=None):
    return run_setup(tmp_path / "home", repo_root(), NOW, ensure_tags_fn=ensure,
                     install_agent=install_agent, run=run or Mock(),
                     which=lambda name: f"/bin/{name}", agents_dir=tmp_path / "agents")


def test_setup_writes_config_once(tmp_path, ensure):
    (tmp_path / "home").mkdir()
    msgs = _setup(tmp_path, ensure)
    cfg = load_config(tmp_path / "home" / "config.toml")
    assert str(cfg.start_week) == "2026-09-28"
    assert cfg.rubric_path == repo_root() / "rubric.md"
    assert str(cfg.claude_path) == "/bin/claude"
    assert any("Created tags: 🟢" in m for m in msgs)
    ensure.assert_called_once_with(list(cfg.tags.values()))

    edited = (tmp_path / "home" / "config.toml").read_text().replace('work = "Work"', 'work = "Job"')
    (tmp_path / "home" / "config.toml").write_text(edited)
    _setup(tmp_path, ensure)
    assert load_config(tmp_path / "home" / "config.toml").areas["work"] == "Job"


def test_setup_renders_plist_and_bootstraps(tmp_path, ensure):
    (tmp_path / "home").mkdir()
    run = Mock()
    _setup(tmp_path, ensure, install_agent=True, run=run)
    plist = (tmp_path / "agents" / f"{LABEL}.plist").read_text()
    assert "<string>/bin/solve-it-grid</string>" in plist and "<string>categorize</string>" in plist
    assert str(tmp_path / "home" / "categorize.err.log") in plist
    assert "__" not in plist
    calls = [c.args[0] for c in run.call_args_list]
    assert calls[0][:2] == ["launchctl", "bootout"] and run.call_args_list[0].kwargs["check"] is False
    assert calls[1][:2] == ["launchctl", "bootstrap"] and calls[1][-1].endswith(f"{LABEL}.plist")


def test_setup_no_agent_skips_launchctl(tmp_path, ensure):
    (tmp_path / "home").mkdir()
    run = Mock()
    _setup(tmp_path, ensure, install_agent=False, run=run)
    run.assert_not_called()
    assert not (tmp_path / "agents").exists()
