"""pad-update.sh brings an installed harness up to a newer PAD commit and keeps local edits.

    pad-update.sh [--pad <clone>] [--project <dir>] [--to <ref>] [--base <sha>] [--dry-run]
    pad-update.sh --find-base ...
    pad-update.sh --record ...

One line per file that changes hands (REPLACE, KEEP, MERGE, CONFLICT, ADD, DELETE, GONE), then
SETTINGS and MIGRATION lines, a SUMMARY, and `UPDATE OK` (exit 0) or `UPDATE CONFLICTS <n>`
(exit 1).

The fixture is a throwaway PAD clone with a small payload and a project that installed it: the
project's `.claude/` is the clone's `payload/claude/` at the base commit.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conftest import BASH, ROOT, git

TEXT = "one\ntwo\nthree\nfour\nfive\nsix\nseven\n"
BASE_FILES = {
    "claude/workflow/VERSION": "0.2.0\n",
    "claude/workflow/doc.md": TEXT,
    "claude/workflow/bin/gate.sh": "#!/usr/bin/env bash\necho gate\n",
    "claude/skills/spec/SKILL.md": "spec\n",
    "claude/agents/tracker.md": "tools: Read\n",
    "claude/settings.example.json": "{}\n",
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _commit(pad: Path, files: dict, message: str, remove: tuple = ()) -> str:
    for rel, text in files.items():
        _write(pad, f"payload/{rel}", text)
    for rel in remove:
        git("rm", "-q", f"payload/{rel}", cwd=pad)
    git("add", "-A", cwd=pad)
    git("commit", "-q", "-m", message, cwd=pad)
    return git("rev-parse", "HEAD", cwd=pad)


@pytest.fixture
def pad(tmp_path: Path) -> Path:
    """A PAD clone with one commit: the base payload."""
    clone = tmp_path / "pad"
    clone.mkdir()
    git("init", "-q", cwd=clone)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=clone)
    git("config", "user.name", "PAD Test", cwd=clone)
    git("config", "user.email", "pad-test@example.invalid", cwd=clone)
    git("config", "commit.gpgsign", "false", cwd=clone)
    git("config", "core.autocrlf", "false", cwd=clone)
    _commit(clone, BASE_FILES, "base")
    return clone


def _install(pad: Path, project: Path, lock: bool = True) -> str:
    """Copy the clone's payload at HEAD into the project, as install.sh would."""
    base = git("rev-parse", "HEAD", cwd=pad)
    for rel in git("ls-files", "payload/claude", cwd=pad).splitlines():
        if rel.endswith("settings.example.json"):
            continue
        _write(project, ".claude/" + rel[len("payload/claude/"):],
               (pad / rel).read_bytes().decode("utf-8"))
    if lock:
        _write(project, ".claude/workflow/pad.lock",
               f"source: https://example.invalid/pad\ncommit: {base}\nversion: 0.2.0\nmigration: 0000\n")
    return base


def _run(pad: Path, project: Path, *args: str) -> subprocess.CompletedProcess:
    script = ROOT / "payload" / "claude" / "workflow" / "bin" / "pad-update.sh"
    return subprocess.run(
        [BASH, script.as_posix(), "--pad", pad.as_posix(), "--project", project.as_posix(), *args],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=120,
    )


def _last(result: subprocess.CompletedProcess) -> str:
    return result.stdout.strip().splitlines()[-1]


def _read(project: Path, rel: str) -> str:
    return (project / rel).read_bytes().decode("utf-8")


def test_an_untouched_file_is_replaced_with_the_new_one(pad, repo):
    _install(pad, repo)
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "grow doc")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "REPLACE .claude/workflow/doc.md" in result.stdout.splitlines()
    assert _read(repo, ".claude/workflow/doc.md") == TEXT + "eight\n"
    assert _last(result) == "UPDATE OK"


def test_a_file_only_the_project_changed_is_kept(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/skills/spec/SKILL.md", "spec, ours\n")
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "grow doc")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(l.startswith("KEEP .claude/skills/spec/SKILL.md") for l in result.stdout.splitlines())
    assert _read(repo, ".claude/skills/spec/SKILL.md") == "spec, ours\n"


def test_changes_on_both_sides_are_merged(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/workflow/doc.md", TEXT.replace("one\n", "one, ours\n"))
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "grow doc")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MERGE .claude/workflow/doc.md" in result.stdout.splitlines()
    assert _read(repo, ".claude/workflow/doc.md") == TEXT.replace("one\n", "one, ours\n") + "eight\n"


