"""O16: every halt appends one line to the main checkout's orchestrator/HALTS.md via halt-log.sh.

Line shape (ticket Interfaces):
    - <yyyy-mm-dd> <run id> <KEY> [<class>] <cause> — <resolution>
"""
from __future__ import annotations

import datetime
from pathlib import Path

import pytest

RUN = "E1-20260929"


def halts(main: Path) -> Path:
    return main / ".claude" / "agent-memory" / "orchestrator" / "HALTS.md"


def run_halt(run_script, *args, cwd):
    """Run halt-log.sh and return (result, dates that were 'today' around the call)."""
    before = datetime.date.today().isoformat()
    result = run_script("halt-log.sh", *args, cwd=cwd)
    after = datetime.date.today().isoformat()
    return result, {before, after}


def assert_single_line(text: str, days: set[str], rest: str) -> None:
    assert text in {f"- {d} {rest}\n" for d in days}, text


def test_o16_parked_question_from_main_checkout_creates_halts_file_with_one_line(repo, run_script):
    result, days = run_halt(
        run_script, RUN, "E1-T4", "project", "which schema version wins?", "pending", cwd=repo
    )

    assert result.returncode == 0, result.stderr
    assert_single_line(
        halts(repo).read_text(encoding="utf-8"), days,
        f"{RUN} E1-T4 [project] which schema version wins? — pending",
    )


def test_o16_halt_from_linked_worktree_subdirectory_lands_in_main_checkout(
    repo, worktree, run_script
):
    wt = worktree(repo, "E1-T7")
    sub = wt / "src" / "deep"
    sub.mkdir(parents=True)

    result, days = run_halt(
        run_script, RUN, "E1-T7", "machine", "port 5432 in use", "pending", cwd=sub
    )

    assert result.returncode == 0, result.stderr
    assert_single_line(
        halts(repo).read_text(encoding="utf-8"), days,
        f"{RUN} E1-T7 [machine] port 5432 in use — pending",
    )
    assert not (wt / ".claude").exists()
    assert not (sub / ".claude").exists()


def test_o16_run_wide_pause_is_logged_with_dash_as_key(repo, run_script):
    result, days = run_halt(
        run_script, RUN, "-", "harness", "nothing runnable: all tasks parked", "operator answered",
        cwd=repo,
    )

    assert result.returncode == 0, result.stderr
    assert_single_line(
        halts(repo).read_text(encoding="utf-8"), days,
        f"{RUN} - [harness] nothing runnable: all tasks parked — operator answered",
    )


@pytest.mark.parametrize("cls", ["pad", "project", "machine", "harness"])
def test_o16_each_halt_class_is_accepted_and_recorded(repo, run_script, cls):
    result, days = run_halt(run_script, RUN, "E1-T2", cls, "cause", "fixed", cwd=repo)

    assert result.returncode == 0, result.stderr
    assert_single_line(
        halts(repo).read_text(encoding="utf-8"), days, f"{RUN} E1-T2 [{cls}] cause — fixed"
    )


def test_o16_existing_halts_are_kept_and_resolution_is_a_second_line(repo, worktree, run_script):
    log = halts(repo)
    log.parent.mkdir(parents=True)
    log.write_bytes(b"# Halts\n\n- 2026-09-01 E0-1 E0-T1 [pad] old cause \xe2\x80\x94 fixed\n")
    wt = worktree(repo, "E1-T9")

    first, days1 = run_halt(run_script, RUN, "E1-T9", "pad", "denied git push", "pending", cwd=wt)
    second, days2 = run_halt(
        run_script, RUN, "E1-T9", "pad", "denied git push", "rule added to settings", cwd=repo
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    days = days1 | days2
    expected = {
        "# Halts\n\n- 2026-09-01 E0-1 E0-T1 [pad] old cause — fixed\n"
        f"- {a} {RUN} E1-T9 [pad] denied git push — pending\n"
        f"- {b} {RUN} E1-T9 [pad] denied git push — rule added to settings\n"
        for a in days for b in days
    }
    assert log.read_text(encoding="utf-8") in expected


def test_o16_cause_and_resolution_are_written_literally(repo, run_script):
    cause = "-e $HOME `whoami` \\t 50% %s"
    result, days = run_halt(run_script, RUN, "E1-T3", "harness", cause, "$PATH \\n", cwd=repo)

    assert result.returncode == 0, result.stderr
    assert_single_line(
        halts(repo).read_text(encoding="utf-8"), days,
        f"{RUN} E1-T3 [harness] {cause} — $PATH \\n",
    )


def test_o16_unknown_class_is_usage_error_and_writes_nothing(repo, run_script):
    result = run_script("halt-log.sh", RUN, "E1-T2", "network", "cause", "pending", cwd=repo)

    assert result.returncode == 64
    assert not halts(repo).exists()


def test_o16_missing_resolution_is_usage_error_and_writes_nothing(repo, run_script):
    result = run_script("halt-log.sh", RUN, "E1-T2", "pad", "cause", cwd=repo)

    assert result.returncode == 64
    assert not halts(repo).exists()


def test_o16_no_arguments_is_usage_error_and_writes_nothing(repo, run_script):
    result = run_script("halt-log.sh", cwd=repo)

    assert result.returncode == 64
    assert not halts(repo).exists()


@pytest.mark.parametrize(
    "args",
    [
        ("", "E1-T2", "pad", "cause", "pending"),
        (RUN, "", "pad", "cause", "pending"),
        (RUN, "E1-T2", "pad", "", "pending"),
    ],
    ids=["empty-run-id", "empty-key", "empty-cause"],
)
def test_o16_empty_run_id_key_or_cause_is_usage_error_and_writes_nothing(repo, run_script, args):
    result = run_script("halt-log.sh", *args, cwd=repo)

    assert result.returncode == 64
    assert not halts(repo).exists()
