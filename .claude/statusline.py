"""Status line: model, checkout, context, cost, and epic progress.

Claude Code pipes session JSON to stdin and prints the first line of stdout under the prompt.
Installed per machine by /setup-workflow, which writes an absolute path into
`.claude/settings.local.json` (gitignored) — this file is committed, that setting is not.

Run it by hand with a sample payload:

    echo '{"model":{"display_name":"Opus"}}' | python3 .claude/statusline.py

Keep it fast and silent: it runs on every event, and anything it prints to stderr is invisible.
Missing fields are normal before the first API response, so every read has a fallback.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

BAR = "▁▂▃▄▅▆▇█"

# How old a progress snapshot may be before the status line stops presenting it as live.
SNAPSHOT_STALE_HOURS = 6

# How much of a session transcript to read when looking for the worktrees it has been in.
TAIL_BYTES = 262144


def get(d: object, *path: str, default: object = None) -> object:
    for key in path:
        if not isinstance(d, dict) or key not in d:
            return default
        d = d[key]
    return d if d is not None else default


def branch(cwd: Path, fallback: str) -> str:
    """The checked-out branch, or the worktree name the payload already knows."""
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        name = out.stdout.strip()
        if name:
            return name
    except (OSError, subprocess.SubprocessError):
        pass
    return fallback


def work_dir(start: Path, *children: str) -> Path | None:
    """The nearest `.work/` at or above `start` holding one of `children`.

    `.work/` is untracked, so every checkout has its own and they hold different things: the
    epic worktree's has the run log, the main checkout's has the tickets. Walking up while
    asking for a specific child finds the right one from either place, and finds nothing in a
    project that does not use this workflow.
    """
    for base in (start, *start.parents):
        work = base / ".work"
        try:
            if any((work / child).exists() for child in children):
                return work
        except OSError:
            return None
    return None


def run_progress(project_dir: Path) -> str:
    """`PROJ-70 2/5` for the newest /batch-implement run log, when there is one.

    The run log is append-only, one line per task outcome, so counting lines is enough.
    """
    work = work_dir(project_dir, "runs")
    if work is None:
        return ""
    runs = sorted(
        work.glob("runs/*/progress.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        return ""
    log = runs[0]
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    done = len(re.findall(r"^\S+: done\b", text, re.MULTILINE))
    stuck = len(re.findall(r"^\S+: (failed|blocked)\b", text, re.MULTILINE))
    total = len(re.findall(r"^\S+: (done|failed|blocked|doing)\b", text, re.MULTILINE))
    if not total:
        return ""
    label = f"{log.parent.name} {done}/{total}"
    return f"{label} ✗{stuck}" if stuck else label


def ticket_status(ticket: Path) -> str:
    """The `status:` field from a local ticket's frontmatter, or "" if it has none."""
    try:
        with ticket.open(encoding="utf-8", errors="replace") as handle:
            for line in islice(handle, 12):
                match = re.match(r"status:\s*(\S+)", line)
                if match:
                    return match.group(1)
    except OSError:
        pass
    return ""


def worktree_name(path: str) -> str:
    """The `<name>` in `.../.claude/worktrees/<name>/...`, or "" for a path elsewhere.

    Separators are normalised through chr(92) rather than a regex class, which is where the
    Windows-path bugs live; doubled separators from JSON-escaped paths drop out as empty parts.
    """
    parts = [part for part in path.replace(chr(92), "/").split("/") if part]
    for index in range(len(parts) - 1, 1, -1):
        if parts[index - 1] == "worktrees" and parts[index - 2] == ".claude":
            return parts[index]
    return ""


def owns(key: str, names: list[str]) -> bool:
    """True when one of the session's names is this epic key, or `<key>-<slug>`."""
    return any(name == key or name.startswith(key + "-") for name in names)


def add_name(names: list[str], candidate: object) -> None:
    """Append a candidate epic name, without `epic/` and without duplicates."""
    text = str(candidate or "")
    if text.startswith("epic/"):
        text = text[len("epic/"):]
    if text and text not in names:
        names.append(text)


def session_names(payload: dict, cwd: Path, head: str) -> list[str]:
    """What epic this session could be on, from what it costs nothing to know.

    Its place in the tree and its branch. Both are immediate when the session moves, and both
    are momentary: an orchestrator hops between the epic worktree, the repo root and its agents'
    worktrees, which is what the pin and the transcript below are for.
    """
    names: list[str] = []
    add_name(names, worktree_name(str(cwd)))
    add_name(names, head)
    add_name(names, get(payload, "worktree", "name"))
    add_name(names, get(payload, "workspace", "git_worktree"))
    return names


def transcript_names(transcript: str) -> list[str]:
    """Worktrees this session's own cwd has been in, most recent first.

    Only the harness-written `"cwd"` fields count. Matching free text instead would claim any
    worktree the session merely mentioned — a session that talked about `worktrees/E2` is not a
    session working on E2.
    """
    try:
        with open(transcript, "rb") as handle:
            handle.seek(0, 2)
            start = max(0, handle.tell() - TAIL_BYTES)
            handle.seek(start)
            tail = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    names: list[str] = []
    for match in re.finditer(r'"cwd":"([^"]*)"', tail):
        add_name(names, worktree_name(match.group(1)))
    names.reverse()
    return names