def test_a_clash_leaves_markers_and_is_counted(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/workflow/doc.md", TEXT.replace("four", "four, ours"))
    _commit(pad, {"claude/workflow/doc.md": TEXT.replace("four", "four, theirs")}, "change four")
    result = _run(pad, repo)
    assert result.returncode == 1
    assert any(l.startswith("CONFLICT .claude/workflow/doc.md") for l in result.stdout.splitlines())
    merged = _read(repo, ".claude/workflow/doc.md")
    assert "<<<<<<<" in merged and "four, ours" in merged and "four, theirs" in merged
    assert _last(result) == "UPDATE CONFLICTS 1"


def test_a_new_upstream_script_is_added_executable(pad, repo):
    _install(pad, repo)
    _commit(pad, {"claude/workflow/bin/new.sh": "#!/usr/bin/env bash\necho new\n"}, "add new.sh")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ADD .claude/workflow/bin/new.sh" in result.stdout.splitlines()
    added = repo / ".claude" / "workflow" / "bin" / "new.sh"
    assert subprocess.run([BASH, "-c", f'test -x "{added.as_posix()}"'], check=False).returncode == 0
    staged = git("ls-files", "-s", ".claude/workflow/bin/new.sh", cwd=repo)
    assert staged.startswith("100755")


def test_a_file_pad_retired_is_deleted_when_untouched(pad, repo):
    _install(pad, repo)
    _commit(pad, {}, "retire spec", remove=("claude/skills/spec/SKILL.md",))
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DELETE .claude/skills/spec/SKILL.md" in result.stdout.splitlines()
    assert not (repo / ".claude" / "skills" / "spec" / "SKILL.md").exists()


def test_a_retired_file_the_project_changed_is_kept_as_a_conflict(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/skills/spec/SKILL.md", "spec, ours\n")
    _commit(pad, {}, "retire spec", remove=("claude/skills/spec/SKILL.md",))
    result = _run(pad, repo)
    assert result.returncode == 1
    assert _read(repo, ".claude/skills/spec/SKILL.md") == "spec, ours\n"
    assert _last(result) == "UPDATE CONFLICTS 1"


def test_a_file_the_project_removed_stays_removed(pad, repo):
    _install(pad, repo)
    (repo / ".claude" / "skills" / "spec" / "SKILL.md").unlink()
    _commit(pad, {"claude/skills/spec/SKILL.md": "spec v2\n"}, "spec v2")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(l.startswith("GONE .claude/skills/spec/SKILL.md") for l in result.stdout.splitlines())
    assert not (repo / ".claude" / "skills" / "spec" / "SKILL.md").exists()


def test_the_projects_own_files_are_never_touched(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/agents/tracker.md", "tools: Read, Edit\n")
    _write(repo, ".claude/workflow/config.md", "mine\n")
    _write(repo, ".claude/settings.json", '{"mine": true}\n')
    _commit(pad, {"claude/agents/tracker.md": "tools: Bash\n",
                  "claude/settings.example.json": '{"new": 1}\n'}, "tracker and settings")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _read(repo, ".claude/agents/tracker.md") == "tools: Read, Edit\n"
    assert _read(repo, ".claude/workflow/config.md") == "mine\n"
    assert _read(repo, ".claude/settings.json") == '{"mine": true}\n'
    assert not (repo / ".claude" / "settings.example.json").exists()
    assert any(l.startswith("SETTINGS ") for l in result.stdout.splitlines())


def test_crlf_in_the_project_is_not_a_local_edit(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/workflow/doc.md", TEXT.replace("\n", "\r\n"))
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "grow doc")
    result = _run(pad, repo)
    assert "REPLACE .claude/workflow/doc.md" in result.stdout.splitlines()
    assert _read(repo, ".claude/workflow/doc.md") == TEXT + "eight\n"


def test_a_second_run_changes_nothing(pad, repo):
    _install(pad, repo)
    _write(repo, ".claude/workflow/doc.md", TEXT.replace("one\n", "one, ours\n"))
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n",
                  "claude/workflow/bin/gate.sh": "#!/usr/bin/env bash\necho gate v2\n"}, "v2")
    assert _run(pad, repo).returncode == 0
    before = {p: p.read_bytes() for p in (repo / ".claude").rglob("*") if p.is_file()}
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    after = {p: p.read_bytes() for p in (repo / ".claude").rglob("*") if p.is_file()}
    assert after == before
    assert "REPLACE" not in result.stdout and "CONFLICT" not in result.stdout


def test_dry_run_prints_the_actions_and_changes_nothing(pad, repo):
    _install(pad, repo)
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n",
                  "claude/workflow/bin/new.sh": "#!/usr/bin/env bash\n"}, "v2",
            remove=("claude/skills/spec/SKILL.md",))
    before = {p: p.read_bytes() for p in (repo / ".claude").rglob("*") if p.is_file()}
    result = _run(pad, repo, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert "REPLACE .claude/workflow/doc.md" in lines
    assert "ADD .claude/workflow/bin/new.sh" in lines
    assert "DELETE .claude/skills/spec/SKILL.md" in lines
    assert {p: p.read_bytes() for p in (repo / ".claude").rglob("*") if p.is_file()} == before


def test_to_names_the_target_commit(pad, repo):
    _install(pad, repo)
    middle = _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "v2")
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\nnine\n"}, "v3")
    result = _run(pad, repo, "--to", middle)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _read(repo, ".claude/workflow/doc.md") == TEXT + "eight\n"


