"""O46, O47: rehearse.sh proves the mechanical delivery path, and /setup-workflow ends with it.

    rehearse.sh [--keep]

Run from a set-up repo's main checkout. In detached throwaway worktrees it moves onto the epic
head, makes a trivial red, runs verify-red, makes a trivial green, runs task-submit, merges with
merge-task into a throwaway head, restarts the configured preview, and writes the ledger from a
worktree. It prints `STEP <name> PASS|FAIL <detail>` per step, then `REHEARSAL OK` or
`REHEARSAL FAILED <n>`, and leaves no branches (local or on origin), worktrees or ledger changes.

Step names, in order: move-onto-epic-head, red, verify-red, green, task-submit, merge-task,
preview-restart, ledger-write. Exit 0 on REHEARSAL OK, non-zero on REHEARSAL FAILED.

The fixture is a set-up repo: the payload's bin copied to `.claude/workflow/bin`, the example
config with a `web` preview (a bash loop that ends by itself), `.work/` ignored, and one
existing ticket in the ledger. The preview is stopped after every test whatever happened.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, BIN, PAYLOAD, git
from test_preview import _app, _row

STEPS = [
    "move-onto-epic-head", "red", "verify-red", "green", "task-submit", "merge-task",
    "preview-restart", "ledger-write",
]
STEP_LINE = re.compile(r"^STEP (\S+) (PASS|FAIL)(?: .*)?$")
TICKET = ".work/tickets/E9/E9-T1.md"
TICKET_TEXT = "---\nkey: E9-T1\nstatus: doing\n---\n\n## Goal\nA real ticket.\n\n## Log\n- 2026-09-01: started\n"
SKILL = "claude/skills/setup-workflow/SKILL.md"


def _config(start: str, ready: str) -> str:
    text = (PAYLOAD / "claude" / "workflow" / "config.example.md").read_text(encoding="utf-8")
    lines = []
    for line in text.splitlines():
        if line.startswith("| `<name>` |"):
            line = _row("web", start, ready, "server.conf")
        elif line.startswith("| Setup in a fresh worktree |"):
            line = "| Setup in a fresh worktree | `true` |"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _set_up(repo: Path, start: str, ready: str) -> None:
    """Make the fixture repo a set-up repo, committed on main and pushed."""
    bin_dir = repo / ".claude" / "workflow" / "bin"
    bin_dir.mkdir(parents=True)
    for script in BIN.glob("*.sh"):
        shutil.copy(script, bin_dir / script.name)
    (repo / ".claude" / "workflow" / "config.md").write_text(_config(start, ready), encoding="utf-8")
    (repo / ".gitignore").write_text(".work/\n", encoding="utf-8")
    git("add", ".", cwd=repo)
    git("commit", "-q", "-m", "set up the workflow", cwd=repo)
    git("push", "-q", "origin", "main", cwd=repo)
    ticket = repo / TICKET
    ticket.parent.mkdir(parents=True)
    ticket.write_bytes(TICKET_TEXT.encode("utf-8"))


def _stop_preview(repo: Path) -> None:
    subprocess.run(
        [BASH, (BIN / "preview.sh").as_posix(), "stop", "--surface", "web", "--worktree",
         repo.as_posix()],
        cwd=str(repo), capture_output=True, check=False, timeout=60,
    )


@pytest.fixture
def setup_repo(tmp_path, repo, worktree):
    """A set-up repo with a working `web` preview and an unrelated task worktree `feature`."""
    start, ready = _app(tmp_path / "beat", tmp_path / "ready")
    _set_up(repo, start, ready)
    worktree(repo, "feature")
    try:
        yield repo
    finally:
        _stop_preview(repo)


@pytest.fixture
def broken_preview_repo(tmp_path, repo, worktree):
    """A set-up repo whose `web` preview exits at once and is never ready."""
    _set_up(repo, "exit 3", "false")
    worktree(repo, "feature")
    try:
        yield repo
    finally:
        _stop_preview(repo)


def _rehearse(cwd: Path, *args: str, script: Path | None = None):
    script = script or cwd / ".claude" / "workflow" / "bin" / "rehearse.sh"
    env = dict(os.environ)
    env["PAD_PREVIEW_TIMEOUT"] = "3"
    return subprocess.run(
        [BASH, script.as_posix(), *args],
        cwd=str(cwd), env=env, capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=600,
    )


def _out(r) -> str:
    return f"exit {r.returncode}\n--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}"


def _lines(r) -> list[str]:
    return [line.rstrip("\r") for line in r.stdout.splitlines() if line.strip()]


def _last(r) -> str:
    lines = _lines(r)
    return lines[-1] if lines else ""


def _steps(r) -> list[tuple[str, str]]:
    found = []
    for line in _lines(r):
        m = STEP_LINE.match(line)
        if m:
            found.append((m.group(1), m.group(2)))
    return found


def _is_subsequence(wanted: list[str], seen: list[str]) -> bool:
    it = iter(seen)
    return all(any(w == s for s in it) for w in wanted)


def _files(root: Path) -> dict[str, bytes]:
    if root.is_file():
        return {".": root.read_bytes()}
    if not root.exists():
        return {}
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _snapshot(repo: Path) -> dict:
    origin = repo.parent / "origin.git"
    return {
        "refs": git("for-each-ref", "--format=%(refname) %(objectname)", cwd=repo),
        "origin refs": git("for-each-ref", "--format=%(refname) %(objectname)", cwd=origin),
        "worktrees": [
            line for line in git("worktree", "list", "--porcelain", cwd=repo).splitlines()
            if line.startswith(("worktree ", "branch ", "detached", "prunable"))
        ],
        "ledger": _files(repo / ".work"),
        "HEAD": git("rev-parse", "HEAD", cwd=repo),
        "branch": git("symbolic-ref", "-q", "HEAD", cwd=repo),
        "status": git("status", "--porcelain", cwd=repo),
    }


def _assert_left_nothing(before: dict, after: dict) -> None:
    for what in before:
        assert after[what] == before[what], f"rehearsal left {what} changed"


# --- O46: the whole mechanical path passes ----------------------------------------------------

def test_o46_rehearsal_in_a_set_up_repo_prints_every_step_pass_then_rehearsal_ok(setup_repo):
    r = _rehearse(setup_repo)
    steps = _steps(r)
    assert _last(r) == "REHEARSAL OK", _out(r)
    assert r.returncode == 0, _out(r)
    assert [s for s, status in steps if status == "FAIL"] == [], _out(r)
    assert _is_subsequence(STEPS, [s for s, _ in steps]), _out(r)


def test_o46_passing_rehearsal_leaves_no_branches_worktrees_or_ledger_changes(setup_repo):
    before = _snapshot(setup_repo)
    r = _rehearse(setup_repo)
    assert _last(r) == "REHEARSAL OK", _out(r)
    _assert_left_nothing(before, _snapshot(setup_repo))


def test_o46_existing_ticket_is_byte_identical_after_the_ledger_write_step(setup_repo):
    r = _rehearse(setup_repo)
    assert ("ledger-write", "PASS") in _steps(r), _out(r)
    assert (setup_repo / TICKET).read_bytes() == TICKET_TEXT.encode("utf-8")


# --- O46: failures are reported, and still clean up -------------------------------------------

def test_o46_preview_that_never_starts_fails_the_preview_restart_step(broken_preview_repo):
    r = _rehearse(broken_preview_repo)
    steps = _steps(r)
    assert ("preview-restart", "FAIL") in steps, _out(r)
    fails = [s for s, status in steps if status == "FAIL"]
    assert _last(r) == f"REHEARSAL FAILED {len(fails)}", _out(r)
    assert r.returncode != 0, _out(r)


def test_o46_failed_preview_step_still_leaves_no_branches_worktrees_or_ledger_changes(
    broken_preview_repo,
):
    before = _snapshot(broken_preview_repo)
    r = _rehearse(broken_preview_repo)
    assert _last(r).startswith("REHEARSAL FAILED "), _out(r)
    _assert_left_nothing(before, _snapshot(broken_preview_repo))


def test_o46_unwritable_ledger_fails_the_ledger_write_step_and_keeps_what_was_there(setup_repo):
    shutil.rmtree(setup_repo / ".work")
    (setup_repo / ".work").write_text("not a directory\n", encoding="utf-8")
    before = _snapshot(setup_repo)
    r = _rehearse(setup_repo)
    assert ("ledger-write", "FAIL") in _steps(r), _out(r)
    assert _last(r).startswith("REHEARSAL FAILED "), _out(r)
    assert r.returncode != 0, _out(r)
    _assert_left_nothing(before, _snapshot(setup_repo))


def test_o46_unreachable_origin_fails_the_rehearsal_and_leaves_no_branches_or_worktrees(
    setup_repo,
):
    git("remote", "set-url", "origin", (setup_repo.parent / "missing.git").as_posix(),
        cwd=setup_repo)
    before = _snapshot(setup_repo)
    r = _rehearse(setup_repo)
    assert _last(r).startswith("REHEARSAL FAILED "), _out(r)
    assert r.returncode != 0, _out(r)
    assert any(status == "FAIL" for _, status in _steps(r)), _out(r)
    _assert_left_nothing(before, _snapshot(setup_repo))


def test_o46_outside_a_git_repo_the_rehearsal_fails(tmp_path, setup_repo):
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    r = _rehearse(outside, script=setup_repo / ".claude" / "workflow" / "bin" / "rehearse.sh")
    assert _last(r).startswith("REHEARSAL FAILED "), _out(r)
    assert r.returncode != 0, _out(r)


# --- O47: /setup-workflow ends with the rehearsal ---------------------------------------------

def _sections(text: str) -> list[tuple[str, int]]:
    return [(m.group(1), m.start()) for m in re.finditer(r"^## (.+)$", text, re.M)]


def test_o47_setup_workflow_runs_rehearse_after_every_other_setup_step(payload_text):
    text = payload_text(SKILL)
    assert "rehearse.sh" in text
    first = text.index("rehearse.sh")
    others = [
        pos for title, pos in _sections(text)
        if not re.search(r"report|rehears", title, re.I)
    ]
    assert others, "no setup sections found"
    assert first > max(others), "rehearse.sh is not the closing step"


def test_o47_setup_workflow_reports_done_only_on_rehearsal_ok(payload_text):
    text = payload_text(SKILL)
    assert "REHEARSAL OK" in text
    assert "REHEARSAL FAILED" in text


def test_o47_setup_workflow_report_section_names_the_rehearsal_result(payload_text):
    text = payload_text(SKILL)
    title, pos = _sections(text)[-1]
    assert re.search(r"report", title, re.I), f"last section is {title!r}"
    assert re.search(r"rehears", text[pos:], re.I)
