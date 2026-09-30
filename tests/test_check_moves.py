"""O2: check-moves.sh proves each Git moves capability is allowed by the effective settings.

Every settings layer is built here from fixtures; nothing reads this repo's own .claude/.
Rule forms follow Claude Code: exact `Bash(cmd)`, prefix `Bash(cmd:*)` (a word boundary, like a
trailing ` *`), and `*` globs anywhere. Deny beats allow in any layer; a command matching no rule
would prompt, so it fails too. Placeholders (`<sha>`, `<branch>`, `<path>`) stand for any value.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SCRIPT = "check-moves.sh"

MOVES = {
    "branch-from-epic-head": "git switch -c <branch> <sha>",
    "move-onto-sha": "git reset --hard <sha>",
    "take-red": "git merge --ff-only <sha>",
    "rebase-red": "git rebase <sha>",
    "discard-changes": "git checkout -- <path>",
    "set-aside-work": "git stash push -u",
    "try-merge": "git merge --no-ff --no-commit <branch>",
    "abort-merge": "git merge --abort",
    "commit-merge": "git commit --no-edit",
    "revert-merge": "git revert -m 1 <sha>",
    "push-epic": "git push origin <branch>",
    "remove-worktree": "git worktree remove <path>",
    "delete-merged-branch": "git branch -d <branch>",
}

# Each layer uniquely allows some capabilities, so ignoring any layer fails the check.
USER_ALLOW = [
    "Bash(git switch -c:*)",
    "Bash(git reset --hard:*)",
    "Bash(git merge --ff-only:*)",
    "Bash(git rebase:*)",
    "Read(**)",
]
PROJECT_ALLOW = [
    "Bash(git checkout -- *)",
    "Bash(git stash push -u)",
    "Bash(git merge --no-ff --no-commit:*)",
    "Bash(git merge --abort)",
    "Bash(git status)",
]
LOCAL_ALLOW = [
    "Bash(git commit --no-edit)",
    "Bash(git revert -m 1 *)",
    "Bash(git push origin *)",
    "Bash(git worktree remove:*)",
    "Bash(git branch -d:*)",
]

FAIL_LINE = re.compile(
    r'^MOVES FAIL (?P<cap>[a-z-]+): (?P<cmd>.+) — add "Bash\((?P<pattern>.+)\)" to permissions\.allow$'
)


def config_md(moves: dict[str, str] = MOVES, section: bool = True) -> str:
    rows = "".join(f"| `{cap}` | `{cmd}` |\n" for cap, cmd in moves.items())
    moves_section = (
        "## Git moves\n\n| Capability | Command |\n|---|---|\n" + rows + "\n" if section else ""
    )
    return (
        "# Workflow config\n\n"
        "## Tracker\n\n- **Adapter:** `local`.\n\n"
        + moves_section
        + "## Commands\n\n| Gate | Command |\n|---|---|\n"
        "| Full suite | `python -m pytest -q tests` |\n"
        "| Lint | `true` |\n"
    )


def settings_json(allow=(), deny=(), extra: dict | None = None) -> str:
    data = {"permissions": {"allow": list(allow), "deny": list(deny)}}
    if extra:
        data.update(extra)
    return json.dumps(data, indent=2)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class Stack:
    """Three explicit settings layers plus a config, passed with --config/--settings."""

    def __init__(self, root: Path):
        self.root = root
        self.config = write(root / "config.md", config_md())
        self.user = {"allow": list(USER_ALLOW), "deny": []}
        self.project = {"allow": list(PROJECT_ALLOW), "deny": []}
        self.local = {"allow": list(LOCAL_ALLOW), "deny": []}

    def run(self, run_script):
        paths = []
        for name, layer in (("user", self.user), ("project", self.project), ("local", self.local)):
            paths.append(write(self.root / f"{name}.json", settings_json(**layer)))
        args = ["--config", self.config.as_posix()]
        for p in paths:
            args += ["--settings", p.as_posix()]
        return run_script(SCRIPT, *args, cwd=self.root)


def lines(result) -> list[str]:
    return [line for line in result.stdout.strip().splitlines() if line.strip()]


def fails(result) -> dict[str, re.Match]:
    out = {}
    for line in lines(result):
        m = FAIL_LINE.match(line)
        if m:
            out[m.group("cap")] = m
    return out


def fail_caps(result) -> set[str]:
    return {
        line.split()[2].rstrip(":")
        for line in lines(result)
        if line.startswith("MOVES FAIL ")
    }


def assert_ok(result):
    assert result.returncode == 0, result.stdout + result.stderr
    assert lines(result)[-1] == "MOVES OK"
    assert not any(line.startswith("MOVES FAIL") for line in lines(result))


def assert_only_fails(result, *caps: str):
    assert result.returncode == 1, result.stdout + result.stderr
    assert fail_caps(result) == set(caps), result.stdout
    assert lines(result)[-1].startswith("MOVES FAIL "), result.stdout
    assert "MOVES OK" not in lines(result)


# --- all allowed ---------------------------------------------------------------------------


def test_o2_every_capability_allowed_across_three_layers_prints_moves_ok(tmp_path, run_script):
    assert_ok(Stack(tmp_path).run(run_script))


def test_o2_default_paths_read_user_project_and_local_settings(repo, tmp_path, run_script):
    home = tmp_path / "home"
    write(home / ".claude" / "settings.json", settings_json(USER_ALLOW))
    write(repo / ".claude" / "settings.json", settings_json(PROJECT_ALLOW))
    write(repo / ".claude" / "settings.local.json", settings_json(LOCAL_ALLOW))
    write(repo / ".claude" / "workflow" / "config.md", config_md())

    result = run_script(
        SCRIPT, cwd=repo, env={"HOME": home.as_posix(), "USERPROFILE": str(home)}
    )

    assert_ok(result)


def test_o2_default_paths_deny_in_user_settings_fails_capability(repo, tmp_path, run_script):
    home = tmp_path / "home"
    write(
        home / ".claude" / "settings.json",
        settings_json(USER_ALLOW, deny=["Bash(git push:*)"]),
    )
    write(repo / ".claude" / "settings.json", settings_json(PROJECT_ALLOW))
    write(repo / ".claude" / "settings.local.json", settings_json(LOCAL_ALLOW))
    write(repo / ".claude" / "workflow" / "config.md", config_md())

    result = run_script(
        SCRIPT, cwd=repo, env={"HOME": home.as_posix(), "USERPROFILE": str(home)}
    )

    assert_only_fails(result, "push-epic")


def test_o2_default_paths_missing_local_settings_file_is_not_an_error(repo, tmp_path, run_script):
    home = tmp_path / "home"
    write(home / ".claude" / "settings.json", settings_json(USER_ALLOW))
    write(repo / ".claude" / "settings.json", settings_json(PROJECT_ALLOW + LOCAL_ALLOW))
    write(repo / ".claude" / "workflow" / "config.md", config_md())

    result = run_script(
        SCRIPT, cwd=repo, env={"HOME": home.as_posix(), "USERPROFILE": str(home)}
    )

    assert_ok(result)


def test_o2_settings_without_permissions_key_contribute_no_rules(tmp_path, run_script):
    config = Stack(tmp_path).config.as_posix()
    user = write(tmp_path / "u.json", settings_json(USER_ALLOW))
    project = write(tmp_path / "p.json", settings_json(PROJECT_ALLOW + LOCAL_ALLOW))
    local = write(tmp_path / "l.json", json.dumps({"env": {"FOO": "1"}}))

    result = run_script(
        SCRIPT,
        "--config", config,
        "--settings", user.as_posix(),
        "--settings", project.as_posix(),
        "--settings", local.as_posix(),
        cwd=tmp_path,
    )

    assert_ok(result)


# --- would prompt ----------------------------------------------------------------------------


def test_o2_command_matching_no_rule_fails_naming_capability_and_command(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["allow"].remove("Bash(git rebase:*)")

    result = stack.run(run_script)

    assert_only_fails(result, "rebase-red")
    assert fails(result)["rebase-red"].group("cmd") == "git rebase <sha>"


def test_o2_suggested_allow_rule_makes_failing_capability_pass(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["allow"].remove("Bash(git rebase:*)")
    failing = fails(stack.run(run_script))
    assert "rebase-red" in failing
    pattern = failing["rebase-red"].group("pattern")
    assert pattern.startswith("git rebase")

    stack.local["allow"].append(f"Bash({pattern})")

    assert_ok(stack.run(run_script))


def test_o2_suggested_rule_for_command_without_placeholder_makes_it_pass(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.project["allow"].remove("Bash(git merge --abort)")
    failing = fails(stack.run(run_script))
    assert "abort-merge" in failing
    assert failing["abort-merge"].group("cmd") == "git merge --abort"

    stack.user["allow"].append(f"Bash({failing['abort-merge'].group('pattern')})")

    assert_ok(stack.run(run_script))


def test_o2_each_failing_capability_gets_its_own_line(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["allow"].remove("Bash(git switch -c:*)")
    stack.local["allow"].remove("Bash(git worktree remove:*)")
    stack.local["allow"].remove("Bash(git branch -d:*)")

    result = stack.run(run_script)

    assert_only_fails(result, "branch-from-epic-head", "remove-worktree", "delete-merged-branch")
    got = fails(result)
    assert got["branch-from-epic-head"].group("cmd") == "git switch -c <branch> <sha>"
    assert got["remove-worktree"].group("cmd") == "git worktree remove <path>"
    assert got["delete-merged-branch"].group("cmd") == "git branch -d <branch>"


def test_o2_empty_settings_fail_every_capability(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user = {"allow": [], "deny": []}
    stack.project = {"allow": [], "deny": []}
    stack.local = {"allow": [], "deny": []}

    assert_only_fails(stack.run(run_script), *MOVES)


# --- deny ------------------------------------------------------------------------------------


def test_o2_deny_in_one_layer_beats_allow_in_another(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.local["deny"].append("Bash(git reset --hard:*)")

    result = stack.run(run_script)

    assert_only_fails(result, "move-onto-sha")
    assert result.stdout.count("MOVES FAIL move-onto-sha: git reset --hard <sha>") == 1


def test_o2_deny_glob_matching_command_fails_capability(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.project["deny"].append("Bash(git * origin *)")

    assert_only_fails(stack.run(run_script), "push-epic")


def test_o2_exact_deny_matching_command_fails_capability(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["deny"].append("Bash(git commit --no-edit)")

    assert_only_fails(stack.run(run_script), "commit-merge")


def test_o2_deny_rule_not_matching_command_leaves_it_allowed(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["deny"] += [
        "Bash(git push --force:*)",
        "Bash(git reset --soft:*)",
        "Bash(git branch -D:*)",
        "Bash(git merge --abortx)",
        "Read(./secrets/**)",
    ]

    assert_ok(stack.run(run_script))


# --- rule-matching forms ---------------------------------------------------------------------


def test_o2_exact_allow_rule_does_not_cover_command_with_more_words(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.local["allow"].remove("Bash(git branch -d:*)")
    stack.local["allow"].append("Bash(git branch -d)")

    assert_only_fails(stack.run(run_script), "delete-merged-branch")


def test_o2_prefix_rule_needs_a_word_boundary(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["allow"].remove("Bash(git rebase:*)")
    stack.user["allow"].append("Bash(git rebas:*)")

    assert_only_fails(stack.run(run_script), "rebase-red")


def test_o2_prefix_rule_for_another_command_does_not_allow(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["allow"].remove("Bash(git reset --hard:*)")
    stack.user["allow"].append("Bash(git reset --soft:*)")

    assert_only_fails(stack.run(run_script), "move-onto-sha")


def test_o2_glob_with_star_in_the_middle_allows_command(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user["allow"].remove("Bash(git reset --hard:*)")
    stack.user["allow"].append("Bash(git * --hard *)")

    assert_ok(stack.run(run_script))


def test_o2_broad_glob_allows_every_git_command(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.user = {"allow": ["Bash(git *)"], "deny": []}
    stack.project = {"allow": [], "deny": []}
    stack.local = {"allow": [], "deny": []}

    assert_ok(stack.run(run_script))


def test_o2_glob_with_different_literal_does_not_allow(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.local["allow"].remove("Bash(git push origin *)")
    stack.local["allow"].append("Bash(git push upstream *)")

    assert_only_fails(stack.run(run_script), "push-epic")


def test_o2_non_bash_rule_naming_the_command_does_not_allow(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.project["allow"].remove("Bash(git stash push -u)")
    stack.project["allow"].append("PowerShell(git stash push -u)")

    assert_only_fails(stack.run(run_script), "set-aside-work")


# --- config ----------------------------------------------------------------------------------


def test_o2_rows_outside_git_moves_section_are_not_checked(tmp_path, run_script):
    # The fixture config has a Commands table after Git moves whose commands no rule allows.
    stack = Stack(tmp_path)
    assert "python -m pytest" in stack.config.read_text(encoding="utf-8")

    assert_ok(stack.run(run_script))


def test_o2_capability_missing_from_table_fails_naming_it(tmp_path, run_script):
    stack = Stack(tmp_path)
    moves = {k: v for k, v in MOVES.items() if k != "delete-merged-branch"}
    write(stack.config, config_md(moves))

    result = stack.run(run_script)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "delete-merged-branch" in fail_caps(result), result.stdout
    assert "MOVES OK" not in lines(result)


def test_o2_config_without_git_moves_section_fails(tmp_path, run_script):
    stack = Stack(tmp_path)
    write(stack.config, config_md(section=False))

    result = stack.run(run_script)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "MOVES OK" not in result.stdout


def test_o2_missing_config_file_fails(tmp_path, run_script):
    stack = Stack(tmp_path)
    stack.config.unlink()

    result = stack.run(run_script)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "MOVES OK" not in result.stdout


def test_o2_malformed_settings_file_fails_rather_than_passing(tmp_path, run_script):
    stack = Stack(tmp_path)
    good = stack.run(run_script)
    assert_ok(good)
    # Hide a deny behind broken JSON: the check must not report OK without reading it.
    write(tmp_path / "broken.json", '{"permissions": {"deny": ["Bash(git push:*)"], }')

    result = run_script(
        SCRIPT,
        "--config", stack.config.as_posix(),
        "--settings", (tmp_path / "user.json").as_posix(),
        "--settings", (tmp_path / "project.json").as_posix(),
        "--settings", (tmp_path / "local.json").as_posix(),
        "--settings", (tmp_path / "broken.json").as_posix(),
        cwd=tmp_path,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "MOVES OK" not in result.stdout


# --- the shipped example ---------------------------------------------------------------------


def git_moves_rows(text: str) -> list[tuple[str, str]]:
    section = text.split("\n## Git moves\n", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] and not set(cells[0]) <= set("-:") and cells[0] != "Capability":
            rows.append((cells[0], cells[1]))
    return rows


def test_o2_config_example_git_moves_table_names_every_capability(payload_text):
    text = payload_text("claude/workflow/config.example.md")

    assert "\n## Git moves\n" in text
    assert "| Capability | Command |" in text.split("\n## Git moves\n", 1)[1]
    assert sorted(cap for cap, _ in git_moves_rows(text)) == sorted(MOVES)


def test_o2_config_example_table_is_checked_by_the_script(tmp_path, run_script):
    config = Path(__file__).resolve().parent.parent / "payload/claude/workflow/config.example.md"
    empty = write(tmp_path / "empty.json", settings_json())

    result = run_script(
        SCRIPT, "--config", config.as_posix(), "--settings", empty.as_posix(), cwd=tmp_path
    )

    assert_only_fails(result, *MOVES)
