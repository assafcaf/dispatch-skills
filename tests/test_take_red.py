"""O3: a red commit taken with the prompts' moves leaves every task branch deletable with `-d`.

Integration: real repos and worktrees. The code-writer takes the red commit with the move its
prompt names, looked up in `config.example.md`'s Git moves; the task merges with
`merge-task.sh`; the owner then cleans up with the moves its prompt names, from the epic
worktree. `git branch -d` must succeed for the test-designer's and the code-writer's branches.
"""
from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

from conftest import git

CONFIG = "claude/workflow/config.example.md"
WRITER = "claude/agents/code-writer.md"
OWNER = "claude/agents/ticket-owner.md"

KEY = "E9-T1"
GOAL = "Add the impl"
TESTS_BRANCH = "E9-T1-tests"
CODE_BRANCH = "E9-T1-code"


def git_moves(payload_text) -> dict[str, str]:
    text = payload_text(CONFIG)
    m = re.search(r"^## Git moves\s*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "no ## Git moves section in config.example.md"
    moves = {}
    for line in m.group(1).splitlines():
        cells = [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] and cells[0] != "Capability" and set(cells[0]) - set("-:"):
            moves[cells[0]] = cells[1]
    return moves


def named_moves(text: str) -> list[str]:
    token = r"`[a-z][a-z0-9-]*`"
    lists = re.findall(
        rf"\bthe\s+((?:{token}\s*(?:,|,?\s*or|,?\s*and)\s*)*{token})\s+moves?\b", text
    )
    return [name for group in lists for name in re.findall(r"`([a-z][a-z0-9-]*)`", group)]


def move(payload_text, prompt: str, cap: str) -> str:
    """The command for `cap`, once the prompt is shown to ask for it by name."""
    assert cap in named_moves(payload_text(prompt)), f"{prompt} does not name the `{cap}` move"
    moves = git_moves(payload_text)
    assert cap in moves, f"`{cap}` is not in the Git moves table"
    return moves[cap]


def run_move(command: str, value: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a one-placeholder move with `value` in place of its placeholder."""
    words = shlex.split(command)
    holes = [i for i, w in enumerate(words) if re.fullmatch(r"<[^<>]+>", w)]
    assert len(holes) == 1, f"expected one placeholder in {command!r}"
    words[holes[0]] = value
    assert words[0] == "git", command
    return subprocess.run(words, cwd=str(cwd), capture_output=True, text=True, check=False)


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _setup(repo: Path, worktree):
    """Epic worktree (pushed), a designer worktree with a red commit, a code-writer worktree.

    Both task worktrees start at the epic head. -> (epic_wt, tests_wt, code_wt, red)
    """
    epic_wt = worktree(repo, "epic")
    epic_head = _commit(epic_wt, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic_wt)
    tests_wt = worktree(repo, TESTS_BRANCH)
    git("reset", "-q", "--hard", epic_head, cwd=tests_wt)
    red = _commit(
        tests_wt,
        {"tests/test_new.py": "def test_new():\n    assert False\n"},
        f"test({KEY}): O1 [red]",
    )
    code_wt = worktree(repo, CODE_BRANCH)
    git("reset", "-q", "--hard", epic_head, cwd=code_wt)
    return epic_wt, tests_wt, code_wt, red


def _merge(run_script, repo: Path, epic_wt: Path, red: str, head: str) -> None:
    r = run_script(
        "merge-task.sh",
        "--worktree", epic_wt.as_posix(),
        "--branch", "epic",
        "--gate", 'grep -q "X = 1" src/impl.py',
        "--lint", "true",
        KEY, red, head, GOAL,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("MERGED "), r.stdout


def _first_red_task(payload_text, run_script, repo, worktree):
    """The code-writer takes the red with its prompt's `take-red`, commits green, merges."""
    epic_wt, tests_wt, code_wt, red = _setup(repo, worktree)
    take = run_move(move(payload_text, WRITER, "take-red"), red, code_wt)
    assert take.returncode == 0, take.stderr
    head = _commit(code_wt, {"src/impl.py": "X = 1\n"}, f"feat({KEY}): impl")
    _merge(run_script, repo, epic_wt, red, head)
    return epic_wt, tests_wt, code_wt, red


def _follow_up_red_task(payload_text, run_script, repo, worktree):
    """As above, then a fixed red on top of the first; the code-writer rebases onto it, merges."""
    epic_wt, tests_wt, code_wt, red = _setup(repo, worktree)
    take = run_move(move(payload_text, WRITER, "take-red"), red, code_wt)
    assert take.returncode == 0, take.stderr
    _commit(code_wt, {"src/impl.py": "X = 1\n"}, f"feat({KEY}): impl")
    fixed = _commit(
        tests_wt,
        {"tests/test_new.py": "def test_new():\n    assert 1 == 2\n"},
        f"test({KEY}): fix O1 [red]",
    )
    again = run_move(move(payload_text, WRITER, "rebase-red"), fixed, code_wt)
    assert again.returncode == 0, again.stderr
    head = git("rev-parse", "HEAD", cwd=code_wt)
    _merge(run_script, repo, epic_wt, fixed, head)
    return epic_wt, tests_wt, code_wt, fixed


def _clean_up(payload_text, epic_wt: Path, tests_wt: Path, code_wt: Path) -> dict[str, subprocess.CompletedProcess]:
    """The owner's cleanup from the epic worktree: remove both worktrees, then delete branches."""
    remove = move(payload_text, OWNER, "remove-worktree")
    delete = move(payload_text, OWNER, "delete-merged-branch")
    for wt in (tests_wt, code_wt):
        r = run_move(remove, wt.as_posix(), epic_wt)
        assert r.returncode == 0, r.stderr
    return {b: run_move(delete, b, epic_wt) for b in (TESTS_BRANCH, CODE_BRANCH)}


def _branches(repo: Path) -> list[str]:
    return git("for-each-ref", "--format=%(refname:short)", "refs/heads/", cwd=repo).split()


# --- first red, taken with take-red ---


def test_o3_take_red_puts_the_designers_own_red_commit_on_the_code_writer_branch(
    payload_text, repo, worktree
):
    _, _, code_wt, red = _setup(repo, worktree)
    take = run_move(move(payload_text, WRITER, "take-red"), red, code_wt)
    assert take.returncode == 0, take.stderr
    assert git("rev-parse", "HEAD", cwd=code_wt) == red


def test_o3_after_merge_the_test_designer_branch_deletes_with_branch_d(
    payload_text, run_script, repo, worktree
):
    epic_wt, tests_wt, code_wt, _ = _first_red_task(payload_text, run_script, repo, worktree)
    result = _clean_up(payload_text, epic_wt, tests_wt, code_wt)[TESTS_BRANCH]
    assert result.returncode == 0, result.stderr
    assert TESTS_BRANCH not in _branches(repo)


def test_o3_after_merge_the_code_writer_branch_deletes_with_branch_d(
    payload_text, run_script, repo, worktree
):
    epic_wt, tests_wt, code_wt, _ = _first_red_task(payload_text, run_script, repo, worktree)
    result = _clean_up(payload_text, epic_wt, tests_wt, code_wt)[CODE_BRANCH]
    assert result.returncode == 0, result.stderr
    assert CODE_BRANCH not in _branches(repo)


# --- follow-up red, rebased in with rebase-red ---


def test_o3_follow_up_red_rebase_puts_the_code_on_top_of_the_fixed_red(
    payload_text, repo, worktree
):
    _, tests_wt, code_wt, red = _setup(repo, worktree)
    take = run_move(move(payload_text, WRITER, "take-red"), red, code_wt)
    assert take.returncode == 0, take.stderr
    _commit(code_wt, {"src/impl.py": "X = 1\n"}, f"feat({KEY}): impl")
    fixed = _commit(
        tests_wt,
        {"tests/test_new.py": "def test_new():\n    assert 1 == 2\n"},
        f"test({KEY}): fix O1 [red]",
    )
    again = run_move(move(payload_text, WRITER, "rebase-red"), fixed, code_wt)
    assert again.returncode == 0, again.stderr
    assert git("rev-parse", "HEAD~1", cwd=code_wt) == fixed
    assert git("rev-parse", "HEAD~2", cwd=code_wt) == red


def test_o3_after_a_follow_up_red_the_test_designer_branch_deletes_with_branch_d(
    payload_text, run_script, repo, worktree
):
    epic_wt, tests_wt, code_wt, _ = _follow_up_red_task(payload_text, run_script, repo, worktree)
    result = _clean_up(payload_text, epic_wt, tests_wt, code_wt)[TESTS_BRANCH]
    assert result.returncode == 0, result.stderr
    assert TESTS_BRANCH not in _branches(repo)


def test_o3_after_a_follow_up_red_the_code_writer_branch_deletes_with_branch_d(
    payload_text, run_script, repo, worktree
):
    epic_wt, tests_wt, code_wt, _ = _follow_up_red_task(payload_text, run_script, repo, worktree)
    result = _clean_up(payload_text, epic_wt, tests_wt, code_wt)[CODE_BRANCH]
    assert result.returncode == 0, result.stderr
    assert CODE_BRANCH not in _branches(repo)
