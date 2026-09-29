from datetime import date, datetime, timedelta
from unittest.mock import Mock

import pytest
import things

from sig import things_read
from sig.things_read import ThingsUnavailable, read_snapshot, to_todo


def _rec(**kw):
    base = {"uuid": "t", "type": "to-do", "title": "x", "status": "incomplete", "start": "Anytime",
            "notes": "", "start_date": None, "deadline": None, "stop_date": None}
    base.update(kw)
    return base


def test_area_resolves_through_heading_project():
    rec = _rec(heading="H1", heading_title="Tasks")
    t = to_todo(rec, projects={"P1": {"uuid": "P1", "title": "Trip", "area": "A-H"}},
                headings={"H1": {"uuid": "H1", "project": "P1"}}, today_ids=set())
    assert (t.area_id, t.project_id, t.project_title) == ("A-H", "P1", "Trip")
    assert t.heading_title == "Tasks"


def test_area_resolves_through_project():
    rec = _rec(project="P1", project_title="Trip")
    t = to_todo(rec, projects={"P1": {"uuid": "P1", "title": "Trip", "area": "A-W"}},
                headings={}, today_ids=set())
    assert (t.area_id, t.project_id) == ("A-W", "P1")


def test_own_area_wins_and_stop_date_parsed():
    rec = _rec(area="A-W", project="P1", status="completed", stop_date="2026-09-21 09:23:07",
               start_date="2026-09-20", deadline="2026-09-30")
    t = to_todo(rec, projects={"P1": {"uuid": "P1", "title": "Trip", "area": "A-H"}},
                headings={}, today_ids={"t"})
    assert t.area_id == "A-W"
    assert t.stop == datetime(2026, 9, 21, 9, 23, 7)
    assert (t.start_date, t.deadline) == (date(2026, 9, 20), date(2026, 9, 30))
    assert t.in_today


def test_missing_tags_key_means_no_tags():
    t = to_todo(_rec(), projects={}, headings={}, today_ids=set())
    assert t.tags == () and t.area_id is None and t.project_id is None


def test_read_snapshot_assembles_from_things_api(monkeypatch):
    def tasks(type, status, **kw):
        if type == "to-do" and status == "incomplete":
            return [_rec(uuid="open1", area="A-W", tags=["🟡 Yellow"])]
        if type == "to-do" and status == "completed":
            assert kw == {"stop_date": ">=2026-09-21"}
            return [_rec(uuid="done1", status="completed", stop_date="2026-09-22 10:00:00")]
        if type == "project":
            return [{"uuid": "P1", "title": "Open", "notes": "", "status": "incomplete", "area": None},
                    {"uuid": "P2", "title": "Done", "notes": "", "status": "completed", "area": "A-H"}]
        if type == "heading":
            return []
        raise AssertionError((type, status, kw))

    monkeypatch.setattr(things, "tasks", tasks)
    monkeypatch.setattr(things, "areas", lambda: [{"uuid": "A-W", "title": "Work"}])
    monkeypatch.setattr(things, "tags", lambda: [{"title": "🟡 Yellow"}])
    monkeypatch.setattr(things, "today", lambda: [{"uuid": "open1"}])
    monkeypatch.setattr(things, "inbox", lambda: [{"uuid": "i1"}, {"uuid": "i2"}])
    monkeypatch.setattr(things, "token", lambda: "tok")
    s = read_snapshot(date(2026, 9, 21))
    assert [t.uuid for t in s.todos] == ["open1", "done1"]
    assert s.todos[0].in_today and s.todos[0].tags == ("🟡 Yellow",)
    assert [p.uuid for p in s.projects] == ["P1"]
    assert s.area_ids == {"Work": "A-W"}
    assert s.tag_names == frozenset({"🟡 Yellow"})
    assert (s.inbox_count, s.token_present) == (2, True)


def test_read_snapshot_wraps_permission_error(monkeypatch):
    monkeypatch.setattr(things, "tasks", Mock(side_effect=PermissionError("Operation not permitted")))
    with pytest.raises(ThingsUnavailable, match="Full Disk Access"):
        read_snapshot(date(2026, 9, 21))


def test_read_snapshot_wraps_sqlite_error(monkeypatch):
    import sqlite3
    monkeypatch.setattr(things, "tasks", Mock(side_effect=sqlite3.OperationalError("unable to open")))
    with pytest.raises(ThingsUnavailable, match="unable to open"):
        read_snapshot(date(2026, 9, 21))


@pytest.mark.live
def test_read_snapshot_live():
    s = read_snapshot(date.today() - timedelta(days=14))
    assert s.token_present and s.area_ids
    assert things_read is not None
