import unicodedata
from datetime import date

from factories import todo

from sig.config import load_config
from sig.model import colors_of, list_name
from sig.paths import repo_root

TAGS = load_config(repo_root() / "config.example.toml").tags


def test_colors_of_matches_nfd_tag():
    t = todo(tags=[unicodedata.normalize("NFD", "🟢 Green")])
    assert colors_of(t, TAGS) == ["green"]


def test_colors_of_multiple():
    t = todo(tags=["🟡 Yellow", "Errand", "🟢 Green"])
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
