"""Read a Snapshot from the local Things database via things.py."""

import sqlite3
from datetime import date, datetime

import things

from solve_it_grid.model import Project, Snapshot, Todo

_FDA_HINT = ("Cannot read the Things database. If this runs from launchd, grant Full Disk Access "
             "to the Python that runs solve-it-grid (System Settings > Privacy & Security).")


class ThingsUnavailable(Exception):
    pass


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def to_todo(record: dict, projects: dict[str, dict], headings: dict[str, dict],
            today_ids: set[str]) -> Todo:
    project_id = record.get("project")
    if not project_id and record.get("heading"):
        project_id = headings.get(record["heading"], {}).get("project")
    project = projects.get(project_id) if project_id else None
    area_id = record.get("area") or (project or {}).get("area")
    stop = record.get("stop_date")
    return Todo(
        uuid=record["uuid"],
        title=record.get("title") or "",
        notes=record.get("notes") or "",
        status=record["status"],
        start=record.get("start") or "",
        start_date=_date(record.get("start_date")),
        deadline=_date(record.get("deadline")),
        stop=datetime.fromisoformat(stop) if stop else None,
        area_id=area_id,
        project_id=project_id,
        project_title=(project or {}).get("title") or record.get("project_title"),
        heading_title=record.get("heading_title"),
        tags=tuple(record.get("tags") or ()),
        in_today=record["uuid"] in today_ids,
    )


def read_snapshot(completed_since: date) -> Snapshot:
    try:
        open_todos = things.tasks(type="to-do", status="incomplete")
        done_todos = things.tasks(type="to-do", status="completed",
                                  stop_date=f">={completed_since.isoformat()}")
        all_projects = things.tasks(type="project", status=None)
        headings = things.tasks(type="heading", status=None)
        areas = things.areas()
        tags = things.tags()
        today_ids = {t["uuid"] for t in things.today()}
        inbox_count = len(things.inbox())
        token = things.token()
    except (sqlite3.Error, PermissionError) as exc:
        raise ThingsUnavailable(f"{_FDA_HINT} ({exc})") from exc

    projects_by_id = {p["uuid"]: p for p in all_projects}
    headings_by_id = {h["uuid"]: h for h in headings}
    todos = tuple(to_todo(r, projects_by_id, headings_by_id, today_ids)
                  for r in [*open_todos, *done_todos])
    return Snapshot(
        todos=todos,
        projects=tuple(
            Project(uuid=p["uuid"], title=p.get("title") or "", notes=p.get("notes") or "",
                    area_id=p.get("area"), status=p["status"])
            for p in all_projects if p["status"] == "incomplete"
        ),
        area_ids={a["title"]: a["uuid"] for a in areas},
        tag_names=frozenset(t["title"] for t in tags),
        inbox_count=inbox_count,
        token_present=bool(token),
    )
