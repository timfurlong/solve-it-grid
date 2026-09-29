# Development

## Layout

```
engine/               Python package `solve_it_grid` (uv), the `solve-it-grid` CLI
menubar/              Swift package: SolveItGridCore (decisions, tested) and SolveItGrid (AppKit shell)
launchd/              categorizer agent plist template
rubric.md             grid definitions and classification rules for the prompt
config.example.toml   default config, copied into place by `solve-it-grid setup`
docs/specs/           the design spec
docs/plans/           the implementation plans each phase was built from
```

## Engine

```bash
cd engine
uv run pytest -q
uv run ruff check .
```

Tests never touch the real Things database or run `open`, `osascript`, `launchctl` or `claude`. The one exception is marked `live` and deselected by default. Run it with `uv run pytest -m live` to smoke-test against your own Things database (read-only).

All user data goes through `app_dir()`, which honors `$SOLVE_IT_GRID_HOME`, so you can point a dev copy of the CLI at a scratch directory.

## Menu bar app

```bash
cd menubar
swift test
scripts/build-app.sh            # builds and signs build/Solve It Grid.app
scripts/build-app.sh --install  # also copies it to ~/Applications and launches it
```

Every decision (icon state, chip board, notification plan, copy) lives in `SolveItGridCore`, which is Foundation-only and unit tested against `status --json` fixtures. `SolveItGrid` is a thin AppKit shell around it.

To check the layout without screen-recording permission, render the popover and history window to PNGs in light and dark mode:

```bash
"build/Solve It Grid.app/Contents/MacOS/SolveItGrid" --snapshot /tmp/sig-snapshots
```

Add `--status <file.json>` to render a saved status instead of the live one. The README screenshots are rendered from `Tests/SolveItGridCoreTests/Fixtures/status-thursday.json`, and the cover image from [`docs/assets/cover.html`](assets/cover.html).

## Contributing

This started as a tool for one person's setup, so some choices (two areas, the default goals, US holidays) reflect that, though most are configurable in `config.toml`. Issues and pull requests are welcome.
