"""install.sh ships the workflows, the gate-runner agent, the scripts, and the PAD version."""
from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import BASH, BIN, PAYLOAD, ROOT


def _install(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, (ROOT / "install.sh").as_posix(), "--project", project.as_posix(),
         "--tracker", "local"],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=120,
    )


def _is_executable(path: Path) -> bool:
    return subprocess.run(
        [BASH, "-c", f'test -x "{path.as_posix()}"'], check=False
    ).returncode == 0


def test_install_copies_the_pad_task_workflow(repo):
    result = _install(repo)
    assert result.returncode == 0, result.stderr
    installed = repo / ".claude" / "workflows" / "pad-task.js"
    assert installed.is_file()
    assert installed.read_text(encoding="utf-8") == (
        PAYLOAD / "claude" / "workflows" / "pad-task.js"
    ).read_text(encoding="utf-8")


def test_install_copies_the_gate_runner_agent(repo):
    assert _install(repo).returncode == 0
    installed = repo / ".claude" / "agents" / "gate-runner.md"
    assert installed.is_file()
    assert installed.read_text(encoding="utf-8") == (
        PAYLOAD / "claude" / "agents" / "gate-runner.md"
    ).read_text(encoding="utf-8")


def test_install_copies_every_script_and_leaves_it_executable(repo):
    assert _install(repo).returncode == 0
    scripts = sorted(p.name for p in BIN.glob("*.sh"))
    assert scripts
    for name in scripts:
        installed = repo / ".claude" / "workflow" / "bin" / name
        assert installed.is_file(), name
        assert _is_executable(installed), name


def test_install_copies_the_version_file(repo):
    assert _install(repo).returncode == 0
    installed = repo / ".claude" / "workflow" / "VERSION"
    assert installed.is_file()
    assert installed.read_text(encoding="utf-8").strip() == (
        PAYLOAD / "claude" / "workflow" / "VERSION"
    ).read_text(encoding="utf-8").strip()


def test_install_writes_the_pad_version_into_config(repo):
    assert _install(repo).returncode == 0
    version = (PAYLOAD / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()
    assert version
    config = (repo / ".claude" / "workflow" / "config.md").read_text(encoding="utf-8")
    assert f"PAD version: {version}" in config.splitlines()
    assert "<PAD_VERSION>" not in config
