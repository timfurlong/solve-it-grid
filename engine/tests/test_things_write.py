import subprocess
from unittest.mock import Mock

import pytest

from solve_it_grid.things_write import ThingsWriteError, UrlSchemeWriter, ensure_tags


def fake_url(uuid=None, command="show", **params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"things:///{command}?id={uuid}&{query}&auth-token=SECRET"


def test_add_tag_opens_update_url_in_background():
    run = Mock()
    UrlSchemeWriter(run=run, url=fake_url).add_tag("T1", "X")
    argv = run.call_args.args[0]
    assert argv == ["/usr/bin/open", "-g", "things:///update?id=T1&add-tags=X&auth-token=SECRET"]
    assert run.call_args.kwargs["check"] is True


def test_todo_area_uses_list_id():
    run = Mock()
    UrlSchemeWriter(run=run, url=fake_url).set_todo_area("T1", "A-W")
    assert run.call_args.args[0][2] == "things:///update?id=T1&list-id=A-W&auth-token=SECRET"


def test_project_area_uses_update_project():
    run = Mock()
    UrlSchemeWriter(run=run, url=fake_url).set_project_area("P1", "A-H")
    assert run.call_args.args[0][2] == "things:///update-project?id=P1&area-id=A-H&auth-token=SECRET"


def test_writer_errors_never_include_token():
    def run(argv, **kw):
        raise subprocess.CalledProcessError(1, argv)
    with pytest.raises(ThingsWriteError) as info:
        UrlSchemeWriter(run=run, url=fake_url).add_tag("T1", "X")
    assert "SECRET" not in str(info.value) and "update" in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_missing_token_raises_write_error():
    def no_token(uuid=None, command="show", **params):
        raise ValueError("Things URL scheme authentication token could not be read")
    with pytest.raises(ThingsWriteError, match="Things URLs are off"):
        UrlSchemeWriter(run=Mock(), url=no_token).add_tag("T1", "X")


def test_ensure_tags_escapes_quotes_and_parses_created():
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout='A "b"\n🟢\n', stderr=""))
    created = ensure_tags(['A "b"', "🟢"], run=run)
    argv = run.call_args.args[0]
    assert argv[:2] == ["/usr/bin/osascript", "-e"]
    assert 'exists tag "A \\"b\\""' in argv[2]
    assert created == ['A "b"', "🟢"]


def test_ensure_tags_nothing_created():
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="\n", stderr=""))
    assert ensure_tags(["X"], run=run) == []
