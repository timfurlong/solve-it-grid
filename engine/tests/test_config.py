from datetime import time

import pytest

from solve_it_grid.config import load_config
from solve_it_grid.paths import app_dir, repo_root


def test_loads_example_config():
    cfg = load_config(repo_root() / "config.example.toml")
    assert [g.id for g in cfg.goals] == ["yellow-work", "yellow-home", "green"]
    assert cfg.tags == {"red": "🔴", "yellow": "🟡", "green": "🟢", "blue": "🔵", "unscored": "⚪"}
    assert cfg.checkin_time == time(9, 0)
    assert cfg.start_week is None and cfg.rubric_path is None
    assert cfg.claude_path is None
    assert cfg.areas == {"work": "Work", "home": "Home"}
    assert cfg.goals[2].target == 2 and cfg.goals[2].area == "any"
    assert (cfg.model, cfg.batch_size, cfg.timeout_seconds, cfg.failure_threshold) == (
        "sonnet", 25, 60, 3)


def test_app_dir_honors_sig_home(tmp_path):
    assert app_dir() == tmp_path


def test_rejects_unknown_goal_color(tmp_path):
    text = (repo_root() / "config.example.toml").read_text().replace(
        'color = "green"', 'color = "purple"')
    path = tmp_path / "config.toml"
    path.write_text(text)
    with pytest.raises(ValueError, match="green"):
        load_config(path)
