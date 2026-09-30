"""O10, O11: merge-task.sh reruns a gate that only failed outside the task, and serializes merges.

O10: a gate whose failures all sit in test files the task neither touched nor imports is rerun
once; a green rerun merges. A failing test file is named in the gate output the way pytest's
summary names it: `FAILED tests/test_x.py::test_y - ...`.

O11: two merge-task.sh runs on one epic take the merge lock (`<git common dir>/pad-locks/merge`)
in turn; the second one's gate runs on the head the first one produced.

Concurrency is checked with files as handshakes, never with a sleep the correct code depends on:
a gate that finds itself alone waits a bounded time for a rival to show up, so an unlocked
implementation is caught, while a locked one passes however loaded the host is.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import BASH, BIN, git

SCRIPT = "merge-task.sh"
KEY = "T-1"
GOAL = "Change base"
LINT = "true"

# Counts its runs in <counter>. Fails on every run ("always") or on the first only ("first"),
# printing a pytest-style FAILED line for each test file given.
FLAKY_GATE = """\
counter="$1"; policy="$2"; shift 2
n=$(( $(cat "$counter" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$counter"
if [ "$policy" = always ] || [ "$n" -eq 1 ]; then
  for f in "$@"; do echo "FAILED $f::test_x - assert 0"; done
  echo "run $n: failed"
  exit 1
fi
echo "run $n: passed"
"""

# Gate for two concurrent merges: records the head it gates, flags an overlap with its rival,
# and, when alone, waits up to 3s for the rival to enter (it only can without a lock).
PAIR_GATE = """\
me="$1"; other="$2"; d="$3"; verdict="$4"
git rev-parse HEAD > "$d/$me.base"
[ -e "$d/$other.inside" ] && echo "$me entered while $other was inside" >> "$d/overlap"
touch "$d/$me.inside"
i=0
while [ $i -lt 30 ] && [ ! -e "$d/$other.inside" ] && [ ! -e "$d/$other.done" ]; do
  sleep 0.1; i=$((i+1))
done
[ -e "$d/$other.inside" ] && echo "$other entered while $me was inside" >> "$d/overlap"
rm -f "$d/$me.inside"
touch "$d/$me.done"
[ "$verdict" = pass ]
"""


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _epic(repo: Path, worktree) -> tuple[Path, str]:
    """Epic worktree on `epic`, pushed. tests/test_other.py imports nothing the task changes;
    tests/test_base.py imports src/base.py, which the task changes."""
    wt = worktree(repo, "epic")
    head = _commit(
        wt,
        {
            "src/__init__.py": "",
            "src/base.py": "BASE = 1\n",
            "tests/test_other.py": "def test_x():\n    assert 1 + 1 == 2\n",
            "tests/test_base.py": "from src.base import BASE\n\n\ndef test_x():\n    assert BASE\n",
        },
        "epic: base",
    )
    git("push", "-q", "-u", "origin", "epic", cwd=wt)
    return wt, head


def _task(repo: Path, worktree, epic_head: str, name: str = "task", key: str = KEY,
          files: dict[str, str] | None = None) -> tuple[str, str]:
    """A red commit adding tests/test_<name>.py, then a code commit. -> (red, head)."""
    wt = worktree(repo, name)
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    red = _commit(
        wt, {f"tests/test_{name}.py": "def test_new():\n    assert False\n"}, f"test({key}): O1 [red]"
    )
    code = files if files is not None else {"src/base.py": "BASE = 2\n", "src/impl.py": "X = 1\n"}
    head = _commit(wt, code, f"feat({key}): impl")
    return red, head


def _last(out: str) -> str:
    lines = out.strip().splitlines()
    return lines[-1] if lines else ""


def _flaky(tmp_path: Path, name: str, policy: str, *failing: str) -> tuple[str, Path]:
    """-> (gate command, run counter path)."""
    script = tmp_path / "flaky-gate.sh"
    script.write_text(FLAKY_GATE, encoding="utf-8")
    counter = tmp_path / f"{name}.runs"
    files = " ".join(failing)
    return f'bash "{script.as_posix()}" "{counter.as_posix()}" {policy} {files}', counter


def _runs(counter: Path) -> int:
    return int(counter.read_text(encoding="utf-8").strip()) if counter.exists() else 0


def _merge(run_script, repo: Path, epic_wt: Path, red: str, head: str, gate: str, key: str = KEY):
    return run_script(
        SCRIPT,
        "--worktree", epic_wt.as_posix(), "--branch", "epic",
        "--gate", gate, "--lint", LINT,
        key, red, head, GOAL,
        cwd=repo,
    )


def _untouched(epic_wt: Path, epic_head: str) -> bool:
    return (git("rev-parse", "HEAD", cwd=epic_wt) == epic_head
            and git("status", "--porcelain", "--untracked-files=no", cwd=epic_wt) == "")


# O10 --------------------------------------------------------------------------------------------


def test_gate_failing_only_in_an_untouched_test_file_is_rerun_and_merges_when_green(
    repo, worktree, run_script, tmp_path
):
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task(repo, worktree, epic_head)
    gate, counter = _flaky(tmp_path, "g", "first", "tests/test_other.py")
    r = _merge(run_script, repo, epic_wt, red, head, gate)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    new_head = git("rev-parse", "HEAD", cwd=epic_wt)
    assert _last(r.stdout) == f"MERGED {new_head}", out
    assert git("log", "-1", "--format=%P", cwd=epic_wt).split() == [epic_head, head]
    assert _runs(counter) == 2, out


def test_gate_failing_again_on_the_rerun_is_rejected_after_exactly_one_rerun(
    repo, worktree, run_script, tmp_path
):
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task(repo, worktree, epic_head)
    gate, counter = _flaky(tmp_path, "g", "always", "tests/test_other.py")
    r = _merge(run_script, repo, epic_wt, red, head, gate)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert _last(r.stdout).startswith(f"REJECTED {KEY}"), out
    assert _runs(counter) == 2, out
    assert _untouched(epic_wt, epic_head), out


def _contrast(run_script, repo, worktree, tmp_path, *failing: str):
    """Same task, same flake: first failing in <failing> (must not rerun, must reject), then in
    the untouched tests/test_other.py only (must rerun and merge)."""
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task(repo, worktree, epic_head)

    gate, counter = _flaky(tmp_path, "task-side", "first", *failing)
    r = _merge(run_script, repo, epic_wt, red, head, gate)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert _last(r.stdout).startswith(f"REJECTED {KEY}"), out
    assert _runs(counter) == 1, f"gate was rerun for a failure the task owns:\n{out}"
    assert _untouched(epic_wt, epic_head), out

    gate, counter = _flaky(tmp_path, "outside", "first", "tests/test_other.py")
    r = _merge(run_script, repo, epic_wt, red, head, gate)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert _last(r.stdout).startswith("MERGED "), out
    assert _runs(counter) == 2, out


def test_gate_failing_in_a_test_file_the_task_touched_is_not_rerun(
    repo, worktree, run_script, tmp_path
):
    _contrast(run_script, repo, worktree, tmp_path, "tests/test_task.py")


def test_gate_failing_in_a_test_file_that_imports_a_changed_file_is_not_rerun(
    repo, worktree, run_script, tmp_path
):
    _contrast(run_script, repo, worktree, tmp_path, "tests/test_base.py")


def test_gate_failing_in_both_an_untouched_and_a_task_test_file_is_not_rerun(
    repo, worktree, run_script, tmp_path
):
    _contrast(run_script, repo, worktree, tmp_path, "tests/test_other.py", "tests/test_task.py")


def test_gate_failing_without_naming_any_test_file_is_not_rerun(
    repo, worktree, run_script, tmp_path
):
    _contrast(run_script, repo, worktree, tmp_path)


# O11 --------------------------------------------------------------------------------------------


def _start_pair(repo: Path, worktree, tmp_path: Path, verdict_a: str = "pass"):
    """Two tasks on one epic head, touching different files; both merge-task.sh runs started at
    once. -> (epic_wt, epic_head, state dir, {name: (result stdout, returncode, head)})."""
    epic_wt, epic_head = _epic(repo, worktree)
    red_a, head_a = _task(repo, worktree, epic_head, "a", "T-A", {"src/a.py": "A = 1\n"})
    red_b, head_b = _task(repo, worktree, epic_head, "b", "T-B", {"src/b.py": "B = 1\n"})
    d = tmp_path / "pair"
    d.mkdir()
    script = tmp_path / "pair-gate.sh"
    script.write_text(PAIR_GATE, encoding="utf-8")

    def cmd(key, red, head, me, other, verdict):
        gate = f'bash "{script.as_posix()}" {me} {other} "{d.as_posix()}" {verdict}'
        return [BASH, (BIN / SCRIPT).as_posix(),
                "--worktree", epic_wt.as_posix(), "--branch", "epic",
                "--gate", gate, "--lint", LINT, key, red, head, GOAL]

    procs = {
        "a": subprocess.Popen(cmd("T-A", red_a, head_a, "a", "b", verdict_a), cwd=str(repo),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8"),
        "b": subprocess.Popen(cmd("T-B", red_b, head_b, "b", "a", "pass"), cwd=str(repo),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8"),
    }
    results = {}
    heads = {"a": head_a, "b": head_b}
    for name, p in procs.items():
        out, _ = p.communicate(timeout=180)
        results[name] = (out, p.returncode, heads[name])
    return epic_wt, epic_head, d, results


def _base(d: Path, name: str) -> str:
    f = d / f"{name}.base"
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def test_two_merges_started_together_both_merge_one_after_the_other(
    repo, worktree, tmp_path
):
    epic_wt, epic_head, d, res = _start_pair(repo, worktree, tmp_path)
    report = "\n".join(f"--- {n} (exit {c})\n{o}" for n, (o, c, _) in res.items())
    assert res["a"][1] == 0 and res["b"][1] == 0, report
    assert _last(res["a"][0]).startswith("MERGED ") and _last(res["b"][0]).startswith("MERGED "), report
    overlap = d / "overlap"
    assert not overlap.exists(), overlap.read_text(encoding="utf-8") + report


def test_two_merges_started_together_the_second_is_gated_on_the_first_ones_merge(
    repo, worktree, tmp_path
):
    epic_wt, epic_head, d, res = _start_pair(repo, worktree, tmp_path)
    report = "\n".join(f"--- {n} (exit {c})\n{o}" for n, (o, c, _) in res.items())
    assert res["a"][1] == 0 and res["b"][1] == 0, report
    merged = {n: _last(o).split()[-1] for n, (o, _, _) in res.items()}
    first, second = ("a", "b") if _base(d, "a") == epic_head else ("b", "a")
    assert _base(d, first) == epic_head, report
    assert _base(d, second) == merged[first], report
    assert git("rev-parse", "HEAD", cwd=epic_wt) == merged[second]
    parents = git("log", "-1", "--format=%P", merged[second], cwd=epic_wt).split()
    assert parents == [merged[first], res[second][2]], report


def test_a_rejected_merge_releases_the_lock_for_the_one_waiting(repo, worktree, tmp_path):
    epic_wt, epic_head, d, res = _start_pair(repo, worktree, tmp_path, verdict_a="fail")
    report = "\n".join(f"--- {n} (exit {c})\n{o}" for n, (o, c, _) in res.items())
    assert res["a"][1] == 1 and _last(res["a"][0]).startswith("REJECTED T-A"), report
    assert res["b"][1] == 0 and _last(res["b"][0]).startswith("MERGED "), report
    assert _base(d, "b") == epic_head, report
    assert not (d / "overlap").exists(), report
