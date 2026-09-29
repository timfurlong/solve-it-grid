import pytest


@pytest.fixture(autouse=True)
def sig_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLVE_IT_GRID_HOME", str(tmp_path))
    return tmp_path
