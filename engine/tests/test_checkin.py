from datetime import date, datetime

import pytest
from factories import project, snapshot, todo

from solve_it_grid.checkin import evaluate_checkin, is_workday, show_url
from solve_it_grid.config import load_config
from solve_it_grid.paths import repo_root

R, Y, G = "🔴", "🟡", "🟢"
THU_10 = datetime(2026, 10, 1, 10, 0).astimezone()


@pytest.fixture
def cfg():
    return load_config(repo_root() / "config.example.toml")


def steps(checkin):
    return {s.id: s for s in checkin.steps}


def test_workdays():
    assert is_workday(date(2026, 11, 25), "US")
    assert not is_workday(date(2026, 11, 26), "US")  # Thanksgiving
    assert not is_workday(date(2026, 10, 3), "US")  # Saturday


def test_due_from_checkin_time_until_done(cfg):
    snap = snapshot()
    assert not evaluate_checkin(snap, cfg, datetime(2026, 10, 1, 8, 59).astimezone(), False, set()).due
    c = evaluate_checkin(snap, cfg, datetime(2026, 10, 1, 9, 0).astimezone(), False, set())
    assert c.workday and c.due and not c.done
    done = evaluate_checkin(snap, cfg, THU_10, True, set())
    assert done.done and not done.due


def test_not_due_on_holiday(cfg):
    c = evaluate_checkin(snapshot(), cfg, datetime(2026, 11, 26, 10, 0).astimezone(), False, set())
    assert not c.workday and not c.due


def test_base_step_order_and_inbox(cfg):
    c = evaluate_checkin(snapshot(inbox_count=2), cfg, THU_10, False, set())
    assert [s.id for s in c.steps] == ["inbox", "red", "yellow", "green", "today-reviewed", "colors-reviewed"]
    assert not steps(c)["inbox"].done
    assert steps(c)["inbox"].links[0].url == "things:///show?id=inbox"
    assert steps(evaluate_checkin(snapshot(), cfg, THU_10, False, set()))["inbox"].done


def test_red_step_done_when_no_open_reds(cfg):
    assert steps(evaluate_checkin(snapshot(), cfg, THU_10, False, set()))["red"].done
    open_red = snapshot([todo(tags=[R])])
    assert not steps(evaluate_checkin(open_red, cfg, THU_10, False, set()))["red"].done
    red_today = snapshot([todo(tags=[R], in_today=True)])
    assert steps(evaluate_checkin(red_today, cfg, THU_10, False, set()))["red"].done


def test_color_steps_need_item_in_today(cfg):
    snap = snapshot([todo(uuid="y", tags=[Y], in_today=True), todo(uuid="g", tags=[G])])
    s = steps(evaluate_checkin(snap, cfg, THU_10, False, set()))
    assert s["yellow"].done and not s["green"].done
    assert s["green"].links[0].url == show_url(query=G)


def test_area_step_excludes_inbox_and_lists_items(cfg):
    snap = snapshot(
        [todo(uuid="a", title="Loose", start="Anytime"), todo(uuid="i", title="Inboxed", start="Inbox"),
         todo(uuid="p", title="In project", project_id="p1"), todo(uuid="w", area_id="A-W")],
        projects=[project(uuid="p2", title="Arealess project")],
    )
    s = steps(evaluate_checkin(snap, cfg, THU_10, False, set()))["areas"]
    assert s.label == "Give 2 items an area" and not s.done
    assert [(link.label, link.url) for link in s.links] == [
        ("Loose", "things:///show?id=a"), ("Arealess project", "things:///show?id=p2")]


def test_no_area_step_when_nothing_needs_area(cfg):
    c = evaluate_checkin(snapshot([todo(area_id="A-W")]), cfg, THU_10, False, set())
    assert "areas" not in steps(c)


def test_fix_step_for_empty_title_and_multi_color(cfg):
    snap = snapshot([todo(uuid="e", title="  ", area_id="A-W"),
                     todo(uuid="m", title="Both", tags=[Y, G], area_id="A-W")])
    s = steps(evaluate_checkin(snap, cfg, THU_10, False, set()))["fix"]
    assert s.label == "Fix 2 items"
    assert [link.url for link in s.links] == ["things:///show?id=e", "things:///show?id=m"]


def test_someday_review_only_on_monday_and_tickable(cfg):
    monday = datetime(2026, 9, 28, 10, 0).astimezone()
    assert "someday-review" not in steps(evaluate_checkin(snapshot(), cfg, THU_10, False, set()))
    s = steps(evaluate_checkin(snapshot(), cfg, monday, False, set()))["someday-review"]
    assert s.label == "Review Someday" and not s.done
    assert s.links[0].url == "things:///show?id=someday"
    assert steps(evaluate_checkin(snapshot(), cfg, monday, False, {"someday-review"}))["someday-review"].done


def test_tag_link_is_encoded():
    assert show_url(query="🟢") == "things:///show?query=%F0%9F%9F%A2"


def test_review_affirmations_are_manual_ticks(cfg):
    s = steps(evaluate_checkin(snapshot(), cfg, THU_10, False, set()))
    assert s["today-reviewed"].label == "Today's list is reviewed" and not s["today-reviewed"].done
    assert s["colors-reviewed"].label == "Colors look right" and not s["colors-reviewed"].done
    assert s["today-reviewed"].links[0].url == "things:///show?id=today"
    ticked = steps(evaluate_checkin(snapshot(), cfg, THU_10, False, {"today-reviewed", "colors-reviewed"}))
    assert ticked["today-reviewed"].done and ticked["colors-reviewed"].done


def test_area_step_includes_completed_this_week(cfg):
    snap = snapshot([todo(uuid="c", title="Done loose", status="completed", start="Inbox", tags=[Y],
                          stop=datetime(2026, 9, 30, 9, 0)),
                     todo(uuid="old", title="Old", status="completed", stop=datetime(2026, 9, 20, 9, 0))])
    s = steps(evaluate_checkin(snap, cfg, THU_10, False, set()))["areas"]
    assert [link.url for link in s.links] == ["things:///show?id=c"]
