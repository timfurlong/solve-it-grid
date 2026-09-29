"""Classify work items with a headless `claude -p` call."""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from solve_it_grid.config import Color
from solve_it_grid.prompt import CLASSIFIER_COLORS, OUTPUT_SCHEMA, WorkItem, build_user_message

AREAS = ("work", "home")
# Extended thinking makes a 10-item batch take ~55 s instead of ~10 s, with no need for it here.
_ENV = {"MAX_THINKING_TOKENS": "0"}


class ClassifierError(Exception):
    pass


@dataclass(frozen=True)
class Assignment:
    uuid: str
    color: Color | None
    area: Literal["work", "home"] | None
    reason: str


class ClaudeClassifier:
    def __init__(self, claude_path: Path, model: str, system_prompt: str, timeout: int, cwd: Path,
                 run=subprocess.run):
        self._claude = claude_path
        self._model = model
        self._system_prompt = system_prompt
        self._timeout = timeout
        self._cwd = cwd
        self._run = run

    def _argv(self) -> list[str]:
        # --bare is deliberately absent: it disables subscription (OAuth) login.
        return [
            str(self._claude), "-p", "--model", self._model, "--tools", "", "--strict-mcp-config",
            "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
            "--output-format", "json", "--json-schema", json.dumps(OUTPUT_SCHEMA),
            "--system-prompt", self._system_prompt,
        ]

    def classify(self, items: list[WorkItem]) -> list[dict]:
        try:
            proc = self._run(self._argv(), input=build_user_message(items, date.today()),
                             capture_output=True, text=True, timeout=self._timeout, cwd=self._cwd,
                             env={**os.environ, **_ENV})
        except subprocess.TimeoutExpired:
            raise ClassifierError(f"claude timed out after {self._timeout}s") from None
        except OSError as exc:
            raise ClassifierError(f"cannot run claude at {self._claude}: {exc}") from None
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            if proc.returncode != 0:
                tail = " ".join(proc.stderr.strip().splitlines()[-2:])
                raise ClassifierError(f"claude exited {proc.returncode}: {tail}") from None
            raise ClassifierError("unparseable claude output") from None
        if data.get("is_error"):
            raise ClassifierError(str(data.get("result") or "claude reported an error"))
        output = data.get("structured_output")
        if not isinstance(output, dict) or not isinstance(output.get("items"), list):
            raise ClassifierError("claude returned no structured output")
        return output["items"]


def validate(items: list[WorkItem], raw: list[dict]) -> tuple[list[Assignment], list[tuple[str, str]]]:
    requested = {i.uuid: i for i in items}
    valid: list[Assignment] = []
    skipped: list[tuple[str, str]] = []
    answered: set[str] = set()
    for answer in raw:
        uuid = answer.get("uuid")
        if uuid not in requested:
            skipped.append((str(uuid), "not requested"))
            continue
        if uuid in answered:
            continue
        answered.add(uuid)
        color, area = answer.get("color"), answer.get("area")
        if color is not None and color not in CLASSIFIER_COLORS:
            skipped.append((uuid, "invalid color"))
        elif area is not None and area not in AREAS:
            skipped.append((uuid, "invalid area"))
        elif requested[uuid].needs_color and color is None:
            skipped.append((uuid, "missing color"))
        else:
            valid.append(Assignment(uuid, color, area, str(answer.get("reason") or "")))
    skipped += [(uuid, "no answer") for uuid in requested if uuid not in answered]
    return valid, skipped
