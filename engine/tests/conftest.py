import pytest


@pytest.fixture(autouse=True)
def sig_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SIG_HOME", str(tmp_path))
    return tmp_path
