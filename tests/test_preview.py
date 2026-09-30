"""O36: preview.sh manages a live preview of the epic head, and merge-task.sh stops it around setup.

    preview.sh start|stop|restart|status [--surface <name>] [--worktree <path>]

The preview is read from the `## Surfaces` table of `<worktree>/.claude/workflow/config.md`
(columns: Surface, Entry point, Test drives it by, Person looks by, Automated check, Preview start,
Ready when, Restart when changed, Cannot show). `Preview start` is a shell command run in the
worktree; `Ready when` is a shell command that exits 0 once the preview is up; `Restart when
changed` is a comma-separated list of repo paths. The pid file is
`<git common dir>/pad-preview/<surface>.pid`. Last output line: `PREVIEW <state> <surface>`.

The fixture preview is a bash loop that writes a counter to a beat file every 0.2 s, at most 150
times, so a leaked process ends by itself; every test stops its preview in a `finally`.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from conftest import git
from test_merge_task import _commit, _last, _merge

HEADER = (
    "| Surface | Entry point | Test drives it by | Person looks by | Automated check "
    "| Preview start | Ready when | Restart when changed | Cannot show |"
)
SEP = "|---|---|---|---|---|---|---|---|---|"


def _row(name: str, start: str, ready: str, restart: str) -> str:
    cells = [f"`{name}`", "`http://localhost:1`", "`curl`", "`browser`", "`true`",
             f"`{start}`" if start else "", f"`{ready}`" if ready else "",
             f"`{restart}`" if restart else "", "`nothing`"]
    return "| " + " | ".join(cells) + " |"


def _config(rows: list[str]) -> str:
    table = "\n".join([HEADER, SEP, *rows])
    return f"# Config\n\n## Surfaces\n\nThe places.\n\n{table}\n\n## Review\n\n- x\n"


def _app(beat: Path, ready: Path) -> tuple[str, str]:
    """(Preview start, Ready when) for a preview that becomes ready after about a second."""
    start = (
        f"rm -f {ready.as_posix()}; sleep 1; touch {ready.as_posix()}; i=0; "
        f"while [ $i -lt 150 ]; do i=$((i+1)); echo $i > {beat.as_posix()}; sleep 0.2; done"
    )
    return start, f"test -f {ready.as_posix()}"


def _wt_with_config(repo: Path, worktree, name: str, rows: list[str]) -> Path:
    wt = worktree(repo, name)
    _commit(wt, {".claude/workflow/config.md": _config(rows)}, "config")
    return wt


def _preview(run_script, repo: Path, verb: str, wt: Path, surface: str | None = "web"):
    args = [verb]
    if surface:
        args += ["--surface", surface]
    args += ["--worktree", wt.as_posix()]
    return run_script("preview.sh", *args, cwd=repo)


def _pidfile(repo: Path, surface: str = "web") -> Path:
    return repo / ".git" / "pad-preview" / f"{surface}.pid"


def _beating(beat: Path) -> bool:
    """True when the preview process is writing its beat file."""
    if not beat.exists():
        return False
    first = beat.read_text().strip()
    deadline = time.time() + 5
    while time.time() < deadline:
        time.sleep(0.5)
        if beat.read_text().strip() != first:
            return True
    return False


def _still(beat: Path) -> bool:
    """True when the beat file stops changing over 1.5 s (the preview process is gone)."""
    first = beat.read_text().strip() if beat.exists() else ""
    time.sleep(1.5)
    return (beat.read_text().strip() if beat.exists() else "") == first


@pytest.fixture
def surface(tmp_path, repo, worktree, run_script):
    """A worktree whose config has a `web` preview; stops it after the test whatever happened."""
    beat, ready = tmp_path / "beat", tmp_path / "ready"
    start, ready_when = _app(beat, ready)
    wt = _wt_with_config(repo, worktree, "epic", [_row("web", start, ready_when, "server.conf")])
    try:
        yield wt, beat, ready
    finally:
        _preview(run_script, repo, "stop", wt)


def test_start_waits_for_ready_when_and_reports_running(repo, surface, run_script):
    wt, beat, ready = surface
    r = _preview(run_script, repo, "start", wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "PREVIEW running web"
    assert ready.exists(), "start returned before Ready when was true"
    assert _pidfile(repo).is_file()
    assert _beating(beat)


def test_status_reports_running_then_stopped(repo, surface, run_script):
    wt, _, _ = surface
    _preview(run_script, repo, "start", wt)
    r = _preview(run_script, repo, "status", wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "PREVIEW running web"
    _preview(run_script, repo, "stop", wt)
    r = _preview(run_script, repo, "status", wt)
    assert _last(r) == "PREVIEW stopped web"


def test_stop_ends_the_preview_process_and_removes_the_pid_file(repo, surface, run_script):
    wt, beat, _ = surface
    _preview(run_script, repo, "start", wt)
    r = _preview(run_script, repo, "stop", wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "PREVIEW stopped web"
    assert not _pidfile(repo).exists()
    assert _still(beat), "the preview kept running after stop"


def test_stop_when_nothing_runs_still_exits_zero(repo, surface, run_script):
    wt, _, _ = surface
    r = _preview(run_script, repo, "stop", wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "PREVIEW stopped web"


def test_restart_replaces_the_process_and_waits_until_ready(repo, surface, run_script):
    wt, beat, ready = surface
    _preview(run_script, repo, "start", wt)
    old = _pidfile(repo).read_text()
    r = _preview(run_script, repo, "restart", wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "PREVIEW running web"
    assert ready.exists()
    assert _pidfile(repo).read_text() != old
    assert _beating(beat)


def test_a_surface_with_no_preview_is_a_noop_that_exits_zero(repo, worktree, run_script):
    wt = _wt_with_config(repo, worktree, "epic", [_row("docs", "", "", "")])
    for verb in ("start", "stop", "restart", "status"):
        r = _preview(run_script, repo, verb, wt, surface="docs")
        assert r.returncode == 0, f"{verb}: {r.stdout}{r.stderr}"
    pid_dir = repo / ".git" / "pad-preview"
    assert not pid_dir.exists() or not any(pid_dir.iterdir())


# merge-task.sh ------------------------------------------------------------------------------------

GATE = 'grep -q "X = 1" src/impl.py'


def _epic_with_preview(repo, worktree, tmp_path):
    beat, ready = tmp_path / "beat", tmp_path / "ready"
    start, ready_when = _app(beat, ready)
    wt = _wt_with_config(repo, worktree, "epic", [_row("web", start, ready_when, "server.conf")])
    git("push", "-q", "-u", "origin", "epic", cwd=wt)
    return wt, git("rev-parse", "HEAD", cwd=wt), beat


def _task_touching(repo, worktree, epic_head: str, files: dict[str, str]):
    wt = worktree(repo, "task")
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    red = _commit(wt, {"tests/test_new.py": "def test_new():\n    assert False\n"},
                  "test(T-1): O1 [red]")
    head = _commit(wt, {"src/impl.py": "X = 1\n", **files}, "feat(T-1): impl")
    return red, head


def test_merge_touching_a_restart_trigger_stops_the_preview_before_setup_and_starts_it_after(
        repo, worktree, run_script, tmp_path):
    epic_wt, epic_head, beat = _epic_with_preview(repo, worktree, tmp_path)
    red, head = _task_touching(repo, worktree, epic_head,
                               {"package.json": "{}\n", "server.conf": "port=1\n"})
    marker = tmp_path / "setup-saw-preview-stopped"
    pid = _pidfile(repo).as_posix()
    try:
        assert _preview(run_script, repo, "start", epic_wt).returncode == 0
        r = _merge(run_script, repo, epic_wt, red, head, gate=GATE,
                   extra=("--setup", f"test ! -e {pid} && touch {marker.as_posix()}"))
        assert r.returncode == 0, r.stdout + r.stderr
        assert _last(r).startswith("MERGED "), r.stdout
        assert marker.exists(), "setup ran while the preview was still up"
        assert _last(_preview(run_script, repo, "status", epic_wt)) == "PREVIEW running web"
        assert _beating(beat)
    finally:
        _preview(run_script, repo, "stop", epic_wt)


def test_merge_touching_no_restart_trigger_leaves_the_preview_running_through_setup(
        repo, worktree, run_script, tmp_path):
    epic_wt, epic_head, _ = _epic_with_preview(repo, worktree, tmp_path)
    red, head = _task_touching(repo, worktree, epic_head, {"package.json": "{}\n"})
    marker = tmp_path / "setup-saw-preview-running"
    pid = _pidfile(repo).as_posix()
    try:
        assert _preview(run_script, repo, "start", epic_wt).returncode == 0
        old = _pidfile(repo).read_text()
        r = _merge(run_script, repo, epic_wt, red, head, gate=GATE,
                   extra=("--setup", f"test -e {pid} && touch {marker.as_posix()}"))
        assert r.returncode == 0, r.stdout + r.stderr
        assert _last(r).startswith("MERGED "), r.stdout
        assert marker.exists(), "the preview was stopped though no trigger changed"
        assert _pidfile(repo).read_text() == old
    finally:
        _preview(run_script, repo, "stop", epic_wt)


def test_merge_does_not_start_a_preview_that_was_not_running(
        repo, worktree, run_script, tmp_path):
    epic_wt, epic_head, _ = _epic_with_preview(repo, worktree, tmp_path)
    red, head = _task_touching(repo, worktree, epic_head,
                               {"package.json": "{}\n", "server.conf": "port=1\n"})
    try:
        r = _merge(run_script, repo, epic_wt, red, head, gate=GATE, extra=("--setup", "true"))
        assert r.returncode == 0, r.stdout + r.stderr
        assert _last(r).startswith("MERGED "), r.stdout
        assert not _pidfile(repo).exists()
        assert _last(_preview(run_script, repo, "status", epic_wt)) == "PREVIEW stopped web"
    finally:
        _preview(run_script, repo, "stop", epic_wt)


def _native_app(beat: Path, ready: Path) -> tuple[str, str]:
    """A preview whose server is a native (non-shell) grandchild: Python under a bash wrapper.

    On Git Bash for Windows, `kill` on the wrapper's pid does not reach a native child like this
    one (vite's node.exe in practice), so it kept serving after `stop`.
    """
    py = Path(sys.executable).as_posix()
    script = beat.parent / "native_app.py"
    script.write_text(
        "import time, pathlib\n"
        f"b = pathlib.Path({str(beat)!r})\n"
        f"pathlib.Path({str(ready)!r}).touch()\n"
        "for i in range(150):\n"
        "    b.write_text(str(i)); time.sleep(0.2)\n",
        encoding="utf-8",
    )
    return f"{py} {script.as_posix()}; true", f"test -f {ready.as_posix()}"


def test_stop_ends_a_native_grandchild_of_the_preview_shell(tmp_path, repo, worktree, run_script):
    beat, ready = tmp_path / "nbeat", tmp_path / "nready"
    start, ready_when = _native_app(beat, ready)
    wt = _wt_with_config(repo, worktree, "epic", [_row("web", start, ready_when, "")])
    try:
        r = _preview(run_script, repo, "start", wt)
        assert _last(r) == "PREVIEW running web", r.stdout + r.stderr
        assert _beating(beat)
        r = _preview(run_script, repo, "stop", wt)
        assert _last(r) == "PREVIEW stopped web", r.stdout + r.stderr
        assert _still(beat), "the native server kept running after stop"
    finally:
        _preview(run_script, repo, "stop", wt)


def test_stop_on_windows_kills_the_process_tree_with_taskkill(
    tmp_path, repo, surface, run_script
):
    """On MSYS/Cygwin, stop runs `taskkill //PID <winpid> //T //F` before the POSIX kill."""
    wt, beat, _ = surface
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    log = tmp_path / "taskkill.log"
    (stubs / "uname").write_text(
        "#!/usr/bin/env bash\necho MINGW64_NT-10.0-19045\n", encoding="utf-8", newline="\n"
    )
    (stubs / "taskkill").write_text(
        f'#!/usr/bin/env bash\necho "$*" >> "{log.as_posix()}"\n', encoding="utf-8", newline="\n"
    )
    for f in stubs.iterdir():
        f.chmod(0o755)
    _preview(run_script, repo, "start", wt)
    r = run_script(
        "preview.sh", "stop", "--surface", "web", "--worktree", wt.as_posix(), cwd=repo,
        env={"PATH": str(stubs) + os.pathsep + os.environ["PATH"]},
    )
    assert _last(r) == "PREVIEW stopped web", r.stdout + r.stderr
    assert log.is_file(), "taskkill was not called on a Windows host"
    args = log.read_text().split()
    assert "//T" in args and "//F" in args, args
    assert args[args.index("//PID") + 1].isdigit(), args
    assert _still(beat)
