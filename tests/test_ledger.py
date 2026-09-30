"""O4: ledger.sh updates a local ticket in the main checkout's ledger from any worktree."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TICKET = """---
key: E1-T4
title: ledger.sh
status: todo
blocked_by: [E1-T1]
labels: [agent-planned]
---

## Goal
Something.
"""


@pytest.fixture
def ledger(repo):
    d = repo / ".work" / "tickets" / "E1"
    d.mkdir(parents=True)
    return d


def _write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def test_status_from_linked_worktree_updates_main_checkout_ticket(
    repo, worktree, ledger, run_script
):
    ticket = _write(ledger / "E1-T4.md", TICKET + "\n## Log\n- 2026-09-01: created\n")
    wt = worktree(repo, "t4")
    r = run_script("ledger.sh", "E1-T4", "status", "doing", "picked up", cwd=wt)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "LEDGER OK E1-T4 doing"
    text = _read(ticket)
    assert re.search(r"^status: doing\s*$", text, re.M)
    assert "status: todo" not in text
    log = text.split("## Log\n", 1)[1].splitlines()
    assert log[0] == "- 2026-09-01: created"
    assert len(log) == 2
    assert re.fullmatch(r"- \d{4}-\d{2}-\d{2}: picked up", log[1])
    assert not (wt / ".work").exists()


def test_status_change_leaves_rest_of_ticket_untouched(repo, ledger, run_script):
    ticket = _write(ledger / "E1-T4.md", TICKET + "\n## Log\n- 2026-09-01: created\n")
    r = run_script("ledger.sh", "E1-T4", "status", "review", "ready", cwd=repo)
    assert r.returncode == 0, r.stderr
    text = _read(ticket)
    for line in ("key: E1-T4", "title: ledger.sh", "blocked_by: [E1-T1]",
                 "labels: [agent-planned]", "## Goal", "Something."):
        assert line in text
    assert re.search(r"^status: review\s*$", text, re.M)


def test_status_creates_log_heading_when_missing(repo, ledger, run_script):
    ticket = _write(ledger / "E1-T4.md", TICKET)
    r = run_script("ledger.sh", "E1-T4", "status", "done", "merged", cwd=repo)
    assert r.returncode == 0, r.stderr
    text = _read(ticket)
    assert text.count("## Log") == 1
    log = text.split("## Log", 1)[1].strip().splitlines()
    assert len(log) == 1
    assert re.fullmatch(r"- \d{4}-\d{2}-\d{2}: merged", log[0])


def test_comment_appends_log_line_and_keeps_status(repo, worktree, ledger, run_script):
    ticket = _write(ledger / "E1-T4.md", TICKET + "\n## Log\n- 2026-09-01: created\n")
    wt = worktree(repo, "t4c")
    r = run_script("ledger.sh", "E1-T4", "comment", "red proven", cwd=wt)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "LEDGER OK E1-T4 todo"
    text = _read(ticket)
    assert re.search(r"^status: todo\s*$", text, re.M)
    log = text.split("## Log\n", 1)[1].splitlines()
    assert len(log) == 2
    assert re.fullmatch(r"- \d{4}-\d{2}-\d{2}: red proven", log[1])


def test_two_updates_append_two_log_lines_in_order(repo, ledger, run_script):
    ticket = _write(ledger / "E1-T4.md", TICKET)
    run_script("ledger.sh", "E1-T4", "status", "doing", "first", cwd=repo)
    r = run_script("ledger.sh", "E1-T4", "comment", "second", cwd=repo)
    assert r.returncode == 0, r.stderr
    log = _read(ticket).split("## Log", 1)[1].strip().splitlines()
    assert len(log) == 2
    assert log[0].endswith(": first") and log[1].endswith(": second")


def test_epic_key_updates_epic_md(repo, ledger, run_script):
    epic = _write(ledger / "epic.md", TICKET.replace("E1-T4", "E1"))
    r = run_script("ledger.sh", "E1", "status", "doing", "started", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "LEDGER OK E1 doing"
    text = _read(epic)
    assert re.search(r"^status: doing\s*$", text, re.M)
    assert text.rstrip().endswith(": started")


def test_missing_ticket_exits_1_and_names_its_path(repo, worktree, ledger, run_script):
    wt = worktree(repo, "t9")
    r = run_script("ledger.sh", "E1-T9", "status", "doing", "x", cwd=wt)
    assert r.returncode == 1
    out = r.stdout + r.stderr
    assert "LEDGER FAIL E1-T9: no ticket at " in out
    assert ".work/tickets/E1/E1-T9.md" in out.replace("\\", "/")
    assert not (ledger / "E1-T9.md").exists()
    assert not (wt / ".work").exists()


def test_invalid_status_is_refused_and_ticket_unchanged(repo, ledger, run_script):
    ticket = _write(ledger / "E1-T4.md", TICKET)
    r = run_script("ledger.sh", "E1-T4", "status", "finished", "x", cwd=repo)
    assert r.returncode == 1
    assert "LEDGER FAIL E1-T4" in r.stdout + r.stderr
    assert _read(ticket) == TICKET
