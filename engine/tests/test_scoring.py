from datetime import date, datetime

import pytest
from factories import todo

from sig.config import load_config
from sig.paths import repo_root
from sig.scoring import score_week, unit_ids
from sig.weeks import week_of

AREAS = {"Work": "A-W", "Home": "A-H"}
WEEK = week_of(date(2026, 9, 28))
WED = datetime(2026, 9, 30, 12, 0)
Y, G, R = "🟡 Yellow", "🟢 Green", "🔴 Red"


@pytest.fixture
def cfg():
    return load_config(repo_root() / "config.example.toml")


def done(uuid="t1", tags=(Y,), stop=WED, **kw):
    return todo(uuid=uuid, status="completed", stop=stop, tags=tags, **kw)


def units(score):
    return {u.id: u.done for u in score.units}


def test_unit_ids(cfg):
    assert unit_ids(cfg.goals) == ["yellow-work", "yellow-home", "green-1", "green-2"]


def test_boundary_sunday_2359_counts_monday_0000_does_not(cfg):
    inside = done("a", area_id="A-W", stop=datetime(2026, 10, 4, 23, 59, 59))
    after = done("b", area_id="A-H", stop=datetime(2026, 10, 5, 0, 0))
    before = done("c", area_id="A-H", stop=datetime(2026, 9, 27, 23, 59, 59))
    s = score_week([inside, after, before], cfg, AREAS, WEEK)
    assert s.counts["yellow-work"] == 1 and s.counts["yellow-home"] == 0


def test_yellow_counts_by_area(cfg):
    s = score_week([done(area_id="A-W")], cfg, AREAS, WEEK)
    assert units(s) == {"yellow-work": True, "yellow-home": False, "green-1": False, "green-2": False}
    assert s.units[0].label == "Work yellow" and s.units[0].color == "yellow"


def test_yellow_without_area_counts_nowhere(cfg):
    s = score_week([done(area_id=None)], cfg, AREAS, WEEK)
    assert s.counts["yellow-work"] == 0 and s.counts["yellow-home"] == 0


def test_green_counts_any_area_including_none(cfg):
    greens = [done("a", tags=(G,), area_id=None), done("b", tags=(G,), area_id="A-H")]
    s = score_week(greens, cfg, AREAS, WEEK)
    assert s.counts["green"] == 2 and units(s)["green-2"]


def test_excluded_statuses_and_markers(cfg):
    items = [
        todo(uuid="c", status="canceled", stop=WED, tags=(Y,), area_id="A-W"),
        todo(uuid="o", status="incomplete", tags=(Y,), area_id="A-W"),
        done("r", tags=(R,), area_id="A-W"),
        done("b", tags=("🔵 Blue",), area_id="A-W"),
        done("u", tags=("⚪ Unscored",), area_id="A-W"),
        done("n", tags=(), area_id="A-W"),
    ]
    s = score_week(items, cfg, AREAS, WEEK)
    assert s.counts == {"yellow-work": 0, "yellow-home": 0, "green": 0}


def test_red_done_counted_not_scored(cfg):
    s = score_week([done(f"r{i}", tags=(R,)) for i in range(3)], cfg, AREAS, WEEK)
    assert s.red_done == 3 and not any(u.done for u in s.units)


def test_multi_color_flagged_not_counted(cfg):
    s = score_week([done(tags=(Y, G), area_id="A-W")], cfg, AREAS, WEEK)
    assert s.multi_color == ("t1",) and s.counts["yellow-work"] == 0 and s.counts["green"] == 0


def test_uncolored_completed_listed(cfg):
    s = score_week([done("n", tags=("Errand",)), done("y", area_id="A-W")], cfg, AREAS, WEEK)
    assert s.uncolored_completed == ("n",)


def test_third_green_earns_nothing(cfg):
    s = score_week([done(f"g{i}", tags=(G,)) for i in range(3)], cfg, AREAS, WEEK)
    assert s.counts["green"] == 3 and len(s.units) == 4 and units(s)["green-2"]


def test_hit_only_when_all_units_done(cfg):
    items = [done("w", area_id="A-W"), done("h", area_id="A-H"), done("g1", tags=(G,))]
    assert not score_week(items, cfg, AREAS, WEEK).hit
    assert score_week([*items, done("g2", tags=(G,))], cfg, AREAS, WEEK).hit


def test_dst_weekend_is_ordinary(cfg):
    week = week_of(date(2026, 11, 1))
    assert week.start == date(2026, 10, 26)
    s = score_week([done(area_id="A-W", stop=datetime(2026, 11, 1, 1, 30))], cfg, AREAS, week)
    assert s.counts["yellow-work"] == 1
