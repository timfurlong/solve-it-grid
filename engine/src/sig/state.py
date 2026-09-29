"""SQLite store for chips, frozen weeks, check-ins, categorizer runs and metadata."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chips (
    id INTEGER PRIMARY KEY,
    week_start TEXT NOT NULL,
    unit TEXT NOT NULL,
    color TEXT NOT NULL,
    awarded_at TEXT NOT NULL,
    acked_at TEXT,
    UNIQUE (week_start, unit)
);
CREATE TABLE IF NOT EXISTS weeks (
    week_start TEXT PRIMARY KEY,
    units_done INTEGER NOT NULL,
    units_total INTEGER NOT NULL,
    hit INTEGER NOT NULL,
    chips INTEGER NOT NULL,
    frozen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkins (day TEXT PRIMARY KEY, done_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkin_ticks (
    day TEXT NOT NULL, step TEXT NOT NULL, ticked_at TEXT NOT NULL, PRIMARY KEY (day, step)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, started_at TEXT NOT NULL, ok INTEGER NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deferrals (uuid TEXT PRIMARY KEY, until TEXT NOT NULL);
"""


@dataclass(frozen=True)
class Chip:
    id: int
    week_start: date
    unit: str
    color: str
    awarded_at: datetime
    acked_at: datetime | None


@dataclass(frozen=True)
class FrozenWeek:
    week_start: date
    units_done: int
    units_total: int
    hit: bool
    chips: int


def _chip(row: sqlite3.Row) -> Chip:
    return Chip(
        id=row["id"], week_start=date.fromisoformat(row["week_start"]), unit=row["unit"],
        color=row["color"], awarded_at=datetime.fromisoformat(row["awarded_at"]),
        acked_at=datetime.fromisoformat(row["acked_at"]) if row["acked_at"] else None,
    )


class StateStore:
    def __init__(self, path: Path):
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._db:
            return self._db.execute(sql, params)

    # chips
    def award_chip(self, week_start: date, unit: str, color: str, now: datetime) -> Chip | None:
        cur = self._exec(
            "INSERT OR IGNORE INTO chips (week_start, unit, color, awarded_at) VALUES (?, ?, ?, ?)",
            (week_start.isoformat(), unit, color, now.isoformat()),
        )
        if cur.rowcount == 0:
            return None
        return _chip(self._db.execute("SELECT * FROM chips WHERE id = ?", (cur.lastrowid,)).fetchone())

    def pending_chips(self) -> list[Chip]:
        rows = self._db.execute("SELECT * FROM chips WHERE acked_at IS NULL ORDER BY id").fetchall()
        return [_chip(r) for r in rows]

    def ack_chips(self, ids: list[int] | None, now: datetime) -> int:
        if ids is None:
            cur = self._exec("UPDATE chips SET acked_at = ? WHERE acked_at IS NULL", (now.isoformat(),))
        else:
            marks = ",".join("?" * len(ids))
            cur = self._exec(
                f"UPDATE chips SET acked_at = ? WHERE acked_at IS NULL AND id IN ({marks})",
                (now.isoformat(), *ids),
            )
        return cur.rowcount

    def total_earned(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM chips WHERE acked_at IS NOT NULL").fetchone()[0]

    def chips_for_week(self, week_start: date) -> list[Chip]:
        rows = self._db.execute(
            "SELECT * FROM chips WHERE week_start = ? ORDER BY id", (week_start.isoformat(),)
        ).fetchall()
        return [_chip(r) for r in rows]

    # weeks
    def freeze_week(self, fw: FrozenWeek, now: datetime) -> None:
        self._exec(
            "INSERT OR REPLACE INTO weeks VALUES (?, ?, ?, ?, ?, ?)",
            (fw.week_start.isoformat(), fw.units_done, fw.units_total, int(fw.hit), fw.chips,
             now.isoformat()),
        )

    def is_frozen(self, week_start: date) -> bool:
        row = self._db.execute("SELECT 1 FROM weeks WHERE week_start = ?", (week_start.isoformat(),))
        return row.fetchone() is not None

    def frozen_weeks(self) -> list[FrozenWeek]:
        rows = self._db.execute("SELECT * FROM weeks ORDER BY week_start").fetchall()
        return [
            FrozenWeek(date.fromisoformat(r["week_start"]), r["units_done"], r["units_total"],
                       bool(r["hit"]), r["chips"])
            for r in rows
        ]

    # check-in
    def set_checkin_done(self, day: date, now: datetime) -> None:
        self._exec("INSERT OR REPLACE INTO checkins VALUES (?, ?)", (day.isoformat(), now.isoformat()))

    def checkin_done(self, day: date) -> bool:
        row = self._db.execute("SELECT 1 FROM checkins WHERE day = ?", (day.isoformat(),))
        return row.fetchone() is not None

    def tick(self, day: date, step: str, now: datetime) -> None:
        self._exec("INSERT OR REPLACE INTO checkin_ticks VALUES (?, ?, ?)",
                   (day.isoformat(), step, now.isoformat()))

    def ticks(self, day: date) -> set[str]:
        rows = self._db.execute("SELECT step FROM checkin_ticks WHERE day = ?", (day.isoformat(),))
        return {r["step"] for r in rows}

    # runs
    def record_run(self, kind: str, ok: bool, error: str | None, now: datetime) -> None:
        self._exec("INSERT INTO runs (kind, started_at, ok, error) VALUES (?, ?, ?, ?)",
                   (kind, now.isoformat(), int(ok), error))

    def failure_streak(self, kind: str) -> tuple[int, datetime | None, str | None]:
        last_ok = self._db.execute(
            "SELECT COALESCE(MAX(id), 0) FROM runs WHERE kind = ? AND ok = 1", (kind,)
        ).fetchone()[0]
        rows = self._db.execute(
            "SELECT started_at, error FROM runs WHERE kind = ? AND ok = 0 AND id > ? ORDER BY id",
            (kind, last_ok),
        ).fetchall()
        if not rows:
            return (0, None, None)
        return (len(rows), datetime.fromisoformat(rows[0]["started_at"]), rows[-1]["error"])

    # meta
    def get_meta(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._exec("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))

    # deferrals: items the categorizer asked about and should leave alone for a while
    def defer(self, uuid: str, until: datetime) -> None:
        self._exec("INSERT OR REPLACE INTO deferrals VALUES (?, ?)", (uuid, until.isoformat()))

    def deferred(self, now: datetime) -> set[str]:
        rows = self._db.execute("SELECT uuid, until FROM deferrals").fetchall()
        return {r["uuid"] for r in rows if datetime.fromisoformat(r["until"]) > now}
