"""One categorizer run: select uncolored or area-less items, classify, write back, verify."""

import fcntl
import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from solve_it_grid.classifier import Assignment, ClassifierError, validate
from solve_it_grid.config import Config
from solve_it_grid.model import Snapshot, colors_of
from solve_it_grid.prompt import WorkItem, work_item_from_project, work_item_from_todo
from solve_it_grid.setup_check import setup_problems
from solve_it_grid.state import StateStore
from solve_it_grid.things_read import ThingsUnavailable
from solve_it_grid.things_write import ThingsWriteError, ThingsWriter
from solve_it_grid.weeks import week_of

RUN_KIND = "categorize"
REVIEW_META = "review_applied_at"
REVIEW_PENDING = ("First review pending. Run solve-it-grid categorize --dry-run, "
                  "then solve-it-grid categorize --apply-review.")
# Things applies URL-scheme writes asynchronously; a big batch can take several seconds to land.
VERIFY_DELAYS_SECONDS = (2, 4, 8)
# An item the model couldn't place (area unsure) is not asked about again for this long.
DEFER = timedelta(hours=24)


class AlreadyRunning(Exception):
    pass


class NotReviewed(Exception):
    pass


class SetupIncomplete(Exception):
    pass


@dataclass(frozen=True)
class CategorizeResult:
    requested: int
    applied: list[Assignment]
    skipped: list[tuple[str, str]]
    unverified: list[str]


@contextmanager
def run_lock(path: Path) -> Iterator[None]:
    handle = open(path, "w")  # noqa: SIM115 - held for the duration of the lock
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise AlreadyRunning from None
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def window_start(today: date) -> date:
    """Completions on or after this date are still eligible for coloring."""
    return week_of(today).prev().start


def select_work(snapshot: Snapshot, cfg: Config, today: date) -> list[WorkItem]:
    since = window_start(today)
    titles = {uuid: title for title, uuid in snapshot.area_ids.items()}
    items: list[WorkItem] = []
    for t in snapshot.todos:
        if t.status == "canceled" or not t.title.strip():
            continue
        completed = t.status == "completed"
        if completed and (t.stop is None or t.stop.date() < since):
            continue
        needs_color = not colors_of(t, cfg.tags)
        needs_area = (t.area_id is None and t.project_id is None
                      and (completed or t.start != "Inbox"))
        if needs_color or needs_area:
            items.append(work_item_from_todo(t, titles, needs_color, needs_area, today))
    items += [work_item_from_project(p) for p in snapshot.projects
              if p.area_id is None and p.title.strip()]
    return items


def apply_assignments(work: list[WorkItem], assignments: list[Assignment], snapshot: Snapshot,
                      writer: ThingsWriter, cfg: Config) -> tuple[list[Assignment], list[tuple[str, str]]]:
    """Write each assignment. Returns (applied, failed) where failed is (uuid, error)."""
    by_uuid = {w.uuid: w for w in work}
    area_ids = {key: snapshot.area_ids.get(title) for key, title in cfg.areas.items()}
    applied: list[Assignment] = []
    failed: list[tuple[str, str]] = []
    for a in assignments:
        item = by_uuid[a.uuid]
        wrote = False
        try:
            if item.needs_color and a.color:
                writer.add_tag(a.uuid, cfg.tags[a.color])
                wrote = True
            if item.needs_area and a.area and area_ids.get(a.area):
                set_area = writer.set_project_area if item.kind == "project" else writer.set_todo_area
                set_area(a.uuid, area_ids[a.area])
                wrote = True
        except ThingsWriteError as exc:
            failed.append((a.uuid, str(exc)))
            continue
        if wrote:
            applied.append(a)
    return applied, failed


def unverified_writes(after: Snapshot, applied: list[Assignment], work: dict[str, WorkItem],
                cfg: Config) -> list[str]:
    todos = {t.uuid: t for t in after.todos}
    projects = {p.uuid: p for p in after.projects}
    area_ids = {key: after.area_ids.get(title) for key, title in cfg.areas.items()}
    missing = []
    for a in applied:
        item = work[a.uuid]
        if item.kind == "project":
            p = projects.get(a.uuid)
            ok = p is not None and (not a.area or p.area_id == area_ids.get(a.area))
        else:
            t = todos.get(a.uuid)
            ok = t is not None
            if ok and item.needs_color and a.color:
                ok = a.color in colors_of(t, cfg.tags)
            if ok and item.needs_area and a.area:
                ok = t.area_id == area_ids.get(a.area)
        if not ok:
            missing.append(a.uuid)
    return missing


def verify_writes(read: Callable[[date], Snapshot], since: date, applied: list[Assignment],
                  work: dict[str, WorkItem], cfg: Config, sleep) -> list[str]:
    """Re-read Things until every write shows up, backing off between reads. Returns what never landed."""
    missing = [a.uuid for a in applied]
    for delay in VERIFY_DELAYS_SECONDS:
        if not missing:
            break
        sleep(delay)
        pending = [a for a in applied if a.uuid in missing]
        missing = unverified_writes(read(since), pending, work, cfg)
    return missing


def log_assignments(log_path: Path, applied: list[Assignment], work: dict[str, WorkItem], model: str,
                    now: datetime) -> None:
    with log_path.open("a", encoding="utf-8") as fh:
        for a in applied:
            fh.write(json.dumps({
                "ts": now.isoformat(timespec="seconds"), "uuid": a.uuid,
                "title": work[a.uuid].payload.get("title"), "color": a.color, "area": a.area,
                "reason": a.reason, "model": model,
            }, ensure_ascii=False) + "\n")


def run_categorize(*, read: Callable[[date], Snapshot], writer: ThingsWriter, classifier, state: StateStore,
                   cfg: Config, now: datetime, log_path: Path, sleep=time.sleep,
                   require_review: bool = True) -> CategorizeResult:
    if require_review and state.get_meta(REVIEW_META) is None:
        raise NotReviewed
    since = window_start(now.date())
    applied: list[Assignment] = []
    skipped: list[tuple[str, str]] = []
    try:
        snap = read(since)
        problems = setup_problems(snap, cfg)
        if problems:
            raise SetupIncomplete(" ".join(problems))
        deferred = state.deferred(now)
        work = [w for w in select_work(snap, cfg, now.date()) if w.uuid not in deferred]
        by_uuid = {w.uuid: w for w in work}
        for i in range(0, len(work), cfg.batch_size):
            batch = work[i:i + cfg.batch_size]
            valid, rejected = validate(batch, classifier.classify(batch))
            done, failed = apply_assignments(batch, valid, snap, writer, cfg)
            applied += done
            skipped += rejected + failed
            written = {a.uuid for a in done} | {uuid for uuid, _ in failed}
            for a in valid:
                if a.uuid not in written:
                    state.defer(a.uuid, now + DEFER)
            log_assignments(log_path, done, by_uuid, cfg.model, now)
        unverified = verify_writes(read, since, applied, by_uuid, cfg, sleep)
    except (ClassifierError, ThingsUnavailable, SetupIncomplete) as exc:
        state.record_run(RUN_KIND, False, str(exc), now)
        raise
    except Exception as exc:
        state.record_run(RUN_KIND, False, f"{type(exc).__name__}: {exc}", now)
        raise
    state.record_run(RUN_KIND, True, None, now)
    return CategorizeResult(len(work), applied, skipped, unverified)
