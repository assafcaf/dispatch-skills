"""O29: task-submit.sh checks a task branch against every submission rule."""
from __future__ import annotations

from pathlib import Path

from conftest import git

TESTS = "tests"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _epic(repo: Path) -> str:
    """Epic head: main plus an existing test the task must not weaken."""
    _commit(repo, {"tests/test_old.py": "def test_old():\n    assert True\n"}, "epic: old test")
    return git("rev-parse", "HEAD", cwd=repo)


def _branch(repo: Path, worktree, name: str, base: str) -> Path:
    wt = worktree(repo, name)
    git("reset", "-q", "--hard", base, cwd=wt)
    return wt


def _submit(run_script, wt: Path, epic: str, red: str, head: str):
    return run_script("task-submit.sh", epic, red, head, "--test-paths", TESTS, cwd=wt)


def _last(result) -> str:
    return result.stdout.strip().splitlines()[-1]


def _red(wt: Path) -> str:
    return _commit(
        wt, {"tests/test_new.py": "def test_new():\n    assert False\n"}, "test(T-1): o1 [red]"
    )


def test_clean_branch_is_submitted_ok(repo, worktree, run_script):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-clean", epic)
    red = _red(wt)
    head = _commit(wt, {"src/impl.py": "X = 1\n"}, "feat(T-1): impl")
    r = _submit(run_script, wt, epic, red, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_sha_that_is_not_a_commit_fails_not_a_commit(repo, worktree, run_script):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-nocommit", epic)
    red = _red(wt)
    r = _submit(run_script, wt, epic, red, "0123456789abcdef0123456789abcdef01234567")
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL not-a-commit:")


def test_test_file_changed_after_red_fails(repo, worktree, run_script):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-changed", epic)
    red = _red(wt)
    head = _commit(
        wt, {"tests/test_new.py": "def test_new():\n    assert True\n"}, "feat(T-1): impl"
    )
    r = _submit(run_script, wt, epic, red, head)
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL test-changed-after-red:")


def test_red_commit_after_a_code_commit_fails(repo, worktree, run_script):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-order", epic)
    _commit(wt, {"src/impl.py": "X = 1\n"}, "feat(T-1): impl first")
    red = _red(wt)
    r = _submit(run_script, wt, epic, red, red)
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL red-after-code:")


def test_weakened_test_fails(repo, worktree, run_script):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-weak", epic)
    red = _commit(
        wt,
        {"tests/test_old.py": "import pytest\n\n@pytest.mark.skip\ndef test_old():\n    assert True\n"},
        "test(T-1): o1 [red]",
    )
    head = _commit(wt, {"src/impl.py": "X = 1\n"}, "feat(T-1): impl")
    r = _submit(run_script, wt, epic, red, head)
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL weakened-tests:")


def test_removed_test_fails_weakened_tests(repo, worktree, run_script):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-removed", epic)
    red = _commit(wt, {"tests/test_old.py": "X = 1\n"}, "test(T-1): o1 [red]")
    r = _submit(run_script, wt, epic, red, red)
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL weakened-tests:")


def test_branch_without_epic_head_fails_missing_epic_head(repo, worktree, run_script):
    old = git("rev-parse", "HEAD", cwd=repo)
    wt = _branch(repo, worktree, "t-stale", old)
    red = _red(wt)
    head = _commit(wt, {"src/impl.py": "X = 1\n"}, "feat(T-1): impl")
    epic = _epic(repo)  # epic advances after the branch was cut
    r = _submit(run_script, wt, epic, red, head)
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL missing-epic-head:")
