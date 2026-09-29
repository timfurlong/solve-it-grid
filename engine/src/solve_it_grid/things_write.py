"""Write colors and areas to Things. URLs carrying the auth token are never logged."""

import subprocess
from typing import Protocol

import things


class ThingsWriteError(Exception):
    pass


class ThingsWriter(Protocol):
    def add_tag(self, uuid: str, tag: str) -> None: ...
    def set_todo_area(self, uuid: str, area_id: str) -> None: ...
    def set_project_area(self, uuid: str, area_id: str) -> None: ...


class UrlSchemeWriter:
    """Opens things:/// update URLs in the background (`open -g`)."""

    def __init__(self, run=subprocess.run, url=things.url):
        self._run = run
        self._url = url

    def _open(self, uuid: str, command: str, **params: str) -> None:
        try:
            url = self._url(uuid, command=command, **params)
        except ValueError:
            raise ThingsWriteError(
                "Things URLs are off. Enable them in Things > Settings > General.") from None
        try:
            self._run(["/usr/bin/open", "-g", url], check=True, capture_output=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            code = getattr(exc, "returncode", None)
            raise ThingsWriteError(f"things:///{command} failed for {uuid} (exit {code})") from None

    def add_tag(self, uuid: str, tag: str) -> None:
        self._open(uuid, "update", **{"add-tags": tag})

    def set_todo_area(self, uuid: str, area_id: str) -> None:
        self._open(uuid, "update", **{"list-id": area_id})

    def set_project_area(self, uuid: str, area_id: str) -> None:
        self._open(uuid, "update-project", **{"area-id": area_id})


def _quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def ensure_tags(names: list[str], run=subprocess.run) -> list[str]:
    """Create any missing Things tags via AppleScript. Returns the names created."""
    blocks = "\n".join(
        f"  if not (exists tag {_quote(n)}) then\n"
        f"    make new tag with properties {{name:{_quote(n)}}}\n"
        f"    set end of created to {_quote(n)}\n"
        f"  end if"
        for n in names
    )
    script = (
        'tell application "Things3"\n  set created to {}\n' + blocks + "\n"
        "  set AppleScript's text item delimiters to linefeed\n"
        "  return created as text\nend tell"
    )
    out = run(["/usr/bin/osascript", "-e", script], check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line.strip()]
