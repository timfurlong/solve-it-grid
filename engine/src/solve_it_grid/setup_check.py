"""Setup problems that make categorizing or freezing unsafe."""

import unicodedata

from solve_it_grid.config import Config
from solve_it_grid.model import Snapshot


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def setup_problems(snapshot: Snapshot, cfg: Config) -> list[str]:
    problems = []
    present = {_nfc(t) for t in snapshot.tag_names}
    missing = [name for name in cfg.tags.values() if _nfc(name) not in present]
    if missing:
        problems.append(f"Missing Things tags: {', '.join(missing)}. Run solve-it-grid setup.")
    for title in cfg.areas.values():
        if title not in snapshot.area_ids:
            problems.append(f"Things area '{title}' not found. Check [areas] in config.toml.")
    if not snapshot.token_present:
        problems.append("Things URLs are off. Enable them in Things > Settings > General.")
    return problems
