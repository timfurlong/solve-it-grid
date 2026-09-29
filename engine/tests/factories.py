"""Builders for model objects used across tests."""

from dataclasses import replace

from sig.model import Project, Snapshot, Todo

DEFAULT_TAGS = frozenset({"🔴 Red", "🟡 Yellow", "🟢 Green", "🔵 Blue", "⚪ Unscored"})
_BASE_TODO = Todo(
    uuid="t1", title="Task", notes="", status="incomplete", start="Anytime", start_date=None,
    deadline=None, stop=None, area_id=None, project_id=None, project_title=None,
    heading_title=None, tags=(), in_today=False,
)


def todo(**overrides) -> Todo:
    if "tags" in overrides:
        overrides["tags"] = tuple(overrides["tags"])
    return replace(_BASE_TODO, **overrides)


def project(**overrides) -> Project:
    base = Project(uuid="p1", title="Project", notes="", area_id=None, status="incomplete")
    return replace(base, **overrides)


def snapshot(todos=(), projects=(), **overrides) -> Snapshot:
    fields = dict(
        todos=tuple(todos), projects=tuple(projects), area_ids={"Work": "A-W", "Home": "A-H"},
        tag_names=DEFAULT_TAGS, inbox_count=0, token_present=True,
    )
    fields.update(overrides)
    return Snapshot(**fields)
