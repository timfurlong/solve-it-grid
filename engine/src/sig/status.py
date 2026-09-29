"""Assemble the `sig status` report and its health checks."""

from datetime import datetime, timedelta

from sig.categorize import REVIEW_META, RUN_KIND
from sig.checkin import MANUAL_STEPS, evaluate_checkin
from sig.config import Config
from sig.model import Snapshot
from sig.progress import refresh
from sig.setup_check import setup_problems
from sig.state import StateStore


def _error(source: str, message: str, since: str | None = None) -> dict:
    return {"source": source, "message": message, "since": since}


def health_errors(snapshot: Snapshot, state: StateStore, cfg: Config, now: datetime) -> list[dict]:
    errors = [_error("setup", problem) for problem in setup_problems(snapshot, cfg)]
    if state.get_meta(REVIEW_META) is None:
        errors.append(_error(
            "categorizer",
            "First review pending. Run sig categorize --dry-run, then sig categorize --apply-review."))
    count, since, last_error = state.failure_streak(RUN_KIND)
    if count >= cfg.failure_threshold:
        errors.append(_error("categorizer", last_error or "Categorizer failing",
                             since.isoformat() if since else None))
    return errors


def build_status(snapshot: Snapshot, state: StateStore, cfg: Config, now: datetime) -> dict:
    today = now.date()
    progress = refresh(snapshot, state, cfg, now)
    checkin = evaluate_checkin(snapshot, cfg, now, state.checkin_done(today), state.ticks(today))
    errors = health_errors(snapshot, state, cfg, now)
    cur = progress.current
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "week": {"start": cur.week.start.isoformat(),
                 "end": (cur.week.end - timedelta(days=1)).isoformat(), "hit": cur.hit},
        "units": [{"id": u.id, "color": u.color, "label": u.label, "done": u.done} for u in cur.units],
        "red_done": cur.red_done,
        "chips": {
            "pending": [{"id": c.id, "week_start": c.week_start.isoformat(), "unit": c.unit, "color": c.color,
                         "awarded_at": c.awarded_at.isoformat(timespec="seconds")}
                        for c in state.pending_chips()],
            "total_earned": state.total_earned(),
        },
        "streak": {"current": progress.streak, "best": progress.best_streak},
        "checkin": {
            "workday": checkin.workday, "due": checkin.due, "done": checkin.done,
            "steps": [{"id": s.id, "label": s.label, "done": s.done, "manual": s.id in MANUAL_STEPS,
                       "links": [{"label": link.label, "url": link.url} for link in s.links]}
                      for s in checkin.steps],
        },
        "last_week": ({"start": progress.last_week.week_start.isoformat(), "hit": progress.last_week.hit}
                      if progress.last_week else None),
        "history": [{"start": fw.week_start.isoformat(), "units_done": fw.units_done, "hit": fw.hit,
                     "chips": fw.chips} for fw in progress.history],
        "health": {"ok": not errors, "errors": errors},
    }


def render_text(status: dict) -> str:
    week = status["week"]
    labels = {u["id"]: u["label"] for u in status["units"]}
    lines = [f"Week of {week['start']} to {week['end']}: {'hit' if week['hit'] else 'not hit yet'}"]
    lines += [f"  {'[x]' if u['done'] else '[ ]'} {u['label']}" for u in status["units"]]
    lines.append(f"  Reds finished: {status['red_done']} (not scored)")
    for chip in status["chips"]["pending"]:
        lines.append(f"Move a {chip['color']} chip ({labels.get(chip['unit'], chip['unit'])}). "
                     f"Then run: sig chip ack {chip['id']}")
    checkin = status["checkin"]
    state = "done" if checkin["done"] else ("due" if checkin["due"] else "not due")
    lines.append(f"Check-in ({state}):")
    for step in checkin["steps"]:
        lines.append(f"  {'[x]' if step['done'] else '[ ]'} {step['label']}")
        if not step["done"]:
            lines += [f"      {link['label']}: {link['url']}" for link in step["links"]]
    streak = status["streak"]
    lines.append(f"Streak: {streak['current']} weeks (best {streak['best']}). "
                 f"Chips earned: {status['chips']['total_earned']}")
    if status["last_week"]:
        lines.append(f"Last week: {'hit' if status['last_week']['hit'] else 'missed'}")
    for err in status["health"]["errors"]:
        since = f" (since {err['since']})" if err["since"] else ""
        lines.append(f"! {err['source']}: {err['message']}{since}")
    return "\n".join(lines)
