"""E1-T25: preflight.sh proves a run's setup still holds before any agent starts (O39, O40).

`preflight.sh [--config <path>]` runs from the repo root. It prints one
`PREFLIGHT FAIL <check>: <detail>` line per failure, then `PREFLIGHT OK` or
`PREFLIGHT FAILED <n>`, and exits 0 or 1. Settings are the effective layers check-moves.sh
reads (`~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json`); HOME
points at an empty directory so the host's own settings never leak in. The installed payload
version is `VERSION` beside `bin/` (payload/claude/workflow/VERSION).

Check names used below: moves, commands, knowledge-paths, version, dependency-directory,
lockfile, models, plugins, executable, gitignore.

Every repo, config, settings file and agent file is built here; nothing reads this repo's own
.claude/.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

import pytest

from conftest import BIN, PAYLOAD, git

SCRIPT = "preflight.sh"
SKILL = "claude/skills/batch-implement/SKILL.md"
CONFIG_EXAMPLE = "claude/workflow/config.example.md"
OLD_VERSION = "0.1.0"

FAIL_LINE = re.compile(r"^PREFLIGHT FAIL (?P<check>[a-z-]+): (?P<detail>.+)$")

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

MOVES_ALLOW = [
    "Bash(git switch -c:*)",
    "Bash(git reset --hard:*)",
    "Bash(git merge --ff-only:*)",
    "Bash(git rebase:*)",
    "Bash(git checkout -- *)",
    "Bash(git stash push -u)",
    "Bash(git merge --no-ff --no-commit:*)",
    "Bash(git merge --abort)",
    "Bash(git commit --no-edit)",
    "Bash(git revert -m 1 *)",
    "Bash(git push origin *)",
    "Bash(git worktree remove:*)",
    "Bash(git branch -d:*)",
]

SETUP_RULE = "Bash(pip install -e .)"
PYTEST_RULE = "Bash(python -m pytest:*)"
TRUE_RULE = "Bash(true)"
PREVIEW_RULE = "Bash(npm run dev)"
WEAKENED_RULE = "Bash(bash .claude/workflow/bin/weakened-tests.sh:*)"
SCRIPTS_RULE = "Bash(bash .claude/workflow/bin/*)"

ALLOW = MOVES_ALLOW + [
    SETUP_RULE, PYTEST_RULE, TRUE_RULE, PREVIEW_RULE, WEAKENED_RULE, SCRIPTS_RULE,
]

# Agent -> model, as the fixture config's Agents table and Tiers `standard` row say.
AGENTS = {
    "tracker": "haiku",
    "task-planner": "sonnet",
    "ticket-owner": "sonnet",
    "test-designer": "sonnet",
    "code-writer": "sonnet",
    "knowledge-scanner": "sonnet",
    "memory-curator": "sonnet",
}

GITIGNORE = [".work/", ".claude/worktrees/", "CLAUDE.local.md", ".claude/settings.local.json"]

# The `## ` sections of a current config, in the order config.example.md has them.
SECTIONS = {
    "Tracker": """- **Adapter:** `local`. Operations are in `.claude/workflow/trackers/local.md`.
- **Statuses:** todo `To Do`, doing `In Progress`, review `In Review`, done `Done`.
""",
    "Agents": """| Role | Agent | Model | Notes |
|---|---|---|---|
| Tracker | `tracker` | `haiku` | tracker tools |
| Planning | `task-planner` | `sonnet` | read-only |
| Task ownership | `ticket-owner` | `sonnet` | one per task |
| Tests | `test-designer` | `sonnet` | red commit |
| Code | `code-writer` | `sonnet` | green commit |
| Knowledge scan | `knowledge-scanner` | `sonnet` | read-only |
| Memory curation | `memory-curator` | `sonnet` | end of epic |

### Tiers

