"""`sig setup`: config, color tags and the launchd agent."""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from sig.config import load_config
from sig.weeks import week_of

LABEL = "com.github.timfurlong.solve-it-grid.categorize"


def _write_config(home: Path, repo: Path, now: datetime, which) -> str:
    path = home / "config.toml"
    if path.exists():
        return f"Kept existing {path}"
    claude = which("claude") or str(Path.home() / ".local" / "bin" / "claude")
    text = (repo / "config.example.toml").read_text(encoding="utf-8")
    text = text.replace('start_week = ""', f'start_week = "{week_of(now.date()).start.isoformat()}"', 1)
    text = text.replace('rubric = ""', f'rubric = "{repo / "rubric.md"}"', 1)
    text = text.replace('claude = ""', f'claude = "{claude}"', 1)
    path.write_text(text, encoding="utf-8")
    return f"Wrote {path}"


def _install_agent(home: Path, repo: Path, run, which, agents_dir: Path) -> str:
    sig = which("sig") or str(Path.home() / ".local" / "bin" / "sig")
    template = (repo / "launchd" / f"{LABEL}.plist").read_text(encoding="utf-8")
    plist = (template.replace("__SIG__", escape(sig)).replace("__LOGDIR__", escape(str(home)))
             .replace("__HOME__", escape(str(Path.home()))))
    agents_dir.mkdir(parents=True, exist_ok=True)
    target = agents_dir / f"{LABEL}.plist"
    target.write_text(plist, encoding="utf-8")
    domain = f"gui/{os.getuid()}"
    run(["launchctl", "bootout", f"{domain}/{LABEL}"], check=False, capture_output=True)
    run(["launchctl", "bootstrap", domain, str(target)], check=True, capture_output=True)
    return f"Installed launchd agent {target} (runs every 10 minutes)"


def run_setup(home: Path, repo: Path, now: datetime, *, ensure_tags_fn, install_agent: bool,
              run=subprocess.run, which=shutil.which,
              agents_dir: Path | None = None) -> list[str]:
    agents_dir = agents_dir or Path.home() / "Library" / "LaunchAgents"
    messages = [_write_config(home, repo, now, which)]
    cfg = load_config(home / "config.toml")
    created = ensure_tags_fn(list(cfg.tags.values()))
    messages.append(f"Created tags: {', '.join(created)}" if created else "All color tags already exist")
    if install_agent:
        messages.append(_install_agent(home, repo, run, which, agents_dir))
    return messages
