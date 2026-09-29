# Solve It Grid for Things: design

- **Date:** 2026-09-28
- **Status:** draft, awaiting review
- **Source framework:** [ADHD Energy Balance: the Solve It Grid](https://www.thecenterforadhd.com/adhd-energy-balance-solve-it-grid/)

## Summary

A personal reward system built on top of Things 3. Every to-do gets a Solve It Grid color. Each week, completing a small quota of yellow and green to-dos earns physical poker chips, moved by hand from one jar to another the moment each one is earned. A macOS menu bar app shows the week's progress at all times and runs a short daily check-in that keeps the Things list planned and tidy.

The system has three jobs:

1. **Balance energy.** Reward the two colors that are easy to neglect: yellow (necessary but dull) and green (fun and energizing).
2. **Reward immediately.** A chip is earned the moment a unit of progress is done, and moving it is a physical act.
3. **Keep Things healthy.** A daily check-in empties the Inbox, puts today's red, yellow and green work in Today, and flags items with missing metadata.

## The grid

The Solve It Grid places activities on two axes, fun and stimulating:

| Color | Fun | Stimulating | Examples | Scored |
|---|---|---|---|---|
| Red | no | yes | deadlines, incidents, someone waiting on you | no |
| Yellow | no | no | chores, admin, errands, appointments to book | yes |
| Green | yes | yes | exercise, socializing, creative hobbies, music, playing with kids | yes |
| Blue | yes | no | passive downtime (TV, scrolling) | no |

Red is never scored. It gets done on its own because it is urgent, and rewarding it would reward crisis mode. Blue rarely appears on a to-do list: the tag exists for manual use, but it is never scored and the categorizer never proposes it.

A fifth marker, **unscored**, covers to-dos that are not standalone tasks: packing-list entries, shopping-list entries, and sub-steps listed under a project heading. Without it, one packing list would satisfy a week of yellow.

## Architecture

Everything runs on the MacBook Pro, where Things, the menu bar and the user are. Things syncs completions from the phone when the laptop wakes, and the reward is only ever seen at the Mac, so nothing needs to run while it sleeps.

```
            ┌──────────────────────────────┐
            │ Things 3 (local SQLite DB)   │
            └──────▲───────────────┬───────┘
     URL scheme    │               │ things.py (read-only)
     (writes)      │               ▼
            ┌──────┴──────────────────────────┐      claude -p (Sonnet)     
 launchd ──►│ engine: `sig` CLI (Python)      │─────► JSON classifier, no tools
  10 min    │  categorize · status · chips    │
            └──────▲───────────────┬──────────┘
                   │ sig chip ack  │ sig status --json
                   │ sig checkin   ▼
            ┌──────┴──────────────────────────┐
            │ menu bar app (SwiftUI)          │──► notifications
            └─────────────────────────────────┘
                         │
                         ▼  "Move a chip"
                  two jars of poker chips (physical)
```

| Component | Responsibility | Depends on |
|---|---|---|
| `engine/` (`sig`) | All logic: reading Things, categorizing, scoring, chips, check-in state, holidays | things.py, `claude` CLI, Things URL scheme, SQLite |
| `menubar/` | Rendering, notifications, snooze timers | `sig` CLI only |
| launchd agent | Runs `sig categorize` every 10 minutes | `sig` |
| `/things` skill (user-level, outside this repo) | Colors to-dos at creation time | `rubric.md` |
| Physical tracker | Two jars and yellow/green poker chips | the user |

The menu bar app never reads Things or the state database directly. Every read goes through `sig status --json` and every write through a `sig` subcommand, so all behavior lives in one tested Python codebase.

## Data model

### Colors are Things tags

Five tags, created once by `sig setup`:

| Marker | Default tag name |
|---|---|
| red | `🔴 Red` |
| yellow | `🟡 Yellow` |
| green | `🟢 Green` |
| blue | `🔵 Blue` |
| unscored | `⚪ Unscored` |

Tag names are configurable. Only to-dos get a color. Projects, headings and checklist items do not.

A to-do with no color tag is uncategorized and is not scored until the categorizer colors it. A to-do with more than one color tag is not scored and is flagged in the check-in.

### Area resolution

A to-do's area is the first of: its own area, its project's area, or its heading's project's area. A to-do with no resolvable area counts toward no area-specific goal.

### Goals and units

Goals live in `config.toml`:

| Goal | Color | Area | Target |
|---|---|---|---|
| `yellow-work` | yellow | Work | 1 |
| `yellow-home` | yellow | Home | 1 |
| `green` | green | any | 2 |

Each point of a target is a **unit**, so the week has four units: work yellow, home yellow, green 1, green 2. Splitting yellow by area enforces a little work/life balance. Green is not split because green means active fun, which almost always lands at home.

- **Counting:** a to-do counts toward a goal when it is completed (not canceled) during the week, has exactly one color tag matching the goal, and resolves to the goal's area. The list it was in (Inbox, Anytime, Someday, a project) does not matter.
- **Week:** Monday 00:00 to Sunday 23:59:59 local time, by completion timestamp.
- **Goal done:** count reaches target. Completions beyond the target earn nothing extra.
- **Week hit:** every goal is done.
- **Streak:** consecutive hit weeks. The current week joins the streak once it is hit.
- **Start:** tracking begins with the week `sig setup` first runs (`start_week` in the config). Earlier weeks are ignored.

### Chips

- One chip per unit, so up to four per week: two yellow, two green.
- A chip is awarded the moment its unit fills. Green 1 fills on the first green completion of the week, green 2 on the second.
- An awarded chip stays **pending** until the user confirms moving it (`sig chip ack`).
- Chips are never revoked, even if a to-do is later uncompleted or recolored.
- A completion colored after its week ended still awards its chip, as long as the week is not frozen yet.

### Week freezing

A past week's result (units filled, hit, chips) is written to the state database and never recomputed once the week **freezes**. A week freezes 48 hours after it ends, which leaves time for completions made on the phone to sync once the Mac wakes and for the categorizer to color them. A week never freezes while `sig status` reports a setup problem (a missing tag or area), because those under-count. Freezing keeps history stable when goals, tags or colors are edited later. Until a week freezes, history shows its live score.

### Storage

All user data lives in `~/Library/Application Support/solve-it-grid/`, never in the repo:

| File | Contents |
|---|---|
| `config.toml` | start week, goals, tag names, area titles, check-in time, categorizer settings, `claude` path |
| `state.db` | SQLite: `chips`, `weeks` (frozen results), `checkins`, `runs` (categorizer run outcomes), `meta` |
| `rubric.local.md` | optional personal examples appended to the classification prompt |
| `review.tsv`, `review.items.jsonl` | the latest dry-run proposals (editable before `--apply-review`) and the item details behind them |
| `golden.jsonl` | user-confirmed colors used by `sig eval` |
| `categorize.log.jsonl` | every assignment: time, uuid, title, color, area, reason, model |

The repo ships `config.example.toml`, and `sig setup` copies it into place. The Things URL-scheme auth token is read from the Things database by things.py when a write needs it (Things > Settings > General > Enable Things URLs must be on). It is never stored, logged or printed.

## Categorizer

### Schedule

A launchd user agent runs `sig categorize` every 10 minutes. It can also be run by hand. A file lock makes an overlapping run exit immediately. When there is nothing to categorize, the run ends without calling Claude. A run also stops, and counts as failed, while `sig status` reports a setup problem, so a renamed tag doesn't send the whole list back to Claude. When the model can't place an item's area, that item is left for the check-in and not asked about again for 24 hours.

### Scope

Each run collects:

1. Open to-dos (Inbox, Today, Anytime, Upcoming, Someday) with no color tag.
2. To-dos completed in the current or previous week with no color tag.
3. To-dos outside the Inbox that have no project and no area, which need an area.
4. Projects with no area, which need an area. To-dos inside a project take the project's area, so the fix goes on the project.

Inbox to-dos get a color but are never filed into an area: the Inbox is the check-in's processing queue. To-dos with an empty title are skipped and flagged in the check-in.

### Classification

- One `claude -p` call per batch of up to 25 items, using the `sonnet` model alias through the locally logged-in Claude Code CLI (subscription auth, no API key). The alias follows the latest Sonnet release, so no code change is needed when a new one ships. Extended thinking is turned off: it made a 10-item batch take about 55 seconds instead of 10.
- The call runs with no tools, no MCP servers, no settings, hooks or plugins, and no user or project `CLAUDE.md`, and requests structured JSON output. The exact CLI flags are pinned in the implementation plan. (`--bare` is not usable because it disables subscription login.)
- Input per item: uuid, title, notes (first 300 characters), project, heading, area, list (Inbox, Today, Anytime, Upcoming or Someday; Things stores Upcoming as Someday plus a start date, so the list is derived), scheduled date, deadline, status.
- Output per item: `{uuid, color, area, reason}`, where `color` is one of `red | yellow | green | unscored` (never blue), and `area` is `work | home | null`. `null` means no area is needed or the model is unsure.
- The prompt is built from `rubric.md` (in the repo: grid definitions and classification rules) plus `rubric.local.md` (personal examples, never committed).

Classification rules in `rubric.md`:

- **Red** means urgency or outside pressure at classification time: a deadline within about three days, an Upcoming to-do scheduled within about three days that carries outside consequences, someone actively waiting, or an incident.
- **Yellow** is a should-do without urgency. Interesting or intellectually engaging work (design, research, spikes, writing for work) is still yellow.
- **Green** is active fun: it takes energy to start but gives energy back, like exercise, socializing, creative hobbies, music, and playing with kids. When in doubt between green and yellow, yellow.
- **Unscored** covers list entries and sub-steps that are not standalone tasks.

### Writing back

- The categorizer never overwrites an existing color tag or area. Manual edits always win, and colors never change after assignment. A yellow does not turn red as its deadline approaches, because that would remove it from the yellow count.
- Writes use the Things URL scheme through `open -g`, so Things never takes focus:
  - to-do: `things:///update?id=<uuid>&auth-token=<token>&add-tags=<tag>[&list-id=<area-id>]`
  - project: `things:///update-project?id=<uuid>&auth-token=<token>&area-id=<area-id>`
- Things applies URL-scheme writes asynchronously, so after writing, the categorizer re-reads the database after 2, 4 and 8 seconds until every write shows up. Any write still missing is reported as unverified and retried on the next run.
- `update` works on completed to-dos too (verified during rollout), so completed and open to-dos use the same write path.

### Validation and failures

Items are skipped (and retried on the next run) when the response has an unknown uuid, an invalid color, or an invalid area. The whole batch is skipped when `claude` exits non-zero, exceeds a 60-second timeout, or returns unparseable output. Each run's outcome is recorded in `runs`. Three consecutive failed runs put the system in the error state (see [Error state](#error-state)).

### First run and tuning

- `sig categorize --dry-run` prints every proposed color and area and saves them to `review.tsv` without writing to Things.
- After the user edits `review.tsv`, `sig categorize --apply-review` writes those colors and areas to Things and saves every reviewed row to `golden.jsonl`.
- Scheduled runs do nothing until a review has been applied once.
- `sig eval` runs the classifier over `golden.jsonl` and reports agreement per color plus the list of disagreements. This is the loop for tuning `rubric.md` and `rubric.local.md`.

## Daily check-in

A workday is Monday to Friday, excluding US federal holidays (computed with the `holidays` Python package). On workdays the check-in is **due** from 9:00 local time until marked done.

The check-in is guided: the popover lists steps and each open step links into Things to do the work there. Most steps check themselves against live Things data. Three are affirmations you tick by hand, because only you can judge them.

| Step | Done when | Link |
|---|---|---|
| Inbox is empty | Inbox has no to-dos | `things:///show?id=inbox` |
| A red is in Today | a red to-do is in Today, or no reds are open | the red tag's list (`things:///show?query=<tag>`) |
| A yellow is in Today | a yellow to-do is in Today | the yellow tag's list (`things:///show?query=<tag>`) |
| A green is in Today | a green to-do is in Today | the green tag's list (`things:///show?query=<tag>`) |
| Give N items an area | no to-do outside the Inbox lacks a resolvable area (shown only when N > 0) | each item by id |
| Fix N items | no empty titles or multi-color items (shown only when N > 0) | each item by id |
| Today's list is reviewed | ticked by hand (`today-reviewed`) | `things:///show?id=today` |
| Colors look right | ticked by hand (`colors-reviewed`) | `things:///show?id=today` |
| Review Someday (Mondays) | ticked by hand (`someday-review`) | `things:///show?id=someday` |

"Done for today" (`sig checkin done`) is always available, whether or not every step is ticked. The check-in guides rather than polices. On Mondays the check-in header also shows last week's result and the streak.

## Menu bar app

A SwiftUI `MenuBarExtra` (window style) that launches at login. It polls `sig status --json` every 60 seconds and whenever the popover opens.

### Icon: ring

A 16-point ring split into four segments. The yellows sit on the right (work top-right, home bottom-right) and the greens on the left, matching the grid's not-fun and fun columns. A filled segment in the color means the unit is done, and a faint segment means it is open.

The center shows the single most important signal, in this priority order:

1. **Check-in due:** an orange dot. Orange is not a grid color, so it can't be mistaken for a red task.
2. **Chip waiting:** a pulsing dot in the chip's color.
3. **Week hit:** a checkmark.
4. Otherwise empty.

### Popover

```
 This week's chips               Sep 28 to Oct 4
   (W)          (H)          (G)          ( )
 Work yellow  Home yellow   Green        Green
 In the jar   Move it now   In the jar   Not yet
 [ I moved the yellow chip                     ]
 • 3 reds finished, not scored

 Today's check-in                         4 left
  ✓ Inbox is empty
  ✓ A red is in Today
  ✓ A yellow is in Today
  ○ A green is in Today                     Show
  ☐ Today's list is reviewed                Show
  ☐ Colors look right                       Show
  ○ Give 1 item an area                  Show it
 [ Snooze 1 hour ]          [ Done for today ]
 ─────────────────────────────────────────────
 3-week streak   14 chips earned         History
```

- The four poker chips are drawn like the physical ones. An earned chip is solid ("In the jar"). A pending chip is solid, lifted and gently animated ("Move it now"). An open unit is a dashed outline ("Not yet"). Animation respects Reduce Motion.
- The acknowledge button appears only while chips are pending and names them ("I moved the yellow chip", "I moved 2 chips"). It acknowledges every pending chip shown.
- Steps with `"manual": true` render as a checkbox the user clicks, which runs `sig checkin tick <id>`. Every other step ticks itself.
- A pending chip belongs to the unit with the same `unit` id only when its `week_start` is the current week. A chip left over from last week shows as its own "Move it now" row.
- **History** opens a small window with the last 12 weeks (units filled, hit or miss, chips) plus the current and best streak.

### Notifications

| Notification | When | Actions |
|---|---|---|
| Check-in | workdays at 9:00, if the check-in is not done | **Start check-in** (opens the popover), **Snooze 1 hour** (repeatable) |
| Chip earned | when a new chip is awarded, e.g. "Home yellow done. Move a yellow chip." | opens the popover |
| Error | when the error state begins, then every 2 hours while it lasts | opens the popover |

Check-in notifications use the time-sensitive interruption level if the app can get that entitlement with local signing. Otherwise they are standard notifications, and setup instructs the user to set the app's notification style to Alerts so they stay on screen until handled.

### Error state

The error state is meant to be hard to ignore. It triggers when `sig status` fails or times out, when the categorizer has failed three runs in a row, or when `sig status` reports a setup problem (missing color tags, an area title not found in Things, Things URLs turned off, or the first review not applied yet). In the error state:

- The ring is replaced by a filled red warning triangle.
- The popover opens with an error banner at the top: what failed, since when, and the likely fix (for example "Claude Code is not logged in: run `claude` in a terminal").
- The last good status stays visible below the banner.
- A notification is posted when the error begins and every 2 hours until it clears.

## `sig` CLI

| Command | Purpose |
|---|---|
| `sig setup [--no-agent]` | create the five tags (AppleScript), write `config.toml` from the example, check areas and the Things URL token, install the launchd agent |
| `sig categorize [--dry-run \| --apply-review [PATH]]` | one categorizer run, a dry run to `review.tsv`, or apply a reviewed file |
| `sig status [--json]` | current week, chips, check-in, hygiene, health, history. Human-readable by default |
| `sig chip ack <id\|all>` | confirm pending chips were moved |
| `sig checkin done` | mark today's check-in done |
| `sig checkin tick <step>` | tick a manual step (`today-reviewed`, `colors-reviewed`, `someday-review`) |
| `sig eval` | score the classifier against `golden.jsonl` |

`sig status --json` is the contract with the menu bar app:

```json
{
  "generated_at": "2026-10-01T10:14:00-06:00",
  "week": {"start": "2026-09-28", "end": "2026-10-04", "hit": false},
  "units": [
    {"id": "yellow-work", "color": "yellow", "label": "Work yellow", "done": true},
    {"id": "yellow-home", "color": "yellow", "label": "Home yellow", "done": true},
    {"id": "green-1", "color": "green", "label": "Green", "done": true},
    {"id": "green-2", "color": "green", "label": "Green", "done": false}
  ],
  "red_done": 3,
  "chips": {
    "pending": [{"id": 57, "week_start": "2026-09-28", "unit": "yellow-home", "color": "yellow",
                 "awarded_at": "2026-10-01T10:12:31-06:00"}],
    "total_earned": 14
  },
  "streak": {"current": 3, "best": 5},
  "checkin": {
    "workday": true, "due": true, "done": false,
    "steps": [{"id": "inbox", "label": "Inbox is empty", "done": true, "manual": false,
               "links": [{"label": "Show", "url": "things:///show?id=inbox"}]}]
  },
  "last_week": {"start": "2026-09-21", "hit": true},
  "history": [{"start": "2026-09-21", "units_done": 4, "hit": true, "chips": 4}],
  "health": {"ok": true, "errors": []}
}
```

## `/things` skill change

The user-level skill at `~/.claude/skills/things/SKILL.md` gains one step in `add`: after choosing the area, choose a color by reading `rubric.md` from this repo (and `rubric.local.md` when present), then pass the color tag on `add_todo`. When merging into an existing to-do that already has a color, keep it. The categorizer backfills anything the skill misses.

## Physical tracker

Two jars on the desk, in view: a **to earn** jar and a **done** jar. It starts with 13 weeks' worth of clay poker chips in the to-earn jar: 26 yellow and 26 green. When the app says to move a chip, move one of that color from the to-earn jar to the done jar, then click the acknowledge button. `total_earned` in the app mirrors the done jar.

## Error handling

| Failure | Behavior |
|---|---|
| `claude` not logged in, errors, times out, bad JSON | batch skipped and retried next run. Three consecutive failures trigger the error state |
| invalid item in model output | that item skipped and retried next run |
| URL-scheme write did not land | logged as a failure for that item, retried next run |
| overlapping categorizer run | exits immediately (file lock) |
| Things closed | reads work (database). Writes launch Things in the background |
| Things database schema change breaks things.py | `sig status` fails, which triggers the error state |
| `sig status` fails or exceeds 10 seconds | menu bar error state, last good status kept |

## Testing

- **Scoring** is a pure function from a list of to-do records to week results, tested with pytest fixtures:
  - week boundaries (Sunday 23:59 vs Monday 00:00, DST changes)
  - area resolution through project and heading
  - red, blue, unscored, canceled and uncategorized items excluded
  - multi-color items flagged
  - units beyond the target earning nothing
- **Chips:** awarded exactly once per unit across repeated runs, never revoked, awarded for late-colored completions before freeze, not after.
- **Freezing:** freezes on complete categorization or at 48 hours. Frozen weeks survive goal and tag edits.
- **Check-in:** step evaluation against fixtures, workday and holiday calendar.
- **Categorizer:** prompt building and response validation against canned `claude` output (subprocess stubbed). Things writes go through an interface with an in-memory fake.
- **Smoke:** `sig status` against the real Things database (read-only).
- **Classifier quality:** `sig eval` against the golden set. This is not part of the test suite.
- **Menu bar app:** unit tests decode `status.json` fixtures and map status to icon state (a pure function). Notification actions are verified by hand.

## Repository

- GitHub: `timfurlong/solve-it-grid`, private at first and kept ready to publish at any time.
- Layout:

  ```
  engine/               Python package `sig` (uv), installed with `uv tool install`
  menubar/              SwiftUI app (Xcode project)
  launchd/              categorizer agent plist template
  rubric.md             grid definitions and classification rules
  config.example.toml   default config
  docs/specs/           final design docs
  docs/explorations/    gitignored: option boards and alternatives
  README.md, LICENSE (MIT)
  ```

- Nothing personal is committed: real to-do titles, logs, the golden set, personal rubric examples, and config all live in Application Support, and the Things token stays in the Things database.
- Docs in the repo describe the final agreed state. Exploration material stays in the gitignored `docs/explorations/`.

## Delivery phases

Each phase gets its own implementation plan.

1. **Engine.**
   - `sig` with setup, categorize, status, chips, check-in and eval.
   - The launchd agent, `rubric.md`, and the `/things` skill change.
   - README and LICENSE.
   - Usable from the terminal on its own: `sig status` shows the week, and chips are acknowledged with `sig chip ack`.
2. **Menu bar app.** The ring icon, popover, history window, notifications and error state, all driven by `sig status --json`.
