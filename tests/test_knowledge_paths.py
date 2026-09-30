"""E1-T24 O38: knowledge-paths.sh fails on a Surfaces entry point or a Git moves script that
does not resolve. Fixtures build a config.md in a throwaway repo; the script is run for real."""
from __future__ import annotations

from pathlib import Path

SCRIPT = "knowledge-paths.sh"

SURFACE_HEADER = (
    "| Surface | Entry point | Test drives it by | Person looks by | Automated check | "
    "Preview start | Ready when | Restart when changed | Cannot show |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)
MOVES_HEADER = "| Capability | Command |\n|---|---|\n"


def surface_row(name: str, entry: str) -> str:
    return f"| `{name}` | {entry} | a | b | c | d | e | f | g |\n"


def write_config(root: Path, surfaces: list[tuple[str, str]] = (), moves: list[tuple[str, str]] = (),
                 mode: str = "off") -> None:
    text = f"## Project knowledge\n\nMode: {mode}\n\n## Surfaces\n\n" + SURFACE_HEADER
    text += "".join(surface_row(n, e) for n, e in surfaces)
    text += "\n## Git moves\n\n" + MOVES_HEADER
    text += "".join(f"| `{c}` | `{cmd}` |\n" for c, cmd in moves)
    text += "\n## Serial resources\n\nNone.\n"
    cfg = root / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(text, encoding="utf-8")


def touch(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n", encoding="utf-8")


def run(run_script, root: Path):
    return run_script(SCRIPT, "--root", root.as_posix(), cwd=root)


def test_o38_surface_entry_point_that_does_not_resolve_fails(repo, run_script):
    write_config(repo, surfaces=[("web", "`web/index.html`")])
    r = run(run_script, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "web/index.html" in r.stdout


def test_o38_surface_entry_point_that_resolves_passes(repo, run_script):
    touch(repo, "web/index.html")
    write_config(repo, surfaces=[("web", "`web/index.html`")])
    r = run(run_script, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o38_surface_command_entry_point_naming_a_missing_script_fails(repo, run_script):
    write_config(repo, surfaces=[("cli", "`bash bin/tool.sh --help`")])
    r = run(run_script, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "bin/tool.sh" in r.stdout


def test_o38_surface_command_entry_point_naming_an_existing_script_passes(repo, run_script):
    touch(repo, "bin/tool.sh")
    write_config(repo, surfaces=[("cli", "`bash bin/tool.sh --help`")])
    r = run(run_script, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o38_surface_url_entry_point_is_not_a_path(repo, run_script):
    write_config(repo, surfaces=[("web", "`http://localhost:3000/app`")])
    r = run(run_script, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o38_surface_placeholder_row_of_the_example_config_is_not_a_path(repo, run_script):
    write_config(repo, surfaces=[("<name>", "`<url, command or file>`")])
    r = run(run_script, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o38_only_the_unresolved_surface_is_named(repo, run_script):
    touch(repo, "web/index.html")
    write_config(repo, surfaces=[("web", "`web/index.html`"), ("api", "`api/server.py`")])
    r = run(run_script, repo)
    assert r.returncode == 1
    assert "api/server.py" in r.stdout
    assert "web/index.html" not in r.stdout


def test_o38_git_moves_script_that_does_not_resolve_fails(repo, run_script):
    write_config(repo, moves=[("take-red", "bash .claude/workflow/bin/take-red.sh <sha>")])
    r = run(run_script, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert ".claude/workflow/bin/take-red.sh" in r.stdout


def test_o38_git_moves_script_that_resolves_passes(repo, run_script):
    touch(repo, ".claude/workflow/bin/take-red.sh")
    write_config(repo, moves=[("take-red", "bash .claude/workflow/bin/take-red.sh <sha>")])
    r = run(run_script, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o38_plain_git_commands_in_git_moves_are_not_paths(repo, run_script):
    write_config(repo, moves=[
        ("move-onto-sha", "git reset --hard <sha>"),
        ("discard-changes", "git checkout -- <path>"),
        ("push-epic", "git push origin <branch>"),
    ])
    r = run(run_script, repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o38_unresolved_surface_fails_even_when_knowledge_mode_is_off(repo, run_script):
    write_config(repo, surfaces=[("web", "`web/index.html`")], mode="off")
    r = run(run_script, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "web/index.html" in r.stdout


def test_o38_unresolved_surface_fails_when_knowledge_mode_is_on(repo, run_script):
    touch(repo, "CONTEXT.md")
    touch(repo, ".claude/workflow/project.md")
    write_config(repo, surfaces=[("web", "`web/index.html`")], mode="on")
    r = run(run_script, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "web/index.html" in r.stdout
