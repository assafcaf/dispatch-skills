"""install.sh ships the workflows, the gate-runner agent, the scripts, and the PAD version."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from conftest import BASH, BIN, PAYLOAD, ROOT, git


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


def test_install_ships_the_config_example_even_when_a_config_exists(repo):
    """/setup-workflow upgrade adds missing sections from `.claude/workflow/config.example.md`,
    so the template is installed and refreshed; only config.md itself is the project's."""
    config = repo / ".claude" / "workflow" / "config.md"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("# Workflow config\n\nmine\n", encoding="utf-8")
    assert _install(repo).returncode == 0
    example = repo / ".claude" / "workflow" / "config.example.md"
    assert example.is_file()
    assert example.read_text(encoding="utf-8") == (
        PAYLOAD / "claude" / "workflow" / "config.example.md"
    ).read_text(encoding="utf-8")
    assert config.read_text(encoding="utf-8") == "# Workflow config\n\nmine\n"


def _packaged_copy(dest: Path) -> Path:
    """A copy of install.sh and the payload outside any git checkout, as npx unpacks it."""
    dest.mkdir()
    shutil.copy(ROOT / "install.sh", dest / "install.sh")
    shutil.copytree(PAYLOAD, dest / "payload")
    return dest


def _install_from(source: Path, project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, (source / "install.sh").as_posix(), "--project", project.as_posix(),
         "--tracker", "local"],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=120,
    )


def test_install_from_a_git_checkout_records_its_commit_in_the_lock(repo, tmp_path):
    """/pad-update merges from the commit in `.claude/workflow/pad.lock`."""
    source = _packaged_copy(tmp_path / "pad-checkout")
    (source / "payload" / "migrations" / "0001-first.md").write_text("# 0001\n", encoding="utf-8")
    git("init", "-q", cwd=source)
    git("config", "user.name", "PAD Test", cwd=source)
    git("config", "user.email", "pad-test@example.invalid", cwd=source)
    git("config", "commit.gpgsign", "false", cwd=source)
    git("config", "core.autocrlf", "false", cwd=source)
    git("remote", "add", "origin", "https://example.invalid/pad", cwd=source)
    git("add", "-A", cwd=source)
    git("commit", "-q", "-m", "pad", cwd=source)
    commit = git("rev-parse", "HEAD", cwd=source)

    assert _install_from(source, repo).returncode == 0
    lock = (repo / ".claude" / "workflow" / "pad.lock").read_text(encoding="utf-8").splitlines()
    version = (PAYLOAD / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()
    assert "source: https://example.invalid/pad" in lock
    assert f"commit: {commit}" in lock
    assert f"version: {version}" in lock
    assert "migration: 0001" in lock


def test_install_from_a_packaged_copy_writes_no_lock_and_drops_a_stale_one(repo, tmp_path):
    """Without a commit the lock would name files it does not describe."""
    source = _packaged_copy(tmp_path / "pad-package")
    lock = repo / ".claude" / "workflow" / "pad.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("commit: 0123456\n", encoding="utf-8")
    assert _install_from(source, repo).returncode == 0
    assert not lock.exists()


def test_install_copies_the_pad_update_skill(repo):
    assert _install(repo).returncode == 0
    assert (repo / ".claude" / "skills" / "pad-update" / "SKILL.md").is_file()
