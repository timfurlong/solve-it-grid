import json
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import Mock

import pytest

from sig.classifier import Assignment, ClassifierError, ClaudeClassifier, validate
from sig.prompt import WorkItem


def item(uuid="t1", needs_color=True, needs_area=False, kind="to-do"):
    needs = [n for n, on in (("color", needs_color), ("area", needs_area)) if on]
    return WorkItem(uuid, kind, needs_color, needs_area, {"uuid": uuid, "kind": kind, "needs": needs})


def classifier(run, tmp_path):
    return ClaudeClassifier(Path("/c"), "claude-haiku-4-5-20251001", "SYS", 60, tmp_path, run=run)


def ok(items):
    body = {"is_error": False, "structured_output": {"items": items}}
    return CompletedProcess([], 0, stdout=json.dumps(body), stderr="")


def test_argv_is_pinned(tmp_path):
    run = Mock(return_value=ok([]))
    classifier(run, tmp_path).classify([item()])
    argv = run.call_args.args[0]
    assert argv[:14] == ["/c", "-p", "--model", "claude-haiku-4-5-20251001", "--tools", "",
                         "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
                         "--no-session-persistence", "--output-format", "json", "--json-schema"]
    assert argv[-2:] == ["--system-prompt", "SYS"] and "--bare" not in argv
    kwargs = run.call_args.kwargs
    assert json.loads(kwargs["input"])["items"][0]["uuid"] == "t1"
    assert kwargs["timeout"] == 60 and kwargs["cwd"] == tmp_path and kwargs["text"] is True


def test_returns_raw_items(tmp_path):
    raw = [{"uuid": "t1", "color": "green", "area": None, "reason": "fun"}]
    assert classifier(Mock(return_value=ok(raw)), tmp_path).classify([item()]) == raw


def test_is_error_raises(tmp_path):
    out = CompletedProcess([], 1, stdout=json.dumps({"is_error": True, "result": "Not logged in"}), stderr="")
    with pytest.raises(ClassifierError, match="Not logged in"):
        classifier(Mock(return_value=out), tmp_path).classify([item()])


def test_timeout_raises(tmp_path):
    run = Mock(side_effect=subprocess.TimeoutExpired(["/c"], 60))
    with pytest.raises(ClassifierError, match="claude timed out after 60s"):
        classifier(run, tmp_path).classify([item()])


def test_nonzero_exit_raises_with_stderr_tail(tmp_path):
    out = CompletedProcess([], 2, stdout="", stderr="line1\nline2\nfatal: no credentials\n")
    with pytest.raises(ClassifierError, match="no credentials"):
        classifier(Mock(return_value=out), tmp_path).classify([item()])


def test_unparseable_output_raises(tmp_path):
    out = CompletedProcess([], 0, stdout="not json", stderr="")
    with pytest.raises(ClassifierError, match="unparseable"):
        classifier(Mock(return_value=out), tmp_path).classify([item()])


def test_missing_structured_output_raises(tmp_path):
    out = CompletedProcess([], 0, stdout=json.dumps({"is_error": False, "result": "hi"}), stderr="")
    with pytest.raises(ClassifierError, match="structured output"):
        classifier(Mock(return_value=out), tmp_path).classify([item()])


def test_validate_filters_bad_answers():
    items = [item("t1"), item("t2", needs_area=True), item("t3")]
    raw = [
        {"uuid": "t1", "color": "yellow", "area": None, "reason": "chore"},
        {"uuid": "t1", "color": "green", "area": None, "reason": "dup"},
        {"uuid": "t2", "color": "purple", "area": "work", "reason": "?"},
        {"uuid": "t9", "color": "red", "area": None, "reason": "?"},
    ]
    valid, skipped = validate(items, raw)
    assert valid == [Assignment("t1", "yellow", None, "chore")]
    assert dict(skipped) == {"t2": "invalid color", "t9": "not requested", "t3": "no answer"}


def test_validate_requires_color_when_needed():
    valid, skipped = validate([item("t1")], [{"uuid": "t1", "color": None, "area": None, "reason": ""}])
    assert valid == [] and skipped == [("t1", "missing color")]


def test_validate_rejects_bad_area_and_allows_project_without_color():
    items = [item("t1", needs_area=True), item("p1", needs_color=False, needs_area=True, kind="project")]
    raw = [{"uuid": "t1", "color": "yellow", "area": "office", "reason": ""},
           {"uuid": "p1", "color": None, "area": "home", "reason": "house"}]
    valid, skipped = validate(items, raw)
    assert valid == [Assignment("p1", None, "home", "house")]
    assert skipped == [("t1", "invalid area")]


def test_thinking_disabled_for_speed(tmp_path, monkeypatch):
    monkeypatch.setenv("KEEP_ME", "1")
    run = Mock(return_value=ok([]))
    classifier(run, tmp_path).classify([item()])
    env = run.call_args.kwargs["env"]
    assert env["MAX_THINKING_TOKENS"] == "0" and env["KEEP_ME"] == "1"


def test_validate_rejects_blue():
    valid, skipped = validate([item("t1")], [{"uuid": "t1", "color": "blue", "area": None, "reason": ""}])
    assert valid == [] and skipped == [("t1", "invalid color")]
