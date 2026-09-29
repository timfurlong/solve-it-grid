import unicodedata
from datetime import date

from factories import todo

from solve_it_grid.config import load_config
from solve_it_grid.model import colors_of, list_name
from solve_it_grid.paths import repo_root

TAGS = load_config(repo_root() / "config.example.toml").tags


def test_colors_of_matches_nfd_tag():
    custom = {**TAGS, "green": "Grün"}
    t = todo(tags=[unicodedata.normalize("NFD", "Grün")])
    assert colors_of(t, custom) == ["green"]


def test_colors_of_multiple():
    t = todo(tags=["🟡", "Errand", "🟢"])
    assert colors_of(t, TAGS) == ["yellow", "green"]


def test_colors_of_none():
    assert colors_of(todo(tags=["Errand"]), TAGS) == []


TODAY = date(2026, 9, 29)


def test_list_name_distinguishes_upcoming_from_someday():
    assert list_name(todo(start="Someday", start_date=date(2026, 10, 1)), TODAY) == "Upcoming"
    assert list_name(todo(start="Someday"), TODAY) == "Someday"
    assert list_name(todo(start="Someday", start_date=date(2026, 9, 29)), TODAY) == "Today"


def test_list_name_inbox_today_anytime():
    assert list_name(todo(start="Inbox"), TODAY) == "Inbox"
    assert list_name(todo(start="Anytime", in_today=True), TODAY) == "Today"
    assert list_name(todo(start="Anytime"), TODAY) == "Anytime"
