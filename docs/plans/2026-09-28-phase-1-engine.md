# Phase 1: Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `solve-it-grid`, the Python engine that colors Things to-dos with Claude Haiku, scores the week's yellow and green goals, awards chips, tracks the daily check-in, and reports everything through `solve-it-grid status`.

**Architecture:** A uv-managed Python package in `engine/` with one module per responsibility. Pure functions do the scoring, check-in and validation work over an immutable `Snapshot` read from Things with things.py. Side effects are isolated in a few modules: the Things reader, the Things writer (URL scheme and AppleScript), the `claude` subprocess, and a SQLite state store. The CLI wires them together. A launchd agent runs `solve-it-grid categorize` every 10 minutes.

**Tech Stack:** Python 3.12+, uv, things.py, holidays, stdlib (sqlite3, tomllib, argparse, subprocess, fcntl), pytest, ruff.

**Spec:** `docs/specs/2026-09-28-solve-it-grid-design.md` (phase 1 of 2). Read the spec before starting any task.

## Global Constraints

- Package `solve_it_grid` lives in `engine/src/solve_it_grid/`. The console script is `solve-it-grid = "solve_it_grid.cli:main"`. Install for real use with `uv tool install --editable ./engine`, so the package can find the repo's `rubric.md` and `config.example.toml`.
- Runtime dependencies: `things.py>=1.0.1` and `holidays>=0.50` only. Everything else comes from the stdlib.
- All user data lives in `app_dir()`: `$SOLVE_IT_GRID_HOME` when set (tests always set it to a tmp dir), otherwise `~/Library/Application Support/solve-it-grid/`. Nothing personal is ever written inside the repo.
- Default tag names: `🔴`, `🟡`, `🟢`, `🔵`, `⚪`. Tags are compared after NFC normalization.
- Units: `yellow-work`, `yellow-home`, `green-1`, `green-2`. A goal with target 1 has a unit id equal to the goal id. Otherwise the ids are `{goal_id}-{i}` for i = 1..target.
- Week: Monday 00:00 to Sunday 23:59:59 local time. A completion belongs to the week containing its local `stop_date`.
- A past week freezes when it has ended and every to-do completed in it has a color, or 48 hours after it ended.
- Model: the `sonnet` alias (follows the latest Sonnet; changed from Haiku after the first review), batch size 25, timeout 60 s, extended thinking off (`MAX_THINKING_TOKENS=0` in the subprocess env), 3 consecutive failed runs trigger the error state.
- Pinned headless argv (verified 2026-09-28 against Claude Code 2.1.284 with subscription login). **Do not use `--bare`: it disables OAuth.**

  ```
  <claude> -p --model <model> --tools "" --strict-mcp-config --setting-sources ""
           --disable-slash-commands --no-session-persistence --output-format json
           --json-schema <OUTPUT_SCHEMA json> --system-prompt <prompt>
  ```

  The user message goes on stdin. The result is in `structured_output` of the stdout JSON. `is_error: true` means failure.
- The Things auth token comes from `things.token()`. A URL containing `auth-token` is never logged, printed or written to disk.
- Tests never touch the real Things database or run real `open`, `osascript`, `launchctl` or `claude` processes, except tests marked `@pytest.mark.live`, which are deselected by default.
- **Human gates.** Ask the user in chat and wait for a yes before any step that:
  - modifies real Things data (tags, colors, areas)
  - edits `~/.claude/skills/things/SKILL.md`
  - installs the launchd agent

  Those steps are marked **GATE**.
- Prose, docs and commit messages use no em dashes. Commit messages carry no attribution lines.
- Run tests from `engine/`: `uv run pytest -q`.

## Review Focus

1. **macOS privacy blocks the launchd process from reading Things' group container.** The categorizer must record a failed run whose message tells the user to grant Full Disk Access, not die silently. Tests in Task 2 and Task 10.
2. **Area titles in `config.toml` don't match Things** (the emoji prefix is missing, or an area was renamed). The yellow goals would never count. `solve-it-grid status` must report a setup error naming the missing area. Test in Task 7.
3. **A color tag is renamed or deleted in Things.** Counts would silently drop to zero. Status must report the missing tags. Tag matching must survive Unicode normalization differences. Tests in Task 2 and Task 7.
4. **The model returns uuids that weren't asked about, duplicates, or omits items.** Only requested items are applied, the first answer wins, and omitted items are retried next run. Test in Task 9.
5. **A completion syncs from the phone after its week froze.** The frozen result must not change, and no chip is awarded for it. Test in Task 5.

---

### Task 1: Package scaffold, paths and config

**Files:**
- Create: `engine/pyproject.toml`, `engine/src/solve_it_grid/__init__.py`, `engine/src/solve_it_grid/paths.py`, `engine/src/solve_it_grid/config.py`, `config.example.toml`
- Test: `engine/tests/test_config.py`, `engine/tests/conftest.py`

**Interfaces:**
- Produces:
  - `paths.app_dir() -> Path` (creates the dir if missing)
  - `paths.repo_root() -> Path` (`Path(__file__).resolve().parents[3]`)
  - `config.Color = Literal["red","yellow","green","blue","unscored"]` and `config.COLORS: tuple[Color, ...]` in that order
  - `config.Goal(id: str, label: str, color: Color, area: str, target: int)`, where `area` is `"work" | "home" | "any"`
  - `config.Config`: `start_week: date | None`, `rubric_path: Path | None`, `claude_path: Path | None`, `tags: dict[Color, str]`, `areas: dict[str, str]` (key to Things area title), `goals: tuple[Goal, ...]`, `checkin_time: time`, `holidays_country: str`, `model: str`, `batch_size: int`, `timeout_seconds: int`, `failure_threshold: int`
  - `config.load_config(path: Path) -> Config`
  - `config.config_path() -> Path` (`app_dir() / "config.toml"`)

