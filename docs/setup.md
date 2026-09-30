# Setup

## Requirements

- macOS 14 or later
- [Things 3](https://culturedcode.com/things/), with Things URLs enabled (Things > Settings > General > Enable Things URLs)
- [Claude Code](https://claude.com/claude-code) installed and logged in (`claude` on your PATH)
- [uv](https://docs.astral.sh/uv/)
- Xcode 16 or later (Swift 6), only for the menu bar app

## Install the CLI

```bash
git clone https://github.com/timfurlong/solve-it-grid.git
cd solve-it-grid
uv tool install --editable ./engine
solve-it-grid setup --no-agent
```

The install is editable because the CLI reads `rubric.md` and `config.example.toml` from the repo, so keep the clone where it is.

`solve-it-grid setup` writes `~/Library/Application Support/solve-it-grid/config.toml`, creates the five color tags in Things, and checks that your areas and Things URLs are in place. Edit `[areas]` in the config so the titles match your Things areas exactly, emoji included. The same file holds the weekly goals, the check-in time and the holiday calendar; every setting is described in [`config.example.toml`](../config.example.toml).

## First review

Nothing is written to Things until you've reviewed the first batch.

```bash
solve-it-grid categorize --dry-run        # proposals go to review.tsv in Application Support
# edit the color and area columns of review.tsv
solve-it-grid categorize --apply-review   # writes them to Things and saves them as your golden set
solve-it-grid setup                       # installs the launchd agent that categorizes every 10 minutes
```

From then on the agent colors new to-dos in the background. Anything you tag by hand is left alone.

## Access to Things' data

The categorizer reads the Things database from Things' app container, which macOS protects.

With the menu bar app installed, the launchd agent runs through it: it starts `Solve It Grid.app/Contents/MacOS/SolveItGrid --categorize`, which runs `solve-it-grid categorize` as its child. macOS then treats the categorizer as Solve It Grid and asks once whether Solve It Grid may access data from other apps. Allow it. `solve-it-grid setup` looks for the app in `~/Applications` and `/Applications`.

Without the app, the agent runs the CLI directly and macOS asks about the Python interpreter instead ("python3.13 would like to access data from other apps"), and that prompt can come back. If `categorize.err.log` in Application Support says "Operation not permitted", add that Python to System Settings > Privacy & Security > Full Disk Access. You can find it with:

```bash
readlink -f ~/.local/share/uv/tools/solve-it-grid/bin/python
```

## Menu bar app

The menu bar app only talks to the `solve-it-grid` CLI, so install that first.

```bash
menubar/scripts/build-app.sh --install
```

That builds `Solve It Grid.app`, signs it (with your Apple Development identity if you have one, otherwise ad-hoc), copies it to `~/Applications` and launches it. An ad-hoc signature changes with every build, so macOS asks about access to Things' data again after each rebuild; an Apple Development identity keeps it stable.

Then run `solve-it-grid setup` again so the background agent runs through the app (see [Access to Things' data](#access-to-things-data)).

On first launch:

- **Allow notifications.** If the prompt doesn't appear or gets dismissed, turn on Allow notifications in System Settings > Notifications > Solve It Grid. Set the alert style to **Persistent** (called Alerts before macOS 26) so the morning check-in stays on screen until you handle it.
- The app adds itself to **Login Items** (System Settings > General > Login Items).

The app, and the agent running through it, run `~/.local/bin/solve-it-grid`. To point them elsewhere:

```bash
defaults write com.github.timfurlong.solve-it-grid cliPath /path/to/solve-it-grid
```

## The physical part

Two jars on the desk, in view: one to earn from and one for chips you've earned. Fill the first with yellow and green poker chips (13 weeks' worth is 26 of each). See [Using Solve It Grid](usage.md) for how chips move.