| Tier | Flow | Test-designer | Code-writer | Retry |
|---|---|---|---|---|
| `small` | one `code-writer` in solo mode | — | `sonnet` | `opus`, standard flow |
| `standard` | `test-designer` and `code-writer` | `sonnet` | `sonnet` | `opus` code-writer |
| `complex` | as standard, wider reading brief | `opus` | `opus` | `opus` code-writer |
""",
    "Tracker updates during a run": """| When | Task | Comment |
|---|---|---|
| Wave starts | → doing | run id and epic branch |
""",
    "Plugins": """| Plugin | Extends | Adds |
|---|---|---|
{plugins}
""",
    "Paths": """| What | Where | Committed |
|---|---|---|
| Working specs | `.work/specs/<yyyy-mm-dd>-<slug>.md` | no |
| Run logs for `/batch-implement` | `.work/runs/<run-id>/progress.md` | no |
| Development record | `docs/decisions/NNNN-<slug>.md` | yes |
""",
    "Project knowledge": """Mode: off
""",
    "Commands": """| Gate | Command |
|---|---|
| Setup in a fresh worktree | `pip install -e .` |
| Run named tests | `python -m pytest -q {{tests}}` (`{{tests}}` = space-separated node ids) |
| Full suite | `python -m pytest -q` |
| Typecheck | `true` (none configured) |
| Lint | `true` (none configured) |
| Dependency directory | {dep} |
| Lockfile | {lock} |
| Red means | exit code `1`: tests collected, ran, and failed |
| Test paths | `tests/` |
| Weakened tests | `bash .claude/workflow/bin/weakened-tests.sh <base> <head>` |
""",
    "Git moves": "| Capability | Command |\n|---|---|\n"
    + "".join(f"| `{cap}` | `{cmd}` |\n" for cap, cmd in MOVES.items()),
    "Serial resources": """None are configured.
""",
    "Surfaces": """| Surface | Entry point | Test drives it by | Person looks by | Automated check | Preview start | Ready when | Restart when changed | Cannot show |
|---|---|---|---|---|---|---|---|---|
| `web` | `{entry}` | a browser test | a browser | `true` | `{preview}` | `ready in` | `src/` | nothing |
""",
    "Review": """- **Cadence:** `none`.
""",
    "Execution": """- **Mode:** `owner`.
