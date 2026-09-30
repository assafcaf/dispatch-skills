"""O25: suite-slot.sh caps concurrent full-suite runs at N slots, and merge gates go first.

    suite-slot.sh [--priority merge] -- <cmd...>

N comes from PAD_SUITE_SLOTS, else `Suite slots: <n>` in .claude/workflow/config.md, else 2.
Slots live under `<git common dir>/pad-locks/slots/`; the script exits with <cmd>'s code.

Each held run is a worker that marks itself inside, records how many are inside, and waits for
the test to release it. The test releases workers one at a time, so a correct implementation
passes however loaded the host is; the bounded waits only decide how hard a broken one is caught.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from conftest import BASH, BIN, git

SCRIPT = "suite-slot.sh"

WORKER = """\
d="$1"; id="$2"
touch "$d/in.$id"
echo "$id" >> "$d/order"
ls "$d" | grep -c '^in\\.' >> "$d/count.$id"
while [ ! -e "$d/release.$id" ]; do sleep 0.05; done
rm -f "$d/in.$id"
"""


class Slots:
    """Starts held runs through suite-slot.sh from `cwd` and drives them by file handshakes."""

    def __init__(self, tmp_path: Path, cwd: Path, env: dict[str, str]):
        self.d = tmp_path / "state"
        self.d.mkdir()
        self.worker = tmp_path / "worker.sh"
        self.worker.write_text(WORKER, encoding="utf-8")
        self.cwd = cwd
        self.env = env
        self.procs: dict[str, subprocess.Popen] = {}

    def start(self, wid: str, *flags: str) -> None:
        self.procs[wid] = subprocess.Popen(
            [BASH, (BIN / SCRIPT).as_posix(), *flags, "--",
             BASH, self.worker.as_posix(), self.d.as_posix(), wid],
            cwd=str(self.cwd), env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        )

    def inside(self) -> set[str]:
        return {p.name[3:] for p in self.d.glob("in.*")}

    def order(self) -> list[str]:
        f = self.d / "order"
        return f.read_text(encoding="utf-8").split() if f.exists() else []

    def counts(self) -> list[int]:
        return [int(x) for f in self.d.glob("count.*")
                for x in f.read_text(encoding="utf-8").split()]

    def wait(self, cond, timeout: float = 60.0) -> bool:
        """True once cond() holds; False on timeout or when every run has already exited."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if cond():
                return True
            if self.procs and all(p.poll() is not None for p in self.procs.values()):
                return cond()
            time.sleep(0.05)
        return cond()

    def release(self, wid: str) -> int:
        (self.d / f"release.{wid}").touch()
        return self.procs[wid].wait(timeout=60)

    def diag(self) -> str:
        lines = [f"inside={sorted(self.inside())} order={self.order()} counts={self.counts()}"]
        for wid, p in self.procs.items():
            if p.poll() is not None:
                lines.append(f"--- {wid} exit {p.returncode}\n{p.stdout.read()}")
        return "\n".join(lines)

    def finish(self) -> None:
        for wid in self.procs:
            (self.d / f"release.{wid}").touch()
        for p in self.procs.values():
            try:
                p.wait(timeout=60)
            except subprocess.TimeoutExpired:
                p.kill()


def _env(slots: str | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "PAD_SUITE_SLOTS"}
    if slots is not None:
        env["PAD_SUITE_SLOTS"] = slots
    return env


def _drain_one_at_a_time(s: Slots, n: int) -> None:
    """Wait until min(n, remaining) runs are inside, release one, repeat until all are done."""
    remaining = set(s.procs)
    while remaining:
        want = min(n, len(remaining))
        assert s.wait(lambda: len(s.inside() & remaining) >= want), s.diag()
        victim = sorted(s.inside() & remaining)[0]
        assert s.release(victim) == 0, s.diag()
        remaining.discard(victim)


def _locks(repo: Path) -> set[str]:
    root = repo / ".git" / "pad-locks"
    return {str(p.relative_to(root)) for p in root.rglob("*")} if root.exists() else set()


def test_suite_slot_exits_with_the_commands_exit_code_and_passes_its_output(repo, run_script):
    r = run_script(SCRIPT, "--", "bash", "-c", "echo out-7c1; exit 3", cwd=repo)
    assert r.returncode == 3, r.stdout + r.stderr
    assert "out-7c1" in r.stdout


