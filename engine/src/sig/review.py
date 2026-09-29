"""First-run review: dry run to review.tsv, apply the edited file, golden set and eval."""

import csv
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sig.categorize import (
    REVIEW_META,
    CategorizeResult,
    apply_assignments,
    log_assignments,
    select_work,
    verify_writes,
    window_start,
)
from sig.classifier import AREAS, Assignment, validate
from sig.config import COLORS, Config
from sig.model import Snapshot
from sig.prompt import WorkItem
from sig.state import StateStore
from sig.things_write import ThingsWriter

HEADER = ["uuid", "kind", "needs", "title", "color", "area", "reason"]
ITEMS_FILE = "review.items.jsonl"


def _clean(text: str) -> str:
    return " ".join(text.split())


def _classify_all(classifier, items: list[WorkItem], batch_size: int):
    valid: list[Assignment] = []
    skipped: list[tuple[str, str]] = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        v, s = validate(batch, classifier.classify(batch))
        valid += v
        skipped += s
    return valid, skipped


def write_review(work: list[WorkItem], assignments: list[Assignment], home: Path) -> Path:
    by_uuid = {a.uuid: a for a in assignments}
    path = home / "review.tsv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        out = csv.writer(fh, delimiter="\t", lineterminator="\n")
        out.writerow(HEADER)
        for w in work:
            a = by_uuid.get(w.uuid)
            out.writerow([w.uuid, w.kind, ",".join(w.payload["needs"]), _clean(w.payload.get("title") or ""),
                          (a.color if a else None) or "", (a.area if a else None) or "",
                          _clean(a.reason) if a else ""])
    with (home / ITEMS_FILE).open("w", encoding="utf-8") as fh:
        for w in work:
            fh.write(json.dumps(w.payload, ensure_ascii=False) + "\n")
    return path


def dry_run(*, read: Callable[[date], Snapshot], classifier, cfg: Config, now: datetime,
            home: Path) -> tuple[Path, list[Assignment], list[tuple[str, str]]]:
    snap = read(window_start(now.date()))
    work = select_work(snap, cfg, now.date())
    assignments, skipped = _classify_all(classifier, work, cfg.batch_size)
    return write_review(work, assignments, home), assignments, skipped


def read_review(path: Path) -> list[Assignment]:
    rows = []
    with path.open(encoding="utf-8", newline="") as fh:
        for n, row in enumerate(csv.reader(fh, delimiter="\t"), start=1):
            if n == 1 or not row:
                continue
            record = dict(zip(HEADER, row + [""] * (len(HEADER) - len(row)), strict=True))
            color, area = record["color"].strip(), record["area"].strip()
            if color and color not in COLORS:
                raise ValueError(f"line {n}: invalid color '{color}'")
            if area and area not in AREAS:
                raise ValueError(f"line {n}: invalid area '{area}'")
            rows.append(Assignment(record["uuid"], color or None, area or None, record["reason"]))
    return rows


def apply_review(path: Path, *, read: Callable[[date], Snapshot], writer: ThingsWriter, state: StateStore,
                 cfg: Config, now: datetime, golden_path: Path, log_path: Path,
                 sleep=time.sleep) -> CategorizeResult:
    rows = read_review(path)
    payloads = {}
    items_path = path.parent / ITEMS_FILE
    if items_path.exists():
        for line in items_path.read_text(encoding="utf-8").splitlines():
            payload = json.loads(line)
            payloads[payload["uuid"]] = payload

    since = window_start(now.date())
    snap = read(since)
    current = {w.uuid: w for w in select_work(snap, cfg, now.date())}
    pending: list[Assignment] = []
    skipped: list[tuple[str, str]] = []
    for row in rows:
        item = current.get(row.uuid)
        if item is None:
            skipped.append((row.uuid, "already handled"))
        elif item.needs_color and row.color is None:
            skipped.append((row.uuid, "missing color"))
        else:
            pending.append(row)

    applied, failed = apply_assignments(list(current.values()), pending, snap, writer, cfg)
    skipped += failed
    unverified = verify_writes(read, since, applied, current, cfg, sleep)
    log_assignments(log_path, applied, current, "review", now)

    with golden_path.open("a", encoding="utf-8") as fh:
        for row in rows:
            if row.uuid in payloads:
                fh.write(json.dumps({"item": payloads[row.uuid], "color": row.color, "area": row.area},
                                    ensure_ascii=False) + "\n")
    state.set_meta(REVIEW_META, now.isoformat(timespec="seconds"))
    return CategorizeResult(len(rows), applied, skipped, unverified)


@dataclass(frozen=True)
class EvalReport:
    total: int
    agree: int
    per_color: dict[str, tuple[int, int]]
    disagreements: list[dict]


def run_eval(classifier, golden_path: Path, batch_size: int) -> EvalReport:
    latest: dict[str, dict] = {}
    for line in golden_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("color"):
            latest[row["item"]["uuid"]] = row
    items = [WorkItem(r["item"]["uuid"], r["item"]["kind"], True, False,
                      {**r["item"], "needs": ["color"]}) for r in latest.values()]
    answers, _ = _classify_all(classifier, items, batch_size)
    got = {a.uuid: a for a in answers}
    per_color: dict[str, tuple[int, int]] = {}
    disagreements = []
    agree = 0
    for uuid, row in latest.items():
        expected = row["color"]
        answer = got.get(uuid)
        hit = answer is not None and answer.color == expected
        ok, total = per_color.get(expected, (0, 0))
        per_color[expected] = (ok + hit, total + 1)
        agree += hit
        if not hit:
            disagreements.append({"title": row["item"].get("title"), "expected": expected,
                                  "got": answer.color if answer else None,
                                  "reason": answer.reason if answer else "no answer"})
    return EvalReport(len(latest), agree, per_color, disagreements)


def render_eval(report: EvalReport) -> str:
    pct = f" ({100 * report.agree // report.total}%)" if report.total else ""
    lines = [f"Agreement: {report.agree}/{report.total}{pct}"]
    lines += [f"  {color:9} {ok}/{total}" for color, (ok, total) in sorted(report.per_color.items())]
    if report.disagreements:
        lines.append("Disagreements:")
        lines += [f"  expected {d['expected']}, got {d['got']}: {d['title']} ({d['reason']})"
                  for d in report.disagreements]
    return "\n".join(lines)
