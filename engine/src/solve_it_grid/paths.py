"""Filesystem locations: the per-user data dir and the repo checkout."""

import os
from pathlib import Path

_DEFAULT_HOME = Path.home() / "Library" / "Application Support" / "solve-it-grid"


def app_dir() -> Path:
    """Directory for all user data. `$SOLVE_IT_GRID_HOME` overrides the default."""
    path = Path(os.environ["SOLVE_IT_GRID_HOME"]) if os.environ.get("SOLVE_IT_GRID_HOME") else _DEFAULT_HOME
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_root() -> Path:
    """Root of the repo checkout (requires an editable install)."""
    return Path(__file__).resolve().parents[3]
