"""`solve-it-grid` command line."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from solve_it_grid.categorize import (
    REVIEW_PENDING,
    AlreadyRunning,
    NotReviewed,
    SetupIncomplete,
    run_categorize,
    run_lock,
)
from solve_it_grid.checkin import MANUAL_STEPS
from solve_it_grid.classifier import ClassifierError, ClaudeClassifier
from solve_it_grid.config import Config, config_path, load_config
from solve_it_grid.paths import app_dir, repo_root
from solve_it_grid.progress import scoring_cutoff
from solve_it_grid.prompt import build_system_prompt
from solve_it_grid.review import apply_review, dry_run, render_eval, run_eval
from solve_it_grid.setup_cmd import run_setup
from solve_it_grid.state import StateStore
from solve_it_grid.status import build_status, health_errors, render_text
from solve_it_grid.things_read import ThingsUnavailable, read_snapshot
from solve_it_grid.things_write import UrlSchemeWriter, ensure_tags


def _now() -> datetime:
    return datetime.now().astimezone()


def _load() -> tuple[Config, StateStore] | None:
    path = config_path()
    if not path.exists():
        print("Run solve-it-grid setup first.", file=sys.stderr)
        return None
    return load_config(path), StateStore(app_dir() / "state.db")


def _cmd_status(args, cfg: Config, state: StateStore) -> int:
    now = _now()
    try:
        snap = read_snapshot(scoring_cutoff(state, cfg, now.date()))
    except ThingsUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    status = build_status(snap, state, cfg, now)
    print(json.dumps(status, ensure_ascii=False, indent=2) if args.json else render_text(status))
    return 0


def _cmd_setup(args) -> int:
    now = _now()
    home = app_dir()
    for message in run_setup(home, repo_root(), now, ensure_tags_fn=ensure_tags,
                             install_agent=not args.no_agent):
        print(message)
    cfg = load_config(config_path())
    state = StateStore(home / "state.db")
    try:
        snap = read_snapshot(now.date())
    except ThingsUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    problems = [e for e in health_errors(snap, state, cfg, now) if e["source"] == "setup"]
    for err in problems:
        print(f"! {err['message']}")
    if not problems:
        print("Setup checks passed: tags, areas and Things URLs are all in place.")
    return 0


def _classifier(cfg: Config, home) -> ClaudeClassifier:
    rubric = (cfg.rubric_path or repo_root() / "rubric.md").read_text(encoding="utf-8")
    local_path = home / "rubric.local.md"
    local = local_path.read_text(encoding="utf-8") if local_path.exists() else None
    claude = cfg.claude_path or Path.home() / ".local" / "bin" / "claude"
    return ClaudeClassifier(claude, cfg.model, build_system_prompt(rubric, local), cfg.timeout_seconds, home)


def _summary(result) -> str:
    return (f"requested {result.requested}, applied {len(result.applied)}, "
            f"skipped {len(result.skipped)}, unverified {len(result.unverified)}")


def _cmd_dry_run(cfg: Config, home) -> int:
    try:
        path, assignments, skipped = dry_run(read=read_snapshot, classifier=_classifier(cfg, home), cfg=cfg,
                                             now=_now(), home=home)
    except (ClassifierError, ThingsUnavailable) as exc:
        print(f"Dry run failed: {exc}", file=sys.stderr)
        return 1
    print(path.read_text(encoding="utf-8").rstrip())
    for uuid, reason in skipped:
        print(f"  skipped {uuid}: {reason}")
    print(f"\n{len(assignments)} proposals written to {path}. Edit the color and area columns, "
          "then run: solve-it-grid categorize --apply-review")
    return 0


def _cmd_apply_review(cfg: Config, state: StateStore, home, path) -> int:
    try:
        result = apply_review(path, read=read_snapshot, writer=UrlSchemeWriter(), state=state, cfg=cfg,
                              now=_now(), golden_path=home / "golden.jsonl",
                              log_path=home / "categorize.log.jsonl")
    except (ValueError, FileNotFoundError, ThingsUnavailable) as exc:
        print(f"Apply review failed: {exc}", file=sys.stderr)
        return 1
    print(_summary(result))
    for uuid, reason in result.skipped:
        print(f"  skipped {uuid}: {reason}")
    return 0


def _cmd_eval(args, cfg: Config, state: StateStore) -> int:
    home = app_dir()
    golden = home / "golden.jsonl"
    if not golden.exists():
        print("No golden set yet. Run solve-it-grid categorize --dry-run and --apply-review first.",
              file=sys.stderr)
        return 2
    try:
        report = run_eval(_classifier(cfg, home), golden, cfg.batch_size)
    except ClassifierError as exc:
        print(f"Eval failed: {exc}", file=sys.stderr)
        return 1
    print(render_eval(report))
    return 0


def _cmd_categorize(args, cfg: Config, state: StateStore) -> int:
    home = app_dir()
    if args.dry_run:
        return _cmd_dry_run(cfg, home)
    if args.apply_review:
        return _cmd_apply_review(cfg, state, home, Path(args.apply_review))
    try:
        with run_lock(home / "categorize.lock"):
            result = run_categorize(read=read_snapshot, writer=UrlSchemeWriter(),
                                    classifier=_classifier(cfg, home), state=state, cfg=cfg, now=_now(),
                                    log_path=home / "categorize.log.jsonl")
    except AlreadyRunning:
        print("Another categorize run is in progress.")
        return 0
    except NotReviewed:
        print(REVIEW_PENDING)
        return 0
    except (ClassifierError, ThingsUnavailable, SetupIncomplete) as exc:
        print(f"Categorize failed: {exc}", file=sys.stderr)
        return 1
    print(_summary(result))
    for uuid, reason in result.skipped:
        print(f"  skipped {uuid}: {reason}")
    return 0


def _cmd_chip(args, cfg: Config, state: StateStore) -> int:
    ids = None if args.ids == ["all"] else [int(i) for i in args.ids]
    count = state.ack_chips(ids, _now())
    print(f"Moved {count} chip{'s' if count != 1 else ''} to the done jar.")
    return 0


def _cmd_checkin(args, cfg: Config, state: StateStore) -> int:
    now = _now()
    if args.action == "done":
        state.set_checkin_done(now.date(), now)
        print("Check-in done for today.")
        return 0
    if args.step not in MANUAL_STEPS:
        print(f"Only manual steps can be ticked: {', '.join(MANUAL_STEPS)}", file=sys.stderr)
        return 2
    state.tick(now.date(), args.step, now)
    print(f"Ticked {args.step}.")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="solve-it-grid", description="Solve It Grid for Things")
    sub = parser.add_subparsers(dest="cmd", required=True)

    setup = sub.add_parser("setup", help="write config, create color tags, install the launchd agent")
    setup.add_argument("--no-agent", action="store_true", help="skip installing the launchd agent")

    status = sub.add_parser("status", help="show this week's progress and check-in")
    status.add_argument("--json", action="store_true", help="machine-readable output")
    status.set_defaults(func=_cmd_status)

    categorize = sub.add_parser("categorize", help="color and file to-dos with Claude")
    mode = categorize.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="write proposals to review.tsv, change nothing")
    mode.add_argument("--apply-review", nargs="?", const=str(app_dir() / "review.tsv"), metavar="PATH",
                      help="apply a reviewed file (default: review.tsv) and save it to the golden set")
    categorize.set_defaults(func=_cmd_categorize)

    evaluate = sub.add_parser("eval", help="measure the classifier against the golden set")
    evaluate.set_defaults(func=_cmd_eval)

    chip = sub.add_parser("chip", help="manage chips")
    chip_sub = chip.add_subparsers(dest="action", required=True)
    ack = chip_sub.add_parser("ack", help="confirm pending chips were moved to the done jar")
    ack.add_argument("ids", nargs="+", help="chip ids, or 'all'")
    chip.set_defaults(func=_cmd_chip)

    checkin = sub.add_parser("checkin", help="daily check-in")
    checkin_sub = checkin.add_subparsers(dest="action", required=True)
    checkin_sub.add_parser("done", help="mark today's check-in done")
    tick = checkin_sub.add_parser("tick", help="tick a manual step")
    tick.add_argument("step")
    checkin.set_defaults(func=_cmd_checkin)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "setup":
        return _cmd_setup(args)
    loaded = _load()
    if loaded is None:
        return 2
    return args.func(args, *loaded)


if __name__ == "__main__":
    sys.exit(main())