- [x] **Step 1: Write `pyproject.toml`**

  - `name = "solve-it-grid"` (the uv tool dir in Task 12 depends on it).
  - hatchling build and a `src/` layout.
  - `requires-python = ">=3.12"`.
  - Dependencies as in Global Constraints. Dev group: `pytest>=8` and `ruff`.
  - `[tool.pytest.ini_options]` with `addopts = "-m 'not live'"` and `markers = ["live: reads the real Things database"]`.

  `conftest.py` has an autouse fixture that sets `SOLVE_IT_GRID_HOME` to `tmp_path`.

- [x] **Step 2: Write `config.example.toml` at the repo root**

  Keys:
  - `start_week = ""`
  - `[paths] rubric = ""`, `claude = ""`
  - `[tags]` with the five default names
  - `[areas] work = "Work"`, `home = "Home"`
  - three `[[goals]]` tables matching the spec's goal table (`id`, `label` "Work yellow" / "Home yellow" / "Green", `color`, `area`, `target`)
  - `[checkin] time = "09:00"`, `holidays = "US"`
  - `[categorizer] model`, `batch_size = 25`, `timeout_seconds = 60`, `failure_threshold = 3`

  Each key gets a one-line comment.

- [x] **Step 3: Write failing tests**

  ```python
  def test_loads_example_config():
      cfg = load_config(repo_root() / "config.example.toml")
      assert [g.id for g in cfg.goals] == ["yellow-work", "yellow-home", "green"]
      assert cfg.tags["green"] == "🟢"
      assert cfg.checkin_time == time(9, 0)
      assert cfg.start_week is None and cfg.rubric_path is None

  def test_app_dir_honors_sig_home(tmp_path):
      assert app_dir() == tmp_path

  def test_rejects_unknown_goal_color(tmp_path): ...  # color = "purple" -> ValueError naming the goal id
  ```

- [x] **Step 4:** Run `uv run pytest tests/test_config.py -q`. Expected: FAIL (module missing).
- [x] **Step 5: Implement `paths.py` and `config.py`** with `tomllib`. Empty strings map to `None`.
- [x] **Step 6:** Run the tests. Expected: PASS. Also run `uv run ruff check`, which should be clean.
- [x] **Step 7: Commit**: `git commit -m "Add solve-it-grid package scaffold and config loading"`

### Task 2: Domain model and Things reader

**Files:**
- Create: `engine/src/solve_it_grid/model.py`, `engine/src/solve_it_grid/things_read.py`, `engine/tests/factories.py`
- Test: `engine/tests/test_model.py`, `engine/tests/test_things_read.py`