def test_pending_migrations_are_listed_in_order_and_older_ones_are_not(pad, repo):
    _commit(pad, {"migrations/0001-first.md": "# 0001\n"}, "note 1")
    _install(pad, repo)
    lock = repo / ".claude" / "workflow" / "pad.lock"
    lock.write_text(lock.read_text(encoding="utf-8").replace("migration: 0000", "migration: 0001"),
                    encoding="utf-8")
    _commit(pad, {"migrations/0003-third.md": "# 0003\n", "migrations/0002-second.md": "# 0002\n",
                  "migrations/README.md": "format\n"}, "notes 2 and 3")
    result = _run(pad, repo)
    assert result.returncode == 0, result.stdout + result.stderr
    notes = [l for l in result.stdout.splitlines() if l.startswith("MIGRATION ")]
    assert notes == ["MIGRATION payload/migrations/0002-second.md",
                     "MIGRATION payload/migrations/0003-third.md"]


def test_without_a_lock_or_a_base_it_refuses_and_names_find_base(pad, repo):
    _install(pad, repo, lock=False)
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "grow doc")
    result = _run(pad, repo)
    assert result.returncode == 2
    assert "--find-base" in result.stderr
    assert _read(repo, ".claude/workflow/doc.md") == TEXT


def test_base_stands_in_for_a_missing_lock_and_skips_the_notes_it_already_had(pad, repo):
    _commit(pad, {"migrations/0001-first.md": "# 0001\n"}, "note 1")
    base = _install(pad, repo, lock=False)
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n",
                  "migrations/0002-second.md": "# 0002\n"}, "v2")
    result = _run(pad, repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _read(repo, ".claude/workflow/doc.md") == TEXT + "eight\n"
    notes = [l for l in result.stdout.splitlines() if l.startswith("MIGRATION ")]
    assert notes == ["MIGRATION payload/migrations/0002-second.md"]


def test_find_base_picks_the_commit_the_project_was_installed_from(pad, repo):
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "v2")
    installed_from = _install(pad, repo, lock=False)
    _write(repo, ".claude/skills/spec/SKILL.md", "spec, ours\n")
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\nnine\n",
                  "claude/workflow/bin/gate.sh": "#!/usr/bin/env bash\necho gate v3\n"}, "v3")
    result = _run(pad, repo, "--find-base")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _last(result).startswith(f"BASE {installed_from} ")


def test_find_base_refuses_when_too_little_matches(pad, repo):
    _install(pad, repo, lock=False)
    for rel in ("workflow/doc.md", "workflow/bin/gate.sh", "skills/spec/SKILL.md"):
        _write(repo, f".claude/{rel}", "rewritten here\n")
    result = _run(pad, repo, "--find-base")
    assert result.returncode == 1
    assert _last(result).startswith("BASE NONE ")


def test_record_writes_the_lock_for_the_target(pad, repo):
    _install(pad, repo)
    target = _commit(pad, {"claude/workflow/VERSION": "0.3.0\n",
                           "migrations/0002-second.md": "# 0002\n"}, "0.3.0")
    result = _run(pad, repo, "--record")
    assert result.returncode == 0, result.stdout + result.stderr
    lock = _read(repo, ".claude/workflow/pad.lock").splitlines()
    assert "source: https://example.invalid/pad" in lock
    assert f"commit: {target}" in lock
    assert "version: 0.3.0" in lock
    assert "migration: 0002" in lock


def test_the_update_itself_does_not_write_the_lock(pad, repo):
    base = _install(pad, repo)
    _commit(pad, {"claude/workflow/doc.md": TEXT + "eight\n"}, "grow doc")
    assert _run(pad, repo).returncode == 0
    assert f"commit: {base}" in _read(repo, ".claude/workflow/pad.lock").splitlines()


def test_a_directory_that_is_not_a_pad_clone_is_refused(repo, tmp_path):
    result = _run(repo, repo)
    assert result.returncode == 2
    assert "payload" in result.stderr
