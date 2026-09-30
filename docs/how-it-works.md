# How it works

Solve It Grid has two parts: a Python CLI (`engine/`) that holds all the logic, and a SwiftUI menu bar app (`menubar/`) that only ever talks to the CLI. The full design, including the `status --json` contract between them, is in the [design spec](specs/2026-09-28-solve-it-grid-design.md).

```
            ┌──────────────────────────────┐
            │ Things 3 (local SQLite DB)   │
            └──────▲───────────────┬───────┘
     URL scheme    │               │ things.py (read-only)
     (writes)      │               ▼
            ┌──────┴───────────────────────┐    claude -p (Sonnet)
 launchd ──►│ engine: solve-it-grid CLI    │───► JSON classifier, no tools
  10 min    │ categorize · status · chips  │
            └──────▲───────────────┬───────┘
     chip ack,     │               │ status --json
     checkin       │               ▼
            ┌──────┴───────────────────────┐
            │ menu bar app (SwiftUI)       │───► notifications
            └──────────────────────────────┘
                           │
                           ▼  "Move a chip"
                two jars of poker chips (physical)
```

## Reading and writing Things

The engine reads the Things database directly with [things.py](https://github.com/thingsapi/things.py), read-only. Writes go through the Things URL scheme with `open -g`, so Things never takes focus. The URL scheme needs an auth token, which is read from the Things database when a write needs it and is never stored, logged or printed. Things applies URL-scheme writes asynchronously, so the categorizer re-reads the database after each batch to confirm every write landed, and retries anything that didn't on the next run.

## The categorizer

A launchd agent runs `solve-it-grid categorize` every 10 minutes. When the menu bar app is installed, the agent starts the app's executable with `--categorize`, which runs the CLI as its child. macOS then attributes the categorizer's reads of the Things database to Solve It Grid rather than to Python, so it asks for access once, on the app's behalf. Each run collects open and recently completed to-dos with no color tag, plus to-dos and projects that need an area. When there's nothing to do, it ends without calling Claude.

Items go to Claude in batches of up to 25 through `claude -p`, using your logged-in Claude Code subscription (no API key). The call runs with no tools, no MCP servers, no settings or plugins, and no `CLAUDE.md`, and asks for structured JSON back. The prompt is [`rubric.md`](../rubric.md) plus your optional `rubric.local.md`.

The categorizer never overwrites a color or area that's already set, so manual edits always win. Answers for items that weren't asked about, or with an invalid color or area, are dropped and retried next run. Three failed runs in a row put the menu bar app in its error state.

## Scoring and chips

Scoring is a pure function from a snapshot of Things to the week's results: which units are filled, which chips are due, and the check-in's steps. A to-do counts toward a goal when it's completed (not canceled) during the week, has exactly one color tag matching the goal, and resolves to the goal's area through its own area, its project or its heading's project.

Chips and check-in state live in a SQLite database. A finished week's result is frozen 48 hours after it ends, so editing goals, tags or colors later never rewrites history.

## Privacy

To-do titles, notes (the first 300 characters), and project and heading names are sent to Claude for classification. Everything else stays on your Mac, in `~/Library/Application Support/solve-it-grid/`:

| File | Contents |
|---|---|
| `config.toml` | goals, tag names, area titles, check-in time, categorizer settings |
| `state.db` | chips, frozen weeks, check-ins, categorizer runs |
| `categorize.log.jsonl` | every color and area assigned, with Claude's reason |
| `review.tsv`, `golden.jsonl` | your first review and the golden set built from it |
| `rubric.local.md` | optional personal examples for the prompt |

Nothing personal is ever written inside the repo.
