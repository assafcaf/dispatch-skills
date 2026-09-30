"""O8, O9, O12: merge-task.sh gates a task's merged tree before it commits the merge.

    merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup "<cmd>"]
                  --gate "<cmd>" --lint "<cmd>" <KEY> <RED> <TASK_HEAD> "<GOAL>"

Each test builds a main checkout with a bare origin, an epic worktree on branch `epic` (pushed),
and a task worktree whose red commit and code commit sit on the epic head. The script runs from
the main checkout and reaches the epic worktree through --worktree only.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import git

SCRIPT = "merge-task.sh"
KEY = "T-1"
GOAL = "Add the impl"
PASS_GATE = 'grep -q "X = 1" src/impl.py'
PASS_LINT = "true"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _epic(repo: Path, worktree) -> tuple[Path, str]:
    """Epic worktree on branch `epic`, one commit past main, pushed to origin."""
    wt = worktree(repo, "epic")
    head = _commit(wt, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=wt)
    return wt, head


def _task(repo: Path, worktree, epic_head: str, impl: str = "X = 1\n") -> tuple[Path, str, str]:
    """Task worktree on the epic head: a red test commit, then a code commit. -> (wt, red, head)."""
    wt = worktree(repo, "task")
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    red = _commit(
        wt, {"tests/test_new.py": "def test_new():\n    assert False\n"}, f"test({KEY}): O1 [red]"
    )
    head = _commit(wt, {"src/impl.py": impl}, f"feat({KEY}): impl")
    return wt, red, head


def _merge(run_script, repo: Path, epic_wt: Path, red: str, head: str, *,
           gate: str = PASS_GATE, lint: str = PASS_LINT, extra: tuple[str, ...] = ()):
    return run_script(
        SCRIPT,
        "--worktree", epic_wt.as_posix(),
        "--branch", "epic",
        *extra,
        "--gate", gate,
        "--lint", lint,
        KEY, red, head, GOAL,
        cwd=repo,
    )


def _last(result) -> str:
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _origin_epic(repo: Path) -> str:
    return git("rev-parse", "refs/heads/epic", cwd=repo.parent / "origin.git")


def _merge_in_progress(wt: Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        cwd=str(wt), capture_output=True, text=True, check=False,
    )
    return r.returncode == 0


def _assert_untouched(epic_wt: Path, repo: Path, epic_head: str, result) -> None:
    out = result.stdout + result.stderr
    assert git("rev-parse", "HEAD", cwd=epic_wt) == epic_head, out
    assert git("status", "--porcelain", cwd=epic_wt) == "", out
    assert not _merge_in_progress(epic_wt), out
    assert _origin_epic(repo) == epic_head, out
    assert not (epic_wt / "src" / "impl.py").exists(), out


# O8 ---------------------------------------------------------------------------------------------


def test_green_task_prints_merged_with_the_new_epic_head(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 0, r.stdout + r.stderr
    new_head = git("rev-parse", "HEAD", cwd=epic_wt)
    assert new_head != epic_head
    assert _last(r) == f"MERGED {new_head}"


def test_green_task_adds_exactly_one_no_ff_merge_commit(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git("rev-list", "--count", "--first-parent", f"{epic_head}..HEAD", cwd=epic_wt) == "1"
    parents = git("log", "-1", "--format=%P", cwd=epic_wt).split()
    assert parents == [epic_head, head]
    assert git("log", "-1", "--format=%s", cwd=epic_wt) == f"Merge {KEY}: {GOAL}"


def test_green_task_merge_is_pushed_to_the_epic_branch(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _origin_epic(repo) == git("rev-parse", "HEAD", cwd=epic_wt)
    assert git("status", "--porcelain", cwd=epic_wt) == ""


def test_gate_and_lint_run_in_the_epic_worktree_on_the_merged_tree(repo, worktree, run_script, tmp_path):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    seen = tmp_path / "seen.txt"
    probe = f'cat src/base.py src/impl.py >> "{seen.as_posix()}"'
    r = _merge(run_script, repo, epic_wt, red, head, gate=probe, lint=probe)
    assert r.returncode == 0, r.stdout + r.stderr
    assert seen.read_text(encoding="utf-8") == "BASE = 1\nX = 1\n" * 2


def test_setup_runs_before_the_gate_when_given(repo, worktree, run_script, tmp_path):
    """Setup is optional; when the merge changes a manifest it runs before the gate."""
    epic_wt, epic_head = _epic(repo, worktree)
    twt = worktree(repo, "task")
    git("reset", "-q", "--hard", epic_head, cwd=twt)
    red = _commit(
        twt, {"tests/test_new.py": "def test_new():\n    assert False\n"}, f"test({KEY}): O1 [red]"
    )
    head = _commit(
        twt,
        {"src/impl.py": "X = 1\n", "requirements.txt": "pytest\n", "package.json": "{}\n"},
        f"feat({KEY}): impl with a new dependency",
    )
    order = tmp_path / "order.txt"
    log = order.as_posix()
    r = _merge(
        run_script, repo, epic_wt, red, head,
        gate=f'echo gate >> "{log}"', lint=f'echo lint >> "{log}"',
        extra=("--setup", f'echo setup >> "{log}"'),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert order.read_text(encoding="utf-8").split() == ["setup", "gate", "lint"]


def test_setup_is_skipped_when_no_manifest_changed(repo, worktree, run_script, tmp_path):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    ran = tmp_path / "setup-ran"
    r = _merge(run_script, repo, epic_wt, red, head, extra=("--setup", f'touch "{ran.as_posix()}"'))
    assert r.returncode == 0, r.stdout + r.stderr
    assert not ran.exists()


# O9---------------------------------------------------------------------------------------------


def test_failing_gate_is_rejected_with_the_failing_output_tail(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, gate="echo GATE-TAIL-7f3e && false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}")
    assert "GATE-TAIL-7f3e" in r.stdout


def test_failing_gate_leaves_epic_head_and_tree_exactly_as_before(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, gate="false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}")
    _assert_untouched(epic_wt, repo, epic_head, r)


def test_gate_failing_on_the_merged_code_is_rejected(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head, impl="X = 2\n")
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}")
    _assert_untouched(epic_wt, repo, epic_head, r)


def test_failing_lint_is_rejected_and_leaves_epic_untouched(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, lint="echo LINT-TAIL-91c && false")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}")
    assert "LINT-TAIL-91c" in r.stdout
    _assert_untouched(epic_wt, repo, epic_head, r)


def test_conflicting_task_prints_conflict_with_paths_and_aborts(repo, worktree, run_script):
    """A task cut from an earlier epic head, while another task changed the same file."""
    epic_wt, first = _epic(repo, worktree)
    twt, red, _ = _task(repo, worktree, first)
    head = _commit(twt, {"src/base.py": "BASE = 'task'\n"}, f"feat({KEY}): change base")
    epic_head = _commit(epic_wt, {"src/base.py": "BASE = 'epic'\n"}, "Merge T-0: other task")
    git("push", "-q", "origin", "epic", cwd=epic_wt)
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"CONFLICT {KEY}:")
    assert "src/base.py" in _last(r)
    _assert_untouched(epic_wt, repo, epic_head, r)


def test_dirty_epic_worktree_is_an_infrastructure_failure_and_keeps_the_change(
    repo, worktree, run_script, tmp_path
):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    (epic_wt / "src" / "base.py").write_text("BASE = 'uncommitted'\n", encoding="utf-8")
    ran = tmp_path / "gate-ran"
    r = _merge(run_script, repo, epic_wt, red, head, gate=f'touch "{ran.as_posix()}"')
    assert r.returncode == 2, r.stdout + r.stderr
    assert not ran.exists()
    assert git("rev-parse", "HEAD", cwd=epic_wt) == epic_head
    assert (epic_wt / "src" / "base.py").read_text(encoding="utf-8") == "BASE = 'uncommitted'\n"
    assert not _merge_in_progress(epic_wt)


def test_failed_push_is_an_infrastructure_failure(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    git("remote", "set-url", "origin", (repo.parent / "gone.git").as_posix(), cwd=repo)
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 2, r.stdout + r.stderr
    assert not _last(r).startswith("MERGED")


# O12 --------------------------------------------------------------------------------------------


def test_task_failing_submission_is_rejected_with_its_reason(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, _ = _task(repo, worktree, epic_head)
    head = _commit(
        twt, {"tests/test_new.py": "def test_new():\n    assert True\n"}, f"feat({KEY}): edit test"
    )
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}:")
    assert "test-changed-after-red" in _last(r)


def test_task_failing_submission_never_touches_the_tree_or_runs_the_gate(
    repo, worktree, run_script, tmp_path
):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, _ = _task(repo, worktree, epic_head)
    head = _commit(
        twt, {"tests/test_new.py": "def test_new():\n    assert True\n"}, f"feat({KEY}): edit test"
    )
    ran = tmp_path / "gate-ran"
    r = _merge(run_script, repo, epic_wt, red, head, gate=f'touch "{ran.as_posix()}"')
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}:")
    assert not ran.exists()
    _assert_untouched(epic_wt, repo, epic_head, r)


def test_task_head_that_is_not_a_commit_is_rejected_as_not_a_commit(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, _ = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, "0123456789abcdef0123456789abcdef01234567")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}:")
    assert "not-a-commit" in _last(r)
    _assert_untouched(epic_wt, repo, epic_head, r)
