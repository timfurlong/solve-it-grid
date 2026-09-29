# Using Solve It Grid

## Colors

Every to-do gets one emoji tag in Things:

| Tag | Color | Means | Scored |
|---|---|---|---|
| 🔴 | red | urgent, not fun: deadlines, incidents, someone waiting on you | never |
| 🟡 | yellow | necessary, dull: chores, admin, errands | yes |
| 🟢 | green | active fun: exercise, friends, hobbies, music | yes |
| 🔵 | blue | passive downtime | never |
| ⚪ | unscored | packing-list entries, shopping-list entries and other non-tasks | never |

Claude (Sonnet, through the Claude Code CLI) assigns colors every 10 minutes and never proposes blue. It also files unfiled to-dos and projects (outside the Inbox) into Work or Home. Anything you tag or file by hand is left alone, and a color never changes once it's assigned.

## The weekly goal and chips

The default goal is 1 work yellow, 1 home yellow and 2 greens. That's four units, and each unit earns a chip the moment it's done. Red is never scored because it gets done anyway. Goals are set in `[[goals]]` in `config.toml`.

When a chip is earned, move one of that color from the to-earn jar to the done jar, then acknowledge it (the menu bar button, or `solve-it-grid chip ack all`). Chips are never taken back, even if a to-do is later uncompleted or recolored.

A week runs Monday to Sunday. Completions made on your phone still count once they sync, for up to 48 hours after the week ends.

## Daily check-in

On workdays (Monday to Friday, minus public holidays) the check-in is due from 9:00. It walks you through:

- Empty the Inbox
- Put a red, a yellow and a green in Today
- Give any unfiled to-do an area, and fix any to-do with an empty title or more than one color
- Confirm Today's list and the colors look right
- On Mondays, review Someday

Most steps tick themselves from live Things data. The review steps are ticked by hand. "Done for today" is always available: the check-in guides rather than polices.

## The menu bar app

The icon is a ring with four segments, one per unit: the yellows on the left (work bottom-left, home top-left) and the greens on the right, like the grid's not-fun and fun columns. A filled segment is done. The center shows what needs you, most important first:

| Center | Meaning |
|---|---|
| orange dot | today's check-in is due |
| pulsing colored dot | a chip is waiting to be moved |
| checkmark | the week is hit |

A red warning triangle replaces the ring when something is wrong: the CLI is missing, the categorizer keeps failing, or setup needs attention. Open the popover for what failed and how to fix it.

The popover shows this week's chips, the check-in and your streak. **History** opens the last 12 weeks.

## Commands

| Command | What it does |
|---|---|
| `solve-it-grid status [--json]` | week progress, chips to move, check-in, health |
| `solve-it-grid chip ack <id...\|all>` | confirm chips were moved to the done jar |
| `solve-it-grid checkin done` | mark today's check-in done |
| `solve-it-grid checkin tick <step>` | tick a manual step (`today-reviewed`, `colors-reviewed`, `someday-review`) |
| `solve-it-grid categorize [--dry-run \| --apply-review [PATH]]` | color and file to-dos now, preview, or apply a reviewed file |
| `solve-it-grid eval` | classifier agreement with your golden set |
| `solve-it-grid setup [--no-agent]` | config, color tags, launchd agent |

## Tuning the classifier

`solve-it-grid eval` scores Claude against your golden set (the colors you confirmed in the first review). To tune it, edit [`rubric.md`](../rubric.md), or add your own examples to `rubric.local.md` in `~/Library/Application Support/solve-it-grid/`, which is never committed.
