"""Monday-to-Sunday weeks in local time."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True, order=True)
class Week:
    start: date

    @property
    def end(self) -> date:
        """Exclusive end: the next Monday."""
        return self.start + timedelta(days=7)

    def contains(self, d: date) -> bool:
        return self.start <= d < self.end

    def prev(self) -> "Week":
        return Week(self.start - timedelta(days=7))

    def next(self) -> "Week":
        return Week(self.end)


def week_of(d: date) -> Week:
    return Week(d - timedelta(days=d.weekday()))


def ended_at(week: Week) -> datetime:
    """Aware local midnight at the start of the following Monday."""
    return datetime.combine(week.end, time()).astimezone()