def pin_path(payload: dict) -> Path | None:
    """Where this session's last answer is remembered. Under TEMP, never in the repo."""
    session = str(get(payload, "session_id", default="") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session):
        return None
    return Path(tempfile.gettempdir()) / "claude-statusline-epic" / session


def from_tickets(tickets: Path, names: list[str]) -> tuple[str, str] | None:
    """`(E2, "E2 5/7 ▶T6")` counted straight from this session's epic, `local` adapter.

    A finished epic still counts: in its own worktree `E2 7/7` is the news, not noise.
    """
    try:
        entries = sorted(tickets.iterdir())
    except OSError:
        return None
    for name in names:
        for epic in entries:
            if not owns(epic.name, [name]) or not epic.is_dir():
                continue
            done, total, doing = 0, 0, []
            for task in sorted(epic.glob(epic.name + "-T*.md")):
                status = ticket_status(task)
                if not status:
                    continue
                total += 1
                if status == "done":
                    done += 1
                elif status == "doing":
                    doing.append(task.stem.rsplit("-", 1)[-1])
            if not total:
                continue
            label = f"{epic.name} {done}/{total}"
            return epic.name, (f"{label} ▶{','.join(doing)}" if doing else label)
    return None


def from_snapshot(path: Path, names: list[str]) -> tuple[str, str] | None:
    """`(PROJ-7, "PROJ-7 4/7 ▶PROJ-12")` from the snapshot `/batch-implement` leaves behind.

    A status line renders on every event, so it may never call a tracker API; the snapshot is
    the only thing it is allowed to read. One older than SNAPSHOT_STALE_HOURS, or carrying no
    timestamp, says so and drops the in-flight task, which by then is not news.
    """
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    if not isinstance(snapshot, dict):
        return None
    epic = str(snapshot.get("epic") or "")
    try:
        done = int(snapshot.get("done", 0))
        total = int(snapshot.get("total", 0))
    except (TypeError, ValueError):
        return None
    if not epic or not total or not owns(epic, names):
        return None
    label = f"{epic} {done}/{total}"
    if stale(snapshot.get("updated")):
        return epic, f"{label} (stale)"
    doing = [str(key) for key in (snapshot.get("doing") or []) if key]
    return epic, (f"{label} ▶{','.join(doing)}" if doing else label)


def stale(updated: object) -> bool:
    """True when a snapshot carries no usable timestamp, or one past the cutoff."""
    try:
        when = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when > timedelta(hours=SNAPSHOT_STALE_HOURS)


def resolve_epic(work: Path, names: list[str]) -> tuple[str, str] | None:
    """The first of `names` that an epic in the ledger answers to, counted."""
    if not names:
        return None
    if (work / "tickets").is_dir():
        return from_tickets(work / "tickets", names)
    return from_snapshot(work / "progress.json", names)


def epic_progress(payload: dict, project_dir: Path, cwd: Path, head: str) -> str:
    """This session's epic, from the ledger, when no run log is speaking.

    Three signals in falling priority: the session's path and branch; the pin, holding what this
    session resolved to last time (empty content means "no epic", so the answer is remembered
    either way); and, only when there is no pin yet, this session's transcript — which is what
    recovers a session that has already left the epic worktree. The transcript is therefore read
    at most once per session, not once per render.
    """
    work = work_dir(project_dir, "tickets", "progress.json")
    if work is None:
        return ""

    names = session_names(payload, cwd, head)
    pin = pin_path(payload)
    pinned = None
    if pin is not None:
        try:
            pinned = pin.read_text(encoding="utf-8").strip()
        except OSError:
            pinned = None
        add_name(names, pinned)

    found = resolve_epic(work, names)
    if found is None and pinned is None:
        transcript = str(get(payload, "transcript_path", default="") or "")
        if transcript:
            for name in transcript_names(transcript):
                add_name(names, name)
            found = resolve_epic(work, names)

    answer = found[0] if found else ""
    if pin is not None and answer != pinned:
        try:
            pin.parent.mkdir(parents=True, exist_ok=True)
            pin.write_text(answer, encoding="utf-8")
        except OSError:
            pass
    return found[1] if found else ""


def main() -> None:
    # Windows consoles default to a codepage that cannot encode the bar glyphs, and an
    # exception here would leave the status line blank with no visible error.
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = Path(str(get(payload, "workspace", "current_dir", default="."))).resolve()
    project_dir = Path(str(get(payload, "workspace", "project_dir", default=cwd)))

    parts = [str(get(payload, "model", "display_name", default="claude"))]
    head = branch(cwd, str(get(payload, "workspace", "git_worktree", default=cwd.name)))
    parts.append(head)

    pct = get(payload, "context_window", "used_percentage", default=0)
    try:
        pct_int = max(0, min(100, int(float(str(pct)))))
    except ValueError:
        pct_int = 0
    parts.append(f"{BAR[min(pct_int * len(BAR) // 100, len(BAR) - 1)]} {pct_int}% ctx")

    cost = get(payload, "cost", "total_cost_usd", default=0)
    try:
        if float(cost) >= 0.01:
            parts.append(f"${float(cost):.2f}")
    except (TypeError, ValueError):
        pass

    if not get(payload, "prompt_cache", "warm", default=True):
        parts.append("cache cold")

    progress = run_progress(project_dir) or epic_progress(payload, project_dir, cwd, head)
    if progress:
        parts.append(progress)

    print(" | ".join(parts))


if __name__ == "__main__":
    main()