- **Parallelism:** at most `3` tasks at once.
""",
}


def payload_version() -> str:
    return (PAYLOAD / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()


def config_md(
    version: str | None = "current",
    omit: tuple[str, ...] = (),
    dep: str = "none",
    lock: str = "none",
    entry: str = "http://localhost:5173",
    preview: str = "npm run dev",
    plugins: str = "",
) -> str:
    out = ["# Workflow config", ""]
    if version is not None:
        out += [f"PAD version: {payload_version() if version == 'current' else version}", ""]
    for heading, body in SECTIONS.items():
        if heading in omit:
            continue
        if heading == "Commands":
            body = body.format(dep=dep, lock=lock)
        elif heading == "Surfaces":
            body = body.format(entry=entry, preview=preview)
        elif heading == "Plugins":
            body = body.format(plugins=plugins)
        out += [f"## {heading}", "", body]
    return "\n".join(out)


def agent_md(name: str, model: str) -> str:
    return f"---\nname: {name}\ndescription: fixture agent\nmodel: {model}\n---\n\nFixture body.\n"


def settings_json(allow: list[str], deny: list[str] | None = None) -> str:
    return json.dumps({"permissions": {"allow": allow, "deny": deny or []}}, indent=2)


def install(
    repo: Path,
    config: str | None = None,
    allow: list[str] | None = None,
    deny: list[str] | None = None,
    models: dict[str, str] | None = None,
    gitignore: list[str] | None = None,
    not_executable: tuple[str, ...] = (),
) -> Path:
    """Lay out a set-up repo in `repo`: config, settings, agents, scripts, .gitignore.

    Every script under .claude/workflow/bin is committed 100755, except `not_executable`, which
    are committed 100644 and made non-executable on disk.
    """
    workflow = repo / ".claude" / "workflow"
    bin_dir = workflow / "bin"
    agents = repo / ".claude" / "agents"
    bin_dir.mkdir(parents=True)
    agents.mkdir(parents=True)
    (workflow / "config.md").write_text(config if config is not None else config_md(),
                                        encoding="utf-8")
    (repo / ".claude" / "settings.json").write_text(
        settings_json(ALLOW if allow is None else allow, deny), encoding="utf-8")
    for name, model in {**AGENTS, **(models or {})}.items():
        (agents / f"{name}.md").write_text(agent_md(name, model), encoding="utf-8")
    (repo / ".gitignore").write_text(
        "\n".join(GITIGNORE if gitignore is None else gitignore) + "\n", encoding="utf-8")
    scripts = sorted(p.name for p in BIN.glob("*.sh"))
    for name in scripts:
        shutil.copyfile(BIN / name, bin_dir / name)
        os.chmod(bin_dir / name, 0o644 if name in not_executable else 0o755)
    git("add", "-A", cwd=repo)
    for name in scripts:
        flag = "-x" if name in not_executable else "+x"
        git("update-index", f"--chmod={flag}", f".claude/workflow/bin/{name}", cwd=repo)
    git("commit", "-q", "-m", "set up PAD", cwd=repo)
    return repo


@pytest.fixture
def preflight(run_script, tmp_path):
    """Factory: preflight(repo, *args) runs preflight.sh from the repo root, HOME isolated."""
    home = tmp_path / "home"
    home.mkdir()

    def run(repo: Path, *args: str):
        return run_script(SCRIPT, *args, cwd=repo, env={"HOME": home.as_posix()})

    return run


def lines(result) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.strip()]


def last(result) -> str:
    out = lines(result)
    return out[-1] if out else ""


def failures(result) -> list[tuple[str, str]]:
    out = []
    for line in lines(result):
        m = FAIL_LINE.match(line)
        if m:
            out.append((m.group("check"), m.group("detail")))
    return out


def assert_failed(result, check: str, *needles: str) -> None:
    """Exit 1; every failure is `check`; one names every needle; the count closes the output."""
    got = failures(result)
    assert result.returncode == 1, (result.returncode, result.stdout, result.stderr)
    assert got, result.stdout
    assert {c for c, _ in got} == {check}, got
    assert any(all(n in detail for n in needles) for _, detail in got), (needles, got)
    assert last(result) == f"PREFLIGHT FAILED {len(got)}", result.stdout


# --- O39: the whole setup ------------------------------------------------------------------


def test_o39_a_repo_whose_setup_holds_passes_with_preflight_ok_and_exit_0(repo, preflight):
    install(repo)
    result = preflight(repo)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert failures(result) == []
    assert last(result) == "PREFLIGHT OK"


def test_o39_a_git_move_the_settings_do_not_allow_fails_the_moves_check(repo, preflight):
    install(repo, allow=[r for r in ALLOW if r != "Bash(git push origin *)"])
    assert_failed(preflight(repo), "moves", "push-epic")


def test_o39_a_setup_command_the_settings_do_not_allow_fails_the_commands_check(repo, preflight):
    install(repo, allow=[r for r in ALLOW if r != SETUP_RULE])
    assert_failed(preflight(repo), "commands", "pip install -e .")


def test_o39_a_denied_gate_command_fails_the_commands_check_though_allowed(repo, preflight):
    install(repo, deny=["Bash(pip install:*)"])
    assert_failed(preflight(repo), "commands", "pip install -e .")


def test_o39_a_full_suite_command_the_settings_do_not_allow_fails_the_commands_check(
    repo, preflight
):
    install(repo, allow=[r for r in ALLOW if r != PYTEST_RULE])
    assert_failed(preflight(repo), "commands", "python -m pytest -q")


def test_o39_a_preview_start_the_settings_do_not_allow_fails_the_commands_check(repo, preflight):
    install(repo, allow=[r for r in ALLOW if r != PREVIEW_RULE])
    assert_failed(preflight(repo), "commands", "npm run dev")


def test_o39_a_workflow_script_the_settings_do_not_allow_fails_the_commands_check(
    repo, preflight
):
    install(repo, allow=[r for r in ALLOW if r != SCRIPTS_RULE])
    result = preflight(repo)
    assert_failed(result, "commands", ".claude/workflow/bin/merge-task.sh")
    assert not any("weakened-tests" in d for _, d in failures(result)), failures(result)


def test_o39_a_surface_entry_point_that_does_not_resolve_fails_the_knowledge_paths_check(
    repo, preflight
):
    install(repo, config=config_md(entry="src/app/main.py"))
    assert_failed(preflight(repo), "knowledge-paths", "src/app/main.py")


def test_o39_a_config_missing_a_section_of_its_version_fails_the_version_check_naming_it(
    repo, preflight
):
    install(repo, config=config_md(omit=("Review",)))
    assert_failed(preflight(repo), "version", "Review")


def test_o39_a_named_dependency_directory_that_is_missing_fails(repo, preflight):
    install(repo, config=config_md(dep="`node_modules`"))
    assert_failed(preflight(repo), "dependency-directory", "node_modules")


def test_o39_a_named_lockfile_that_is_missing_fails(repo, preflight):
    install(repo, config=config_md(lock="`package-lock.json`"))
    assert_failed(preflight(repo), "lockfile", "package-lock.json")


def test_o39_a_named_dependency_directory_and_lockfile_that_exist_pass(repo, preflight):
    install(repo, config=config_md(dep="`node_modules`", lock="`package-lock.json`"))
    (repo / "node_modules" / "left-pad").mkdir(parents=True)
    (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")
    result = preflight(repo)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert last(result) == "PREFLIGHT OK"


@pytest.mark.parametrize("agent,model", [("code-writer", "opus"), ("test-designer", "haiku")])
def test_o39_an_agent_model_that_differs_from_the_tiers_table_fails_the_models_check(
    repo, preflight, agent, model
):
    install(repo, models={agent: model})
    assert_failed(preflight(repo), "models", agent)


PLUGIN = ".claude/pad-plugins/attachments.md"


def _with_plugin(repo: Path, extends: str, write: bool = True) -> Path:
    install(repo, config=config_md(plugins=f"| `{PLUGIN}` | `{extends}` | attachments |"))
    if write:
        (repo / PLUGIN).parent.mkdir(parents=True)
        (repo / PLUGIN).write_text("# Plugin: attachments\n\nExtends: `tracker`\n",
                                   encoding="utf-8")
    return repo


def test_plugins_a_listed_plugin_that_exists_and_extends_an_agent_passes(repo, preflight):
    result = preflight(_with_plugin(repo, "tracker"))
    assert result.returncode == 0, result.stdout
    assert last(result) == "PREFLIGHT OK"


def test_plugins_a_listed_plugin_file_that_is_missing_fails_naming_it(repo, preflight):
    result = preflight(_with_plugin(repo, "tracker", write=False))
    assert_failed(result, "plugins", PLUGIN, "does not exist")


def test_plugins_a_plugin_extending_no_agent_or_skill_fails_naming_both(repo, preflight):
    result = preflight(_with_plugin(repo, "ledger-keeper"))
    assert_failed(result, "plugins", PLUGIN, "ledger-keeper")


def test_o39_a_script_not_executable_in_git_fails_the_executable_check(repo, preflight):
    install(repo, not_executable=("merge-task.sh",))
    assert_failed(preflight(repo), "executable", "merge-task.sh")


@pytest.mark.parametrize("missing,named", [(".work/", ".work"), (".claude/worktrees/", "worktrees")])
def test_o39_a_gitignore_not_covering_a_run_path_fails_the_gitignore_check(
    repo, preflight, missing, named
):
    install(repo, gitignore=[g for g in GITIGNORE if g != missing])
    assert_failed(preflight(repo), "gitignore", named)


def test_o39_every_failure_is_listed_and_counted_not_just_the_first(repo, preflight):
    install(repo, models={"code-writer": "opus"},
            gitignore=[g for g in GITIGNORE if g != ".work/"])
    result = preflight(repo)
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert sorted(c for c, _ in failures(result)) == ["gitignore", "models"], result.stdout
    assert last(result) == "PREFLIGHT FAILED 2"


def test_o39_config_option_checks_the_named_config_instead_of_the_default(repo, preflight):
    install(repo)
    alt = repo / "alt-config.md"
    alt.write_text(config_md(dep="`node_modules`"), encoding="utf-8")
    assert_failed(preflight(repo, "--config", alt.as_posix()), "dependency-directory",
                  "node_modules")


def test_o39_a_missing_config_fails_with_a_count_and_exit_1(repo, preflight):
    install(repo)
    result = preflight(repo, "--config", (repo / "no-such-config.md").as_posix())
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert failures(result), result.stdout
    assert re.fullmatch(r"PREFLIGHT FAILED [1-9][0-9]*", last(result)), result.stdout


# --- O39: /batch-implement runs it at the baseline ----------------------------------------


def baseline_step(skill: str) -> str:
    start = re.search(r"^## 2\. Start[ \t]*$", skill, re.M)
    assert start, "no '## 2. Start' section"
    end = re.search(r"^## ", skill[start.end():], re.M)
    body = skill[start.end(): start.end() + end.start()] if end else skill[start.end():]
    step = re.search(r"^5\. \*\*Baseline\.\*\*(.*?)(?=^\d+\. \*\*|\Z)", body, re.M | re.S)
    assert step, "no step 5 Baseline in '## 2. Start'"
    return step.group(1)


def test_o39_batch_implement_baseline_runs_preflight_before_the_preview_start(payload_text):
    step = baseline_step(payload_text(SKILL))
    run = step.find("bash .claude/workflow/bin/preflight.sh")
    preview = step.find("preview.sh start --surface")
    assert run != -1, step
    assert preview != -1, step
    assert run < preview, step
    finish = payload_text(SKILL).split("## 4. Finish the epic", 1)[-1]
    assert "preview.sh stop --surface <name> --worktree <epic worktree>" in finish


def test_o39_batch_implement_stops_before_any_wave_when_preflight_fails(payload_text):
    skill = payload_text(SKILL)
    step = baseline_step(skill)
    assert "PREFLIGHT FAILED" in step, step
    assert skill.find("preflight.sh") < skill.find("## 3. Run waves"), "preflight after waves"


# --- O40: an older PAD version -------------------------------------------------------------


def test_o40_an_older_pad_version_fails_naming_setup_workflow_upgrade_and_the_sections_to_add(
    repo, preflight
):
    install(repo, config=config_md(version=OLD_VERSION, omit=("Surfaces", "Review")))
    result = preflight(repo)
    assert_failed(result, "version", "/setup-workflow upgrade")
    named = " ".join(d for _, d in failures(result))
    assert "Surfaces" in named, named
    assert "Review" in named, named
    assert "Serial resources" not in named, named


def test_o40_a_config_with_no_pad_version_fails_naming_setup_workflow_upgrade(repo, preflight):
    install(repo, config=config_md(version=None))
    assert_failed(preflight(repo), "version", "/setup-workflow upgrade")


def test_o40_the_current_pad_version_passes_the_version_check(repo, preflight):
    install(repo, config=config_md(version="current"))
    result = preflight(repo)
    assert not any(c == "version" for c, _ in failures(result)), result.stdout
    assert last(result) == "PREFLIGHT OK", result.stdout


def test_o40_config_example_records_the_pad_version_for_the_installer(payload_text):
    text = payload_text(CONFIG_EXAMPLE)
    assert re.search(r"^PAD version: <PAD_VERSION>$", text, re.M), "no PAD version line"
