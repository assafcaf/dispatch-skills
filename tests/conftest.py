"""Shared harness: throwaway git repos with linked worktrees, and a runner for payload scripts.

Everything here builds its own repos under pytest's tmp_path and reads only `payload/` from this
checkout, never the installed `.claude/`. It must behave the same under Git Bash on Windows and
bash on Linux, with git as old as 2.23 (no `git init -b`, no `--path-format`).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "payload"
BIN = PAYLOAD / "claude" / "workflow" / "bin"


def _find_bash() -> str:
    """The bash that runs payload scripts. On Windows, prefer Git's own bash over WSL's."""
    override = os.environ.get("PAD_BASH")
    if override:
        return override
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for parent in Path(git).resolve().parents:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
    bash = shutil.which("bash")
    if not bash:
        raise RuntimeError("bash is not available: install it or set PAD_BASH")
    return bash


BASH = _find_bash()


def git(*args: str, cwd: Path) -> str:
    """Run git in cwd, fail loudly, and return stdout stripped."""
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\n{result.stderr}")
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fresh git repo on branch `main` with one commit, pushed to a bare `origin`."""
    origin = tmp_path / "origin.git"
    main = tmp_path / "main"
    origin.mkdir()
    main.mkdir()
    git("init", "--bare", "-q", cwd=origin)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=origin)
    git("init", "-q", cwd=main)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=main)
    git("config", "user.name", "PAD Test", cwd=main)
    git("config", "user.email", "pad-test@example.invalid", cwd=main)
    git("config", "commit.gpgsign", "false", cwd=main)
    git("config", "core.autocrlf", "false", cwd=main)
    (main / "README.md").write_text("fixture repo\n", encoding="utf-8")
    git("add", "README.md", cwd=main)
    git("commit", "-q", "-m", "initial", cwd=main)
    git("remote", "add", "origin", origin.as_posix(), cwd=main)
    git("push", "-q", "-u", "origin", "main", cwd=main)
    return main


@pytest.fixture
def worktree():
    """Factory: worktree(repo, name) -> Path of a linked worktree on new branch `name` from main.

    The worktree sits beside the repo, not inside it, so a script can't find the main checkout
    by walking up from its working directory.
    """

    def make(repo: Path, name: str) -> Path:
        path = repo.parent / f"wt-{name}"
        git("worktree", "add", "-q", "-b", name, path.as_posix(), "main", cwd=repo)
        return path

    return make


@pytest.fixture
def run_script():
    """Factory: run_script(name, *args, cwd, env=None) -> CompletedProcess (text mode).

    Runs `bash payload/claude/workflow/bin/<name> *args` in cwd. `env`, when given, is merged
    over the current environment.
    """

    def run(name: str, *args: str, cwd: Path, env: dict | None = None):
        script = BIN / name
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        return subprocess.run(
            [BASH, script.as_posix(), *args],
            cwd=str(cwd),
            env=full_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=120,
        )

    return run


@pytest.fixture
def payload_text():
    """Factory: payload_text(relpath) -> the text of payload/<relpath>."""

    def read(relpath: str) -> str:
        return (PAYLOAD / relpath).read_text(encoding="utf-8")

    return read
