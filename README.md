# Solve It Grid for Things

A small reward system for [Things 3](https://culturedcode.com/things/), built around the ADHD [Solve It Grid](https://www.thecenterforadhd.com/adhd-energy-balance-solve-it-grid/). Every to-do gets a grid color, and each week a small quota of yellow and green to-dos earns physical poker chips that you move from one jar to another the moment you earn them.

It's built for one person's setup (a Mac, Things 3, and a Claude subscription), but it's small and readable if you want to adapt it.

## How it works

- **Colors.** Every to-do gets one emoji tag: 🔴 red (urgent, not fun), 🟡 yellow (necessary, dull), 🟢 green (active fun), 🔵 blue (passive downtime), or ⚪ unscored (packing-list entries and other non-tasks). Claude (Sonnet, through the Claude Code CLI) assigns them every 10 minutes, and never proposes blue. Anything you tag by hand is left alone.
- **Weekly goal.** 1 work yellow, 1 home yellow, and 2 greens. That's four units, and each unit earns a chip the moment it's done. Red is never scored: it gets done anyway.
- **Chips.** Two jars on the desk, one of yellow and green chips to earn and one for chips you've earned. When `solve-it-grid status` says to move a chip, move it, then run `solve-it-grid chip ack`.
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
solve-it-grid setup --no-agent
```

`solve-it-grid setup` writes `~/Library/Application Support/solve-it-grid/config.toml`, creates the five color tags in Things, and checks that your areas and Things URLs are in place. Edit `[areas]` in the config so the titles match your Things areas exactly, emoji included.

## First review

Nothing is written to Things until you've reviewed the first batch.

```bash
solve-it-grid categorize --dry-run        # proposals go to review.tsv in Application Support
# edit the color and area columns of review.tsv
solve-it-grid categorize --apply-review   # writes them to Things and saves them as your golden set
solve-it-grid setup                       # installs the launchd agent that categorizes every 10 minutes
```

`solve-it-grid eval` scores Claude against your golden set. To tune it, edit `rubric.md`, or add your own examples to `rubric.local.md` in Application Support.

## Daily use

```bash
solve-it-grid status            # this week's units, chips to move, and today's check-in
solve-it-grid chip ack all      # after moving chips to the done jar
solve-it-grid checkin done      # after the morning check-in
```

## Menu bar app

The menu bar app shows the week as a ring and runs the daily check-in. It only talks to the `solve-it-grid` CLI, so install that first.

```bash
menubar/scripts/build-app.sh --install
```

That builds `Solve It Grid.app`, signs it (with your Apple Development identity if you have one, otherwise ad-hoc), copies it to `~/Applications` and launches it. On first launch:

- **Allow notifications.** If the prompt doesn't appear or gets dismissed, turn on Allow notifications in System Settings > Notifications > Solve It Grid. Set the alert style to **Persistent** (called Alerts before macOS 26) so the morning check-in stays on screen until you handle it.
- The app adds itself to **Login Items** (System Settings > General > Login Items).

**Reading the ring.** Four segments, one per unit: the yellows on the left (work bottom-left, home top-left) and the greens on the right, like the grid's not-fun and fun columns. A filled segment is done. The center shows what needs you, most important first:

| Center | Meaning |
|---|---|
| orange dot | today's check-in is due |
| pulsing colored dot | a chip is waiting to be moved |
| checkmark | the week is hit |

A red warning triangle replaces the ring when something is wrong (the CLI is missing, the categorizer keeps failing, or setup needs attention). Open the popover for what failed and how to fix it.

**Checking the layout.** `"~/Applications/Solve It Grid.app/Contents/MacOS/SolveItGrid" --snapshot <dir>` renders the popover and history window, in light and dark mode, to PNGs and quits. Add `--status <file.json>` to render a saved status instead of the live one.

**CLI location.** The app runs `~/.local/bin/solve-it-grid`. To point it elsewhere:

```bash
defaults write com.github.timfurlong.solve-it-grid cliPath /path/to/solve-it-grid
```

## Commands

| Command | What it does |
|---|---|
| `solve-it-grid setup [--no-agent]` | config, color tags, launchd agent |
| `solve-it-grid status [--json]` | week progress, chips, check-in, health |
| `solve-it-grid categorize [--dry-run \| --apply-review [PATH]]` | color and file to-dos |
| `solve-it-grid eval` | classifier agreement with your golden set |
| `solve-it-grid chip ack <id...\|all>` | confirm chips were moved |
| `solve-it-grid checkin done` / `solve-it-grid checkin tick <step>` | check-in bookkeeping (`today-reviewed`, `colors-reviewed`, `someday-review`) |

## Privacy

To-do titles, notes (the first 300 characters), project and heading names are sent to Claude for classification. Everything else stays on your Mac, in `~/Library/Application Support/solve-it-grid/`: the config, the state database, the classification log, and your golden set. The Things URL token is read from the Things database when needed and is never stored or logged.

## Full Disk Access

The launchd agent reads the Things database from Things' app container. If `categorize.err.log` in Application Support says "Operation not permitted", add the Python that runs `solve-it-grid` to System Settings > Privacy & Security > Full Disk Access. You can find it with:

```bash
readlink -f ~/.local/share/uv/tools/solve-it-grid/bin/python
```

## License

MIT
