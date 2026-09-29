import json
from datetime import date

from factories import project, todo

from sig.prompt import (
    OUTPUT_SCHEMA,
    build_system_prompt,
    build_user_message,
    work_item_from_project,
    work_item_from_todo,
)

TODAY = date(2026, 9, 29)


def test_todo_payload_and_notes_trimmed_to_300():
    t = todo(uuid="t1", title="Book dentist", notes="x" * 500, area_id="A-H", project_title="Health",
             heading_title="Todo", deadline=date(2026, 10, 3), start="Someday", start_date=date(2026, 10, 1))
    item = work_item_from_todo(t, {"A-H": "Home"}, needs_color=True, needs_area=False, today=TODAY)
    assert item.kind == "to-do" and item.needs_color and not item.needs_area
    assert item.payload == {
        "uuid": "t1", "kind": "to-do", "title": "Book dentist", "notes": "x" * 300,
        "project": "Health", "heading": "Todo", "area": "Home", "list": "Upcoming",
        "scheduled": "2026-10-01", "deadline": "2026-10-03", "status": "incomplete", "needs": ["color"],
    }


def test_project_payload_needs_area_only():
    item = work_item_from_project(project(uuid="p1", title="Garage", notes="clean it"))
    assert (item.kind, item.needs_color, item.needs_area) == ("project", False, True)
    assert item.payload["needs"] == ["area"] and item.payload["kind"] == "project"


def test_user_message_is_items_json():
    item = work_item_from_todo(todo(uuid="t1"), {}, needs_color=True, needs_area=True, today=TODAY)
    msg = json.loads(build_user_message([item], today=date(2026, 10, 1)))
    assert msg == {"today": "2026-10-01", "items": [item.payload]}
    assert msg["items"][0]["needs"] == ["color", "area"]


def test_system_prompt_appends_local_examples():
    assert "My examples" not in build_system_prompt("RUBRIC", None)
    prompt = build_system_prompt("RUBRIC", "- Play guitar → green")
    assert prompt.startswith("RUBRIC") and "My examples" in prompt and "Play guitar" in prompt


def test_output_schema_enums():
    item = OUTPUT_SCHEMA["properties"]["items"]["items"]
    assert item["required"] == ["uuid", "color", "area", "reason"]
    assert item["properties"]["color"]["enum"] == ["red", "yellow", "green", "unscored", None]
    assert item["properties"]["area"]["enum"] == ["work", "home", None]
