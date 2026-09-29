"""Build the classification prompt, request and output schema."""

import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sig.model import Project, Todo, list_name

NOTES_LIMIT = 300
# Blue (passive downtime) almost never appears on a to-do list, so the model never proposes it.
CLASSIFIER_COLORS = ("red", "yellow", "green", "unscored")

OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "uuid": {"type": "string"},
                    "color": {"type": ["string", "null"], "enum": [*CLASSIFIER_COLORS, None]},
                    "area": {"type": ["string", "null"], "enum": ["work", "home", None]},
                    "reason": {"type": "string"},
                },
                "required": ["uuid", "color", "area", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_INSTRUCTIONS = (
    "Classify every item in the user's JSON request. Answer once per item, using its exact uuid. "
    "Follow the rubric above."
)


@dataclass(frozen=True)
class WorkItem:
    uuid: str
    kind: Literal["to-do", "project"]
    needs_color: bool
    needs_area: bool
    payload: dict


def _needs(needs_color: bool, needs_area: bool) -> list[str]:
    return [name for name, on in (("color", needs_color), ("area", needs_area)) if on]


def work_item_from_todo(t: Todo, area_titles: dict[str, str], needs_color: bool, needs_area: bool,
                        today: date) -> WorkItem:
    payload = {
        "uuid": t.uuid, "kind": "to-do", "title": t.title, "notes": t.notes[:NOTES_LIMIT],
        "project": t.project_title, "heading": t.heading_title,
        "area": area_titles.get(t.area_id) if t.area_id else None,
        "list": list_name(t, today),
        "scheduled": t.start_date.isoformat() if t.start_date else None,
        "deadline": t.deadline.isoformat() if t.deadline else None,
        "status": t.status, "needs": _needs(needs_color, needs_area),
    }
    return WorkItem(t.uuid, "to-do", needs_color, needs_area, payload)


def work_item_from_project(p: Project) -> WorkItem:
    payload = {
        "uuid": p.uuid, "kind": "project", "title": p.title, "notes": p.notes[:NOTES_LIMIT],
        "project": None, "heading": None, "area": None, "list": None, "scheduled": None, "deadline": None,
        "status": p.status, "needs": ["area"],
    }
    return WorkItem(p.uuid, "project", False, True, payload)


def build_system_prompt(rubric: str, local: str | None) -> str:
    parts = [rubric.rstrip()]
    if local and local.strip():
        parts.append("## My examples\n\n" + local.strip())
    parts.append(_INSTRUCTIONS)
    return "\n\n".join(parts)


def build_user_message(items: list[WorkItem], today: date) -> str:
    return json.dumps({"today": today.isoformat(), "items": [i.payload for i in items]},
                      ensure_ascii=False)