def test_suite_slot_exits_zero_when_the_command_succeeds(repo, run_script):
    r = run_script(SCRIPT, "--", "bash", "-c", "echo ok-5d2", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ok-5d2" in r.stdout


def test_at_most_pad_suite_slots_runs_are_inside_at_once(repo, tmp_path):
    s = Slots(tmp_path, repo, _env("2"))
    try:
        for wid in ("w1", "w2", "w3", "w4"):
            s.start(wid)
        _drain_one_at_a_time(s, 2)
        assert max(s.counts()) == 2, s.diag()
        assert sorted(s.order()) == ["w1", "w2", "w3", "w4"], s.diag()
    finally:
        s.finish()


def test_suite_slots_line_in_config_sets_the_slot_count(repo, tmp_path):
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("# Config\n\n## Execution\n\n- Suite slots: 1\n", encoding="utf-8")
    s = Slots(tmp_path, repo, _env(None))
    try:
        for wid in ("w1", "w2", "w3"):
            s.start(wid)
        _drain_one_at_a_time(s, 1)
        assert max(s.counts()) == 1, s.diag()
        assert sorted(s.order()) == ["w1", "w2", "w3"], s.diag()
    finally:
        s.finish()


def test_slot_count_defaults_to_two_without_env_or_config(repo, tmp_path):
    s = Slots(tmp_path, repo, _env(None))
    try:
        for wid in ("w1", "w2", "w3"):
            s.start(wid)
        _drain_one_at_a_time(s, 2)
        assert max(s.counts()) == 2, s.diag()
    finally:
        s.finish()


def test_a_waiting_merge_run_takes_the_next_slot_before_a_waiting_task_run(repo, tmp_path):
    s = Slots(tmp_path, repo, _env("1"))
    try:
        s.start("holder")
        assert s.wait(lambda: s.inside() == {"holder"}), s.diag()

        before = _locks(repo)
        s.start("task")
        # Let the task run queue first, so a first-come-first-served slot would hand it the slot.
        s.wait(lambda: _locks(repo) != before, timeout=3)
        assert "task" not in s.inside(), s.diag()

        before = _locks(repo)
        s.start("merge", "--priority", "merge")
        s.wait(lambda: _locks(repo) != before, timeout=10)
        assert s.inside() == {"holder"}, s.diag()

        assert s.release("holder") == 0, s.diag()
        assert s.wait(lambda: len(s.order()) >= 2), s.diag()
        assert s.order()[1] == "merge", s.diag()
        assert s.release("merge") == 0, s.diag()
        assert s.wait(lambda: "task" in s.inside()), s.diag()
        assert s.release("task") == 0, s.diag()
    finally:
        s.finish()


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def test_merge_task_gate_waits_for_a_suite_slot(repo, worktree, tmp_path):
    epic = worktree(repo, "epic")
    epic_head = _commit(epic, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic)
    task = worktree(repo, "task")
    git("reset", "-q", "--hard", epic_head, cwd=task)
    red = _commit(task, {"tests/test_new.py": "def test_new():\n    assert False\n"},
                  "test(T-1): O25 [red]")
    head = _commit(task, {"src/impl.py": "X = 1\n"}, "feat(T-1): impl")

    s = Slots(tmp_path, repo, _env("1"))
    gate_ran = tmp_path / "gate-ran"
    try:
        s.start("holder")
        assert s.wait(lambda: s.inside() == {"holder"}), s.diag()
        merge = subprocess.Popen(
            [BASH, (BIN / "merge-task.sh").as_posix(),
             "--worktree", epic.as_posix(), "--branch", "epic",
             "--gate", f'touch "{gate_ran.as_posix()}"', "--lint", "true",
             "T-1", red, head, "Add the impl"],
            cwd=str(repo), env=_env("1"),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        )
        s.procs["merge-task"] = merge
        s.wait(lambda: gate_ran.exists(), timeout=5)
        assert not gate_ran.exists(), "merge gate ran while every suite slot was held\n" + s.diag()

        assert s.release("holder") == 0, s.diag()
        out, _ = merge.communicate(timeout=120)
        assert merge.returncode == 0, out
        assert out.strip().splitlines()[-1].startswith("MERGED "), out
        assert gate_ran.exists(), out
    finally:
        s.finish()