**Interfaces:**
- Consumes: `Color`, `Config` (Task 1).
- Produces:
  - `model.Todo` (frozen):
    - `uuid: str`, `title: str`, `notes: str`
    - `status: Literal["incomplete","completed","canceled"]`
    - `start: str` (`"Inbox" | "Anytime" | "Someday"`)
    - `start_date: date | None`, `deadline: date | None`
    - `stop: datetime | None` (local naive)
    - `area_id: str | None`: the resolved area (own area, then project, then heading's project)
    - `project_id: str | None`: the resolved project, including via heading
    - `project_title: str | None`, `heading_title: str | None`
    - `tags: tuple[str, ...]`, `in_today: bool`
  - `model.Project` (frozen): `uuid`, `title`, `notes`, `area_id: str | None`, `status`
  - `model.Snapshot` (frozen):
    - `todos: tuple[Todo, ...]`: open to-dos plus to-dos completed since the cutoff
    - `projects: tuple[Project, ...]`: open projects
    - `area_ids: dict[str, str]`: area title to uuid
    - `tag_names: frozenset[str]`
    - `inbox_count: int`
    - `token_present: bool`
  - `model.colors_of(todo: Todo, tags: dict[Color, str]) -> list[Color]`: NFC-normalized match
  - `things_read.ThingsUnavailable(Exception)`
  - `things_read.to_todo(record: dict, projects: dict[str, dict], headings: dict[str, dict], today_ids: set[str]) -> Todo`
  - `things_read.read_snapshot(completed_since: date) -> Snapshot`
  - `factories.todo(**overrides) -> Todo`, with defaults `uuid="t1"`, `title="Task"`, `status="incomplete"`, `start="Anytime"`, everything else empty or `None`
  - `factories.snapshot(todos=(), projects=(), **overrides) -> Snapshot`, with default `area_ids={"Work": "A-W", "Home": "A-H"}`, all five default tags present, `token_present=True`

- [x] **Step 1: Write failing tests**

  ```python
  def test_area_resolves_through_heading_project():
      rec = {"uuid": "t", "type": "to-do", "title": "x", "status": "incomplete", "start": "Anytime",
             "heading": "H1", "heading_title": "Tasks", "notes": "", "start_date": None,
             "deadline": None, "stop_date": None}
      t = to_todo(rec, projects={"P1": {"uuid": "P1", "title": "Trip", "area": "A-H"}},
                  headings={"H1": {"uuid": "H1", "project": "P1"}}, today_ids=set())
      assert (t.area_id, t.project_id, t.project_title) == ("A-H", "P1", "Trip")

  def test_own_area_wins_and_stop_date_parsed(): ...   # "2026-09-21 09:23:07" -> datetime(2026, 9, 21, 9, 23, 7)
  def test_missing_tags_key_means_no_tags(): ...       # records without "tags" -> tags == ()
  def test_colors_of_matches_nfd_tag(): ...            # unicodedata.normalize("NFD", "🟢") -> ["green"]
  def test_colors_of_multiple(): ...                   # two color tags plus "Errand" -> ["yellow", "green"]
  def test_read_snapshot_wraps_permission_error(monkeypatch):
      monkeypatch.setattr(things, "tasks", Mock(side_effect=PermissionError("Operation not permitted")))
      with pytest.raises(ThingsUnavailable, match="Full Disk Access"):
          read_snapshot(date(2026, 9, 21))

  @pytest.mark.live
  def test_read_snapshot_live():
      s = read_snapshot(date.today() - timedelta(days=14))
      assert s.token_present and s.area_ids
  ```

- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement `model.py` and `things_read.py`**

  `read_snapshot` uses:
  - `things.tasks(type="to-do", status="incomplete")`
  - `things.tasks(type="to-do", status="completed", stop_date=f">={completed_since.isoformat()}")`
  - `things.tasks(type="project", status=None)` (all projects, for resolution)
  - `things.tasks(type="heading", status=None)`
  - `things.areas()`, `things.tags()`, `things.today()`, `things.inbox()`, `things.token()`

  `Snapshot.projects` keeps only projects with status `incomplete`. `sqlite3.Error` and `PermissionError` are wrapped in `ThingsUnavailable`, and the message names the macOS setting: "grant Full Disk Access to the Python that runs solve-it-grid".
- [x] **Step 4:** Run the tests. Expected: PASS. Run once with `-m live`, which should also pass.
- [x] **Step 5: Commit**: `git commit -m "Add domain model and Things reader"`

### Task 3: Weeks and scoring

**Files:**
- Create: `engine/src/solve_it_grid/weeks.py`, `engine/src/solve_it_grid/scoring.py`
- Test: `engine/tests/test_weeks.py`, `engine/tests/test_scoring.py`

**Interfaces:**
- Consumes: `Todo`, `colors_of`, `Config`, `Goal`.
- Produces:
  - `weeks.Week(start: date)` (frozen), with `.end -> date` (exclusive, start + 7 days), `.contains(d: date) -> bool`, `.prev() -> Week` and `.next() -> Week`
  - `weeks.week_of(d: date) -> Week`
  - `weeks.ended_at(week: Week) -> datetime`: aware local midnight at `week.end`
  - `scoring.Unit(id: str, goal_id: str, label: str, color: Color, done: bool)` (frozen)
  - `scoring.WeekScore(week: Week, counts: dict[str, int], units: tuple[Unit, ...], hit: bool, red_done: int, uncolored_completed: tuple[str, ...], multi_color: tuple[str, ...])`
  - `scoring.unit_ids(goals: tuple[Goal, ...]) -> list[str]`
  - `scoring.score_week(todos: Iterable[Todo], cfg: Config, area_ids: dict[str, str], week: Week) -> WeekScore`

- [x] **Step 1: Write failing tests** (use `factories.todo` with `status="completed"` and `stop=`):

  ```python
  def test_unit_ids(cfg): assert unit_ids(cfg.goals) == ["yellow-work", "yellow-home", "green-1", "green-2"]
  def test_week_of_sunday_and_monday():
      assert week_of(date(2026, 10, 4)).start == date(2026, 9, 28)
      assert week_of(date(2026, 10, 5)).start == date(2026, 10, 5)
  def test_boundary_sunday_2359_counts_monday_0000_does_not(): ...
  def test_yellow_counts_by_area(): ...           # Work yellow -> yellow-work done, yellow-home not
  def test_yellow_without_area_counts_nowhere(): ...
  def test_green_counts_any_area_including_none(): ...
  def test_excluded_statuses_and_markers(): ...   # canceled, incomplete, red, blue, unscored, uncolored -> counts 0
  def test_red_done_counted_not_scored(): ...     # 3 red completions -> red_done == 3, units unchanged
  def test_multi_color_flagged_not_counted(): ... # -> multi_color == ("t1",), counts["yellow-work"] == 0
  def test_uncolored_completed_listed(): ...
  def test_third_green_earns_nothing(): ...       # counts["green"] == 3, 4 units total, green-2 done
  def test_hit_only_when_all_units_done(): ...
  def test_dst_weekend_is_ordinary():             # 2026-11-01 01:30 local (DST ends) -> week 2026-10-26
  ```

  `cfg` is a fixture: `load_config(repo_root() / "config.example.toml")`.
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement.**
  - A goal's area key maps to `area_ids[cfg.areas[key]]`. `"any"` matches any area, including none.
  - A to-do counts only when `colors_of` returns exactly one color.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5: Commit**: `git commit -m "Add week math and goal scoring"`

### Task 4: State store

**Files:**
- Create: `engine/src/solve_it_grid/state.py`
- Test: `engine/tests/test_state.py`

**Interfaces:**
- Produces: `state.Chip(id: int, week_start: date, unit: str, color: str, awarded_at: datetime, acked_at: datetime | None)` and `state.FrozenWeek(week_start: date, units_done: int, units_total: int, hit: bool, chips: int)`.
- `state.StateStore(path: Path)` creates the schema on open (tables `chips` with UNIQUE(week_start, unit), `weeks`, `checkins`, `checkin_ticks`, `runs`, `meta`). Methods:

  | Area | Methods |
  |---|---|
  | chips | `award_chip(week_start, unit, color, now) -> Chip \| None` (None when that week and unit were already awarded), `pending_chips() -> list[Chip]`, `ack_chips(ids: list[int] \| None, now) -> int` (None acks all pending), `total_earned() -> int` (acked chips, which mirror the done jar), `chips_for_week(week_start) -> list[Chip]` |
  | weeks | `freeze_week(fw: FrozenWeek, now)`, `is_frozen(week_start) -> bool`, `frozen_weeks() -> list[FrozenWeek]` (ascending) |
  | check-in | `set_checkin_done(day, now)`, `checkin_done(day) -> bool`, `tick(day, step, now)`, `ticks(day) -> set[str]` |
  | runs | `record_run(kind: str, ok: bool, error: str \| None, now)`, `failure_streak(kind) -> tuple[int, datetime \| None, str \| None]` (count since the last ok run, first failure time, last error) |
  | meta | `get_meta(key) -> str \| None`, `set_meta(key, value)` |

- [x] **Step 1: Write failing tests**
  - `test_award_is_idempotent`
  - `test_ack_all_and_some`
  - `test_total_earned_counts_acked_only`
  - `test_freeze_roundtrip_and_order`
  - `test_checkin_done_and_ticks_are_per_day`
  - `test_failure_streak_resets_on_success` (fail, fail, ok, fail gives count 1, whose first-failure time is the last failure's time)
  - `test_meta_roundtrip`
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement** with stdlib `sqlite3`. Datetimes are stored as ISO strings.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5: Commit**: `git commit -m "Add SQLite state store"`

### Task 5: Progress: chips, freezing, streaks

**Files:**
- Create: `engine/src/solve_it_grid/progress.py`
- Test: `engine/tests/test_progress.py`

**Interfaces:**
- Consumes: `Snapshot`, `score_week`, `week_of`, `ended_at`, `StateStore`, `Chip`, `FrozenWeek`.
- Produces:
  - `progress.Progress(current: WeekScore, new_chips: list[Chip], streak: int, best_streak: int, history: list[FrozenWeek], last_week: FrozenWeek | None)`
  - `progress.scoring_cutoff(state, cfg, today: date) -> date`: the start of the earliest unfrozen week at or after `cfg.start_week`, never later than the current week's start. It's used as `read_snapshot(completed_since=...)`.
  - `progress.refresh(snapshot, state, cfg, now: datetime) -> Progress`

- [x] **Step 1: Write failing tests** (`cfg.start_week = date(2026, 9, 21)` via `dataclasses.replace`)

  ```python
  def test_chip_awarded_once_when_unit_fills(): ...        # refresh twice -> 1 chip, new_chips empty the 2nd time
  def test_green_units_award_in_order(): ...               # 1 green -> green-1 chip only
  def test_chip_not_revoked_when_completion_disappears(): ...
  def test_late_colored_completion_awards_past_unfrozen_week(): ...  # Monday 10:00, last week's item newly colored
  def test_freezes_past_week_when_all_colored(): ...
  def test_waits_to_freeze_while_uncolored_then_freezes_after_48h(): ...  # Tue 23:59 not frozen, Wed 00:00 frozen
  def test_frozen_week_ignores_late_synced_completion():
      # week of 9/21 frozen with 2 units; a yellow completed 9/24 appears later -> no chip, FrozenWeek unchanged
  def test_weeks_before_start_week_ignored(): ...
  def test_streak_and_best(): ...                          # frozen hits H,H,miss,H,H + current hit -> streak 3, best 3
  def test_current_week_not_hit_does_not_break_streak(): ... # H,H + current open -> streak 2
  def test_history_is_last_12_frozen_weeks(): ...
  ```

- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement `refresh`**
  - Score every unfrozen week from `scoring_cutoff` to the current week, and award chips for its done units.
  - Freeze each past week that meets the freeze rule. `FrozenWeek.chips` counts the chips awarded for that week.
  - Build the streak from the frozen hits, plus unfrozen past weeks at their live score, plus the current week only if it's hit.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5: Commit**: `git commit -m "Award chips, freeze weeks, compute streaks"`

### Task 6: Daily check-in

**Files:**
- Create: `engine/src/solve_it_grid/checkin.py`
- Test: `engine/tests/test_checkin.py`

**Interfaces:**
- Consumes: `Snapshot`, `colors_of`, `Config`.
- Produces:
  - `checkin.Link(label: str, url: str)`, `checkin.Step(id: str, label: str, done: bool, links: tuple[Link, ...])`, `checkin.Checkin(workday: bool, due: bool, done: bool, steps: tuple[Step, ...])`
  - `checkin.is_workday(day: date, country: str) -> bool`
  - `checkin.show_url(**params: str) -> str`: `things:///show?...` with `urllib.parse.quote`, and never an auth token
  - `checkin.evaluate_checkin(snapshot, cfg, now: datetime, done: bool, ticks: set[str]) -> Checkin`
- Step ids, labels and done-rules, in order:

  | id | label | done when |
  |---|---|---|
  | `inbox` | Inbox is empty | inbox is empty |
  | `red` | A red is in Today | a red is in Today, or no reds are open |
  | `yellow` | A yellow is in Today | a yellow is in Today |
  | `green` | A green is in Today | a green is in Today |
  | `areas` | Give N items an area | only present when N > 0, so never done |
  | `fix` | Fix N items | only present when there are empty titles or multi-color items |
  | `someday-review` | Review Someday | Mondays only, done when `"someday-review" in ticks` |

- [x] **Step 1: Write failing tests**

  ```python
  def test_workdays():
      assert is_workday(date(2026, 11, 25), "US")
      assert not is_workday(date(2026, 11, 26), "US")   # Thanksgiving
      assert not is_workday(date(2026, 10, 3), "US")    # Saturday
  def test_due_from_checkin_time_until_done(): ...      # Thu 08:59 not due; 09:00 due; done=True not due
  def test_not_due_on_holiday(): ...
  def test_red_step_done_when_no_open_reds(): ...
  def test_color_steps_need_item_in_today(): ...
  def test_area_step_excludes_inbox_and_lists_items(): ...  # links show?id=<uuid> labelled with title
  def test_fix_step_for_empty_title_and_multi_color(): ...
  def test_someday_review_only_on_monday_and_tickable(): ...
  def test_tag_link_is_encoded():
      assert show_url(query="🟢") == "things:///show?query=%F0%9F%9F%A2"
  ```

- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement.** Use `holidays.country_holidays(country)`. A to-do "needs an area" when it's open, not in the Inbox, and has `area_id is None` and `project_id is None`. Projects with no area count too.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5: Commit**: `git commit -m "Add daily check-in evaluation"`

### Task 7: Status, health and the status CLI

**Files:**
- Create: `engine/src/solve_it_grid/status.py`, `engine/src/solve_it_grid/cli.py`
- Test: `engine/tests/test_status.py`, `engine/tests/test_cli.py`

**Interfaces:**
- Consumes: `read_snapshot`, `ThingsUnavailable`, `refresh`, `scoring_cutoff`, `evaluate_checkin`, `StateStore`, `load_config`, `config_path`.
- Produces:
  - `status.health_errors(snapshot, state, cfg, now) -> list[dict]`: each item is `{"source": str, "message": str, "since": str | None}`
  - `status.build_status(snapshot, state, cfg, now) -> dict`: the exact JSON shape in the spec's `solve-it-grid status` section
  - `status.render_text(status: dict) -> str`
  - `cli.main(argv: list[str] | None = None) -> int`, with subcommands `status [--json]`, `chip ack (ID... | all)`, `checkin done`, `checkin tick STEP`
- Health errors, in this order, with this exact copy:

  | source | when | message |
  |---|---|---|
  | `setup` | a configured tag is missing | `Missing Things tags: <names>. Run solve-it-grid setup.` |
  | `setup` | a configured area title is not in Things | `Things area '<title>' not found. Check [areas] in config.toml.` |
  | `setup` | no token | `Things URLs are off. Enable them in Things > Settings > General.` |
  | `categorizer` | meta `review_applied_at` unset | `First review pending. Run solve-it-grid categorize --dry-run, then solve-it-grid categorize --apply-review.` |
  | `categorizer` | failure streak ≥ `failure_threshold` | the last error, with `since` set to the first failure |

- [x] **Step 1: Write failing tests**

  ```python
  def test_status_shape(): ...          # keys: generated_at, week{start,end,hit}, units[4], red_done, chips{pending,total_earned},
                                        # streak{current,best}, checkin{workday,due,done,steps}, last_week, history, health{ok,errors}
  def test_missing_tag_reported(): ...
  def test_missing_area_reported(): ...  # cfg.areas["work"] = "Work" but snapshot.area_ids has only "👨‍💻 Work"
  def test_token_off_reported(): ...
  def test_review_pending_reported(): ...
  def test_categorizer_streak_reported_with_since(): ...
  def test_health_ok_when_clean(): ...
  def test_render_text_mentions_pending_chip(): ...   # "Move a yellow chip" appears
  def test_cli_status_json(monkeypatch, capsys): ...  # read_snapshot patched; stdout parses as JSON; exit 0
  def test_cli_status_things_unavailable_exits_1(monkeypatch, capsys): ...  # message on stderr
  def test_cli_chip_ack_all(): ...
  def test_cli_checkin_done_and_tick(): ...
  ```

- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement.**
  - `solve-it-grid status` loads config from `config_path()`. If the file is missing, it prints `Run solve-it-grid setup first.` and exits 2.
  - It opens `StateStore(app_dir() / "state.db")`, calls `read_snapshot(scoring_cutoff(...))`, then `build_status`.
  - The text rendering is plain, one line per unit, the pending chips, the check-in steps, and any health errors.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5: Commit**: `git commit -m "Add solve-it-grid status, chip ack and check-in commands"`

### Task 8: Things writer and `solve-it-grid setup`

**Files:**
- Create: `engine/src/solve_it_grid/things_write.py`, `engine/src/solve_it_grid/setup_cmd.py`, `launchd/com.github.timfurlong.solve-it-grid.categorize.plist`
- Modify: `engine/src/solve_it_grid/cli.py` (add `setup [--no-agent]`)
- Test: `engine/tests/test_things_write.py`, `engine/tests/test_setup.py`

**Interfaces:**
- Produces:
  - `things_write.ThingsWriter` (Protocol): `add_tag(uuid: str, tag: str) -> None`, `set_todo_area(uuid: str, area_id: str) -> None`, `set_project_area(uuid: str, area_id: str) -> None`
  - `things_write.UrlSchemeWriter(run=subprocess.run, url=things.url)`: runs `["/usr/bin/open", "-g", url]` with `check=True`
    - add tag: `url(uuid, command="update", **{"add-tags": tag})`
    - to-do area: `url(uuid, command="update", **{"list-id": area_id})`
    - project area: `url(uuid, command="update-project", **{"area-id": area_id})`
  - `things_write.ensure_tags(names: list[str], run=subprocess.run) -> list[str]`: runs one `osascript` that creates each missing tag, and returns the created names
  - `setup_cmd.run_setup(home: Path, repo: Path, now: datetime, *, ensure_tags_fn, install_agent: bool, run=subprocess.run) -> list[str]` (messages)
- The plist template has placeholders `__CLI__`, `__HOME__` and `__LOGDIR__`.
  - `ProgramArguments`: `[__CLI__, "categorize"]`
  - `StartInterval` 600, `RunAtLoad` true
  - stdout and stderr go to `__LOGDIR__/categorize.out.log` and `categorize.err.log`
  - `EnvironmentVariables.PATH`: `/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:__HOME__/.local/bin`

- [x] **Step 1: Write failing tests**
  - `test_add_tag_opens_update_url_in_background`: the fake `url` returns `"things:///update?id=T1&add-tags=X&auth-token=SECRET"`. Assert the argv equals `["/usr/bin/open", "-g", that_url]`.
  - `test_project_area_uses_update_project`
  - `test_writer_errors_never_include_token`: `run` raises `CalledProcessError` whose `cmd` contains the URL. The re-raised `ThingsWriteError` message excludes `SECRET`.
  - `test_ensure_tags_escapes_quotes`
  - `test_setup_writes_config_once`: sets `start_week` to the Monday of `now`, `paths.rubric` to `repo/rubric.md`, and `paths.claude` via `shutil.which("claude")`, falling back to `~/.local/bin/claude`. A second run leaves an edited config untouched.
  - `test_setup_renders_plist_and_bootstraps`: the argv includes `launchctl bootstrap gui/<uid> <plist>`, preceded by a `bootout` whose failure is ignored.
  - `test_setup_no_agent_skips_launchctl`
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement.** `ThingsWriteError` wraps process errors with a token-free message. `solve-it-grid setup` prints each message and ends by reporting the area check (configured titles vs. Things) and the token check.
- [x] **Step 4:** Run the tests. Expected: PASS. Commit: `git commit -m "Add Things writer and solve-it-grid setup"`
- [x] **Step 5: GATE. Live setup.**
  1. Ask the user: "OK to run `solve-it-grid setup --no-agent`? It creates the five color tags in Things and writes config.toml to Application Support."
  2. On yes, run `uv tool install --editable ./engine`, then `solve-it-grid setup --no-agent`.
  3. Edit `[areas]` in the real config to the user's actual area titles.
  4. Confirm `solve-it-grid status` reports no `setup` errors. Only the "First review pending" error should remain.
- [x] **Step 6: GATE. Verify URL-scheme writes on a completed to-do.** This settles the spec's open risk.
  1. Ask the user to name one to-do completed this week that may receive a color tag.
  2. Call `UrlSchemeWriter().add_tag(uuid, "🟡")` (or the color the user picks).
  3. Wait 2 s, then re-read the item with `things.get(uuid)` and check the tag landed.
  4. **If it did not land:** add `AppleScriptWriter.add_tag`, which uses `tell application "Things3"` to append to `tag names` of `to do id`, and select it for completed to-dos in `UrlSchemeWriter.add_tag` via a `completed: bool` parameter. Add a unit test for the selection, re-verify live, and commit.
  5. Record the outcome in this plan under the step.

  **Outcome (2026-09-29):** `update` with `add-tags` works on completed to-dos. The tag landed on a to-do completed the week before, and its status stayed completed. No AppleScript fallback needed.

### Task 9: Rubric, prompt and classifier

**Files:**
- Create: `rubric.md`, `engine/src/solve_it_grid/prompt.py`, `engine/src/solve_it_grid/classifier.py`
- Test: `engine/tests/test_prompt.py`, `engine/tests/test_classifier.py`

**Interfaces:**
- Consumes: `Todo`, `Project`, `Color`.
- Produces:
  - `prompt.WorkItem(uuid: str, kind: Literal["to-do","project"], needs_color: bool, needs_area: bool, payload: dict)` (frozen)
    - `payload` keys: `uuid, kind, title, notes (first 300 chars), project, heading, area, deadline, start, status, needs`
  - `prompt.work_item_from_todo(t: Todo, area_titles: dict[str, str], needs_color: bool, needs_area: bool) -> WorkItem`
  - `prompt.work_item_from_project(p: Project) -> WorkItem`
  - `prompt.OUTPUT_SCHEMA: dict`: an object with `items[]` of `{uuid: string, color: enum[red,yellow,green,blue,unscored] | null, area: enum[work,home] | null, reason: string}`, all required
  - `prompt.build_system_prompt(rubric: str, local: str | None) -> str`
  - `prompt.build_user_message(items: list[WorkItem]) -> str`: the JSON `{"items": [payload, ...]}`
  - `classifier.Assignment(uuid: str, color: Color | None, area: Literal["work","home"] | None, reason: str)` (frozen)
  - `classifier.ClassifierError(Exception)`
  - `classifier.ClaudeClassifier(claude_path: Path, model: str, system_prompt: str, timeout: int, cwd: Path, run=subprocess.run)`, with `.classify(items: list[WorkItem]) -> list[dict]` (raw `items` from `structured_output`)
  - `classifier.validate(items: list[WorkItem], raw: list[dict]) -> tuple[list[Assignment], list[tuple[str, str]]]`: returns (valid, skipped as (uuid, reason))

- [x] **Step 1: Write `rubric.md`.** It contains:
  - the grid table from the spec
  - the five markers with the spec's classification rules, word for word
  - the rule that `area` is `work` or `home` only when asked (`needs` contains `area`), and `null` when unsure
  - the rule that `color` is `null` only for projects
  - one generic example per marker, plus one work green

  No personal to-dos.
- [x] **Step 2: Write failing tests**

  ```python
  def test_argv_is_pinned(tmp_path):
      run = Mock(return_value=CompletedProcess([], 0, stdout=json.dumps(
          {"is_error": False, "structured_output": {"items": []}}), stderr=""))
      ClaudeClassifier(Path("/c"), "claude-haiku-4-5-20251001", "SYS", 60, tmp_path, run=run).classify([item()])
      argv = run.call_args.args[0]
      assert argv[:14] == ["/c", "-p", "--model", "claude-haiku-4-5-20251001", "--tools", "",
                           "--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands",
                           "--no-session-persistence", "--output-format", "json", "--json-schema"]
      assert argv[-2:] == ["--system-prompt", "SYS"] and "--bare" not in argv
      assert json.loads(run.call_args.kwargs["input"])["items"][0]["uuid"] == "t1"

  def test_is_error_raises(): ...        # {"is_error": true, "result": "Not logged in"} -> ClassifierError("Not logged in")
  def test_timeout_raises(): ...         # TimeoutExpired -> ClassifierError("claude timed out after 60s")
  def test_nonzero_exit_raises_with_stderr_tail(): ...
  def test_validate_filters_bad_answers():
      # requested t1 (needs color), t2 (needs color+area), t3; raw answers: t1 ok, t1 duplicate (ignored),
      # t2 color "purple", t9 unknown, t3 missing -> valid [t1]; skipped {t2: "invalid color", t9: "not requested",
      # t3: "no answer"}
  def test_validate_requires_color_when_needed(): ...
  def test_notes_trimmed_to_300(): ...
  def test_system_prompt_appends_local_examples(): ...
  ```

- [x] **Step 3:** Run the tests. Expected: FAIL.
- [x] **Step 4: Implement.** `classify` passes `input=build_user_message(items)`, `capture_output=True`, `text=True`, `timeout=timeout` and `cwd=cwd`.
- [x] **Step 5:** Run the tests. Expected: PASS.
- [x] **Step 6: Live check (reads Things, calls Haiku, no writes).** Build `WorkItem`s for 5 real open to-dos, call `classify`, and confirm that `validate` accepts every answer. No GATE is needed because nothing is written.
- [x] **Step 7: Commit**: `git commit -m "Add rubric, prompt building and Claude classifier"`

### Task 10: Categorize orchestrator

**Files:**
- Create: `engine/src/solve_it_grid/categorize.py`
- Modify: `engine/src/solve_it_grid/cli.py` (add `categorize`)
- Test: `engine/tests/test_categorize.py`

**Interfaces:**
- Consumes: `Snapshot`, `read_snapshot`, `ThingsUnavailable`, `colors_of`, `WorkItem`, `work_item_from_*`, `ClaudeClassifier`, `validate`, `Assignment`, `ClassifierError`, `ThingsWriter`, `ThingsWriteError`, `StateStore`, `week_of`.
- Produces:
  - `categorize.select_work(snapshot, cfg, today: date) -> list[WorkItem]`
  - `categorize.CategorizeResult(requested: int, applied: list[Assignment], skipped: list[tuple[str, str]], unverified: list[str])`
  - `categorize.AlreadyRunning(Exception)`, `categorize.NotReviewed(Exception)`
  - `categorize.run_lock(path: Path)` (a context manager; `fcntl.flock` with `LOCK_EX | LOCK_NB`)
  - `categorize.apply_assignments(work, assignments, snapshot, writer, cfg) -> list[Assignment]`
  - `categorize.run_categorize(*, read, writer, classifier, state, cfg, now, log_path, sleep=time.sleep, require_review=True) -> CategorizeResult`
- Scope rules (from the spec):
  - A to-do needs a color when it has no color tag and is either open, or completed with `stop` in the current or previous week. Canceled to-dos and empty titles are never selected.
  - A to-do needs an area when `area_id is None and project_id is None`, and it is either open and not in the Inbox, or completed within that window.
  - An open project with no area needs an area.

- [x] **Step 1: Write failing tests**

  ```python
  def test_select_work_scope(): ...              # one case per rule above, incl. inbox color-only and project area-only
  def test_no_work_skips_claude_and_records_ok(): ...
  def test_batches_by_batch_size(): ...          # 60 items -> classify called with 25, 25, 10
  def test_applies_tag_and_area_names(): ...     # green + work -> add_tag(uuid, "🟢"), set_todo_area(uuid, "A-W")
  def test_classifier_error_records_failed_run_and_writes_nothing(): ...
  def test_things_unavailable_records_failed_run_with_fda_hint(): ...
  def test_write_error_skips_item_and_continues(): ...
  def test_unverified_writes_reported(): ...     # re-read snapshot still lacks the tag -> uuid in unverified
  def test_log_line_per_applied(): ...           # categorize.log.jsonl: ts, uuid, title, color, area, reason, model
  def test_refuses_before_first_review(): ...    # require_review and no meta -> NotReviewed, no classify call
  def test_lock_prevents_overlap(tmp_path): ...
  ```

- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement.**
  - `run_categorize` reads with `completed_since = week_of(today).prev().start`, selects the work, classifies in batches, validates, and applies. It then waits `sleep(2)`, re-reads, fills `unverified`, logs, and records the run.
  - Any `ClassifierError` or `ThingsUnavailable` records `ok=False` and re-raises.
  - CLI `solve-it-grid categorize` prints `requested N, applied N, skipped N, unverified N`. It exits 0 on `AlreadyRunning` and `NotReviewed` (printing why) and exits 1 on a recorded failure.
- [x] **Step 4:** Run the tests. Expected: PASS.
- [x] **Step 5: Commit**: `git commit -m "Add categorize orchestrator"`

### Task 11: First-run review, golden set and eval

**Files:**
- Create: `engine/src/solve_it_grid/review.py`
- Modify: `engine/src/solve_it_grid/cli.py` (add `categorize --dry-run`, `categorize --apply-review [PATH]`, `eval`)
- Test: `engine/tests/test_review.py`

**Interfaces:**
- Consumes: `select_work`, `ClaudeClassifier`, `validate`, `apply_assignments`, `StateStore`, `WorkItem`, `Assignment`.
- Produces:
  - `review.write_review(work: list[WorkItem], assignments: list[Assignment], home: Path) -> Path`
    - writes `home/review.tsv` with columns `uuid, kind, needs, title, color, area, reason`
    - writes `home/review.items.jsonl` with the payloads
  - `review.read_review(path: Path) -> list[Assignment]`: raises `ValueError(f"line {n}: invalid color 'x'")`
  - `review.apply_review(path, *, read, writer, state, cfg, now, golden_path, log_path) -> CategorizeResult`
  - `review.EvalReport(total: int, agree: int, per_color: dict[str, tuple[int, int]], disagreements: list[dict])`
  - `review.run_eval(classifier, golden_path, batch_size) -> EvalReport` and `review.render_eval(report) -> str`
- `golden.jsonl` row: `{"item": <payload>, "color": <color|null>, "area": <area|null>}`.

- [x] **Step 1: Write failing tests**
  - `test_dry_run_writes_review_and_never_writes_things`
  - `test_apply_review_uses_edited_color` (the TSV row changed from yellow to green, so `add_tag` gets the green tag)
  - `test_apply_review_skips_items_colored_since_dry_run`
  - `test_apply_review_appends_golden_and_sets_meta` (`review_applied_at` is set)
  - `test_read_review_reports_bad_line`
  - `test_eval_agreement_math` (4 golden rows, classifier agrees on 3, giving `agree == 3` with the disagreement listed)
- [x] **Step 2:** Run the tests. Expected: FAIL.
- [x] **Step 3: Implement.** `--dry-run` classifies the full scope (no review gate), writes the review files, and prints the table plus the file path. `--apply-review` defaults to `app_dir()/review.tsv`.
- [x] **Step 4:** Run the tests. Expected: PASS. Commit: `git commit -m "Add first-run review, golden set and eval"`

### Task 11b: First-review feedback (added during execution)

The first dry run was reviewed in Notion. These changes came out of it and were made before any write to Things.

- [x] **Classifier model:** `sonnet` alias in `config.example.toml`, with extended thinking off in `ClaudeClassifier` (`MAX_THINKING_TOKENS=0`). Test: `test_thinking_disabled_for_speed`.
- [x] **Real list names:** `model.list_name(todo, today)` returns Inbox, Today, Anytime, Upcoming or Someday (Upcoming = Someday with a future start date). The prompt payload carries `list` and `scheduled` instead of `start`. `work_item_from_todo` takes `today`. Tests: `test_list_name_*`, `test_todo_payload_and_notes_trimmed_to_300`.
- [x] **No blue from the classifier:** `prompt.CLASSIFIER_COLORS = ("red", "yellow", "green", "unscored")` drives the schema enum and `validate`. Test: `test_validate_rejects_blue`.
- [x] **Check-in affirmations:** manual steps `today-reviewed` ("Today's list is reviewed") and `colors-reviewed` ("Colors look right") after the color steps. `checkin.MANUAL_STEPS` is the single list `solve-it-grid checkin tick` accepts. Tests: `test_review_affirmations_are_manual_ticks`, `test_cli_checkin_tick_accepts_review_affirmations`.
- [x] **Rubric:** green is active fun; interesting work is yellow; red includes Upcoming dates within about three days with outside consequences. Spec and README updated to match.
- [x] **Re-run the dry run with Sonnet** and layer the user's Notion corrections on top (`review.corrections.json` in Application Support), then show the user only the differences. Outcome: Sonnet matched 12 of 13 corrections; 3 other colors changed and were approved.
- [x] **Verification backoff:** `categorize.verify_writes` re-reads after 2, 4 and 8 s. A fixed 2 s check flagged 3 of 48 real writes that landed moments later. Tests: `test_verification_retries_while_things_catches_up`, `test_verification_gives_up_after_retries`.

### Task 12: Live rollout

**Files:** none in the repo (records the outcome in this plan).

- [x] **Step 1:** Run `solve-it-grid categorize --dry-run`, which only reads. Show the user the table from `review.tsv`, grouped by color.
- [x] **Step 2:** Collect the user's corrections in chat and edit `review.tsv` to match. Read the file back to the user.
- [x] **Step 3: GATE.** Ask "OK to write these colors and areas to Things?" On yes, run `solve-it-grid categorize --apply-review`, then `solve-it-grid status`. Confirm there are no health errors and that the colored counts match Things.
- [x] **Step 4: GATE.** Ask "OK to install the launchd agent (runs every 10 minutes)?" On yes, run `solve-it-grid setup` (with the agent) and then `launchctl kickstart -k gui/$(id -u)/com.github.timfurlong.solve-it-grid.categorize`.
- [x] **Step 5:** Check `categorize.err.log` and `solve-it-grid status`.
  - If the error mentions Full Disk Access or "Operation not permitted", tell the user to add the resolved Python binary (`readlink -f ~/.local/share/uv/tools/solve-it-grid/bin/python`) under System Settings > Privacy & Security > Full Disk Access, then kickstart again.
  - Done means one successful scheduled run is recorded (`requested 0, applied 0` is fine).
- [x] **Step 6:** Run `solve-it-grid eval` and record the baseline agreement in this plan.

  **Outcome (2026-09-29):** 48 colors and 4 areas written, confirmed in Things. The launchd agent's first scheduled run succeeded without Full Disk Access. `solve-it-grid eval` baseline: 47/49 (95%). Both misses were completed incidents judged as of today, so `rubric.md` gained a rule to judge completed to-dos as of when the work happened, giving 48/49 (97%). The remaining miss (a completed investigation the user rated yellow for low priority) needs priority context the model doesn't have.

### Task 13: `/things` skill coloring

**Files:**
- Modify: `~/.claude/skills/things/SKILL.md` (outside the repo, so there is no repo commit)

- [x] **Step 1: GATE.** Show the user the proposed diff and ask before editing:
  - Add `### 2b. Pick a color` after "Determine the area". It reads `/Users/timfurlong/code/solve-it-grid/rubric.md` and `~/Library/Application Support/solve-it-grid/rubric.local.md` (if present), chooses exactly one color tag, and passes it in `tags` on `add_todo`.
  - When merging into an existing to-do that already has a color tag, keep it.
  - One new row in "Common mistakes": "Adding a to-do without a color tag. Pick one from the rubric. The categorizer is only the backstop."
- [x] **Step 2:** On yes, apply the edit.
- [x] **Step 3: GATE.** Ask whether to verify by creating a real test to-do. (Skipped at the user's choice: the first real `/things` add shows the color in its confirmation line.) If yes, create one through the skill, confirm it has exactly one color tag, then ask whether to delete it (the user deletes it in Things).

### Task 14: README, license and spec sync

**Files:**
- Create: `README.md`, `LICENSE`
- Modify: `docs/specs/2026-09-28-solve-it-grid-design.md` (only if the build diverged)

- [x] **Step 1: Write `LICENSE`** (MIT, "Copyright (c) 2026 Tim Furlong").
- [x] **Step 2: Write `README.md`** in this order:
  1. What it is (credit and link the Solve It Grid page)
  2. How it works (4 bullets)
  3. Requirements: macOS, Things 3 with Things URLs enabled, Claude Code CLI logged in, uv
  4. Install (`uv tool install --editable ./engine`, then `solve-it-grid setup`)
  5. First review (dry run, then apply)
  6. Daily use (`solve-it-grid status`, `solve-it-grid chip ack`, `solve-it-grid checkin done`)
  7. Commands
  8. Privacy: to-do titles and notes are sent to Claude for classification, and all state stays in Application Support
  9. Full Disk Access note
  10. License

  Describe only what exists: no roadmap, no alternatives.
- [x] **Step 3:** Diff the spec against what was built (CLI flags, file names, JSON keys, the Task 8 Step 6 outcome) and correct the spec wherever it's now wrong.
- [x] **Step 4: Public-readiness check.** `git grep -nIiE "gmail|auth-token=[A-Za-z0-9]|@(gmail|icloud)\.com"` returns nothing. No real to-do titles appear in the repo (`git grep -nI` for 3 titles from `golden.jsonl` returns nothing).
- [x] **Step 5: Commit**: `git commit -m "Add README and license; sync spec with the build"`

### Task 15: Phase 2 readiness

**Files:**
- Modify: `docs/specs/2026-09-28-solve-it-grid-design.md` (menu bar sections), if needed

- [x] **Step 1:** Run `solve-it-grid status --json` against real data and compare it key by key with the spec's `solve-it-grid status` contract and the menu bar sections (icon states, popover rows, error state triggers). Fix any mismatch in the spec so the phase 2 plan can be written from it directly.
- [x] **Step 2:** List for the user anything phase 1 learned that changes phase 2 (for example, how long status takes to run, since the app polls every 60 s). Commit any spec edits: `git commit -m "Sync spec menu bar contract with solve-it-grid status"`

  **Outcome (2026-09-29):** `solve-it-grid status --json` against real data runs in about 0.2 s, so 60 s polling is cheap. The contract gained `manual` on each check-in step (the app renders manual steps as checkboxes) and `week_start` on each pending chip (so a leftover chip from last week isn't matched to this week's unit). The spec's popover now shows the two review affirmations.
