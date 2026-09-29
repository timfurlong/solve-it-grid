# Solve It Grid for Things

A small reward system for [Things 3](https://culturedcode.com/things/), built around the ADHD [Solve It Grid](https://www.thecenterforadhd.com/adhd-energy-balance-solve-it-grid/). Every to-do gets a grid color, and each week a small quota of yellow and green to-dos earns physical poker chips that you move from one jar to another the moment you earn them.

It's built for one person's setup (a Mac, Things 3, and a Claude subscription), but it's small and readable if you want to adapt it.

## How it works

- **Colors.** Every to-do gets one tag: 🔴 Red (urgent, not fun), 🟡 Yellow (necessary, dull), 🟢 Green (active fun), 🔵 Blue (passive downtime), or ⚪ Unscored (packing-list entries and other non-tasks). Claude (Sonnet, through the Claude Code CLI) assigns them every 10 minutes, and never proposes blue. Anything you tag by hand is left alone.
- **Weekly goal.** 1 work yellow, 1 home yellow, and 2 greens. That's four units, and each unit earns a chip the moment it's done. Red is never scored: it gets done anyway.
- **Chips.** Two jars on the desk, one of yellow and green chips to earn and one for chips you've earned. When `sig status` says to move a chip, move it, then run `sig chip ack`.
- **Daily check-in.** On workdays from 9:00: empty the Inbox, put a red, a yellow and a green in Today, confirm Today and the colors look right, and fix any to-do with a missing area or a broken tag.

## Requirements

- macOS
- Things 3, with Things URLs enabled (Things > Settings > General > Enable Things URLs)
- [Claude Code](https://claude.com/claude-code) installed and logged in (`claude` on your PATH)
- [uv](https://docs.astral.sh/uv/)

## Install

```bash
git clone https://github.com/timfurlong/solve-it-grid.git
cd solve-it-grid
uv tool install --editable ./engine
sig setup --no-agent
```

`sig setup` writes `~/Library/Application Support/solve-it-grid/config.toml`, creates the five color tags in Things, and checks that your areas and Things URLs are in place. Edit `[areas]` in the config so the titles match your Things areas exactly, emoji included.

## First review

Nothing is written to Things until you've reviewed the first batch.

```bash
sig categorize --dry-run        # proposals go to review.tsv in Application Support
# edit the color and area columns of review.tsv
sig categorize --apply-review   # writes them to Things and saves them as your golden set
sig setup                       # installs the launchd agent that categorizes every 10 minutes
```

`sig eval` scores Claude against your golden set. To tune it, edit `rubric.md`, or add your own examples to `rubric.local.md` in Application Support.

## Daily use

```bash
sig status            # this week's units, chips to move, and today's check-in
sig chip ack all      # after moving chips to the done jar
sig checkin done      # after the morning check-in
```

## Commands

| Command | What it does |
|---|---|
| `sig setup [--no-agent]` | config, color tags, launchd agent |
| `sig status [--json]` | week progress, chips, check-in, health |
| `sig categorize [--dry-run \| --apply-review [PATH]]` | color and file to-dos |
| `sig eval` | classifier agreement with your golden set |
| `sig chip ack <id...\|all>` | confirm chips were moved |
| `sig checkin done` / `sig checkin tick <step>` | check-in bookkeeping (`today-reviewed`, `colors-reviewed`, `someday-review`) |

## Privacy

To-do titles, notes (the first 300 characters), project and heading names are sent to Claude for classification. Everything else stays on your Mac, in `~/Library/Application Support/solve-it-grid/`: the config, the state database, the classification log, and your golden set. The Things URL token is read from the Things database when needed and is never stored or logged.

## Full Disk Access

The launchd agent reads the Things database from Things' app container. If `categorize.err.log` in Application Support says "Operation not permitted", add the Python that runs `sig` to System Settings > Privacy & Security > Full Disk Access. You can find it with:

```bash
readlink -f ~/.local/share/uv/tools/solve-it-grid/bin/python
```

## License

MIT
