"""O35: the epic gate runs each Surfaces row's automated check; a red check fails the gate.

    surface-checks.sh [--config <path>]

Reads the `## Surfaces` table (default `.claude/workflow/config.md`), runs each non-empty
`Automated check` cell as a shell command in the current directory. Last line `SURFACES OK`, or
`SURFACES FAIL <surface>` for each failure. Exit 0 or 1.
"""
from __future__ import annotations

from pathlib import Path

HEADER = (
    "| Surface | Entry point | Test drives it by | Person looks by | Automated check "
    "| Preview start | Ready when | Restart when changed | Cannot show |"
)
SEP = "|---|---|---|---|---|---|---|---|---|"


def _row(name: str, check: str) -> str:
    cells = [f"`{name}`", "`http://localhost:1`", "`curl`", "`browser`",
             f"`{check}`" if check else "", "", "", "", "`nothing`"]
    return "| " + " | ".join(cells) + " |"


def _config(tmp: Path, rows: list[str]) -> Path:
    table = "\n".join([HEADER, SEP, *rows])
    p = tmp / "cfg.md"
    p.write_text(f"# Config\n\n## Surfaces\n\nThe places.\n\n{table}\n\n## Review\n\n- x\n",
                 encoding="utf-8")
    return p


def _last(out: str) -> str:
    return out.strip().splitlines()[-1]


def test_o35_all_checks_green_reports_surfaces_ok(run_script, tmp_path):
    cfg = _config(tmp_path, [_row("web", "true"), _row("api", "true")])
    r = run_script("surface-checks.sh", "--config", str(cfg), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert _last(r.stdout) == "SURFACES OK"


def test_o35_a_check_is_actually_run_in_the_current_directory(run_script, tmp_path):
    cfg = _config(tmp_path, [_row("web", "touch ran.marker")])
    r = run_script("surface-checks.sh", "--config", str(cfg), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "ran.marker").exists()


def test_o35_red_check_fails_the_gate_naming_the_surface(run_script, tmp_path):
    cfg = _config(tmp_path, [_row("web", "true"), _row("api", "exit 3")])
    r = run_script("surface-checks.sh", "--config", str(cfg), cwd=tmp_path)
    assert r.returncode == 1
    assert _last(r.stdout) == "SURFACES FAIL api"
    assert "SURFACES OK" not in r.stdout


def test_o35_every_failing_surface_is_named_and_later_checks_still_run(run_script, tmp_path):
    cfg = _config(tmp_path, [_row("web", "exit 1"), _row("api", "exit 2"),
                             _row("docs", "touch docs.marker")])
    r = run_script("surface-checks.sh", "--config", str(cfg), cwd=tmp_path)
    assert r.returncode == 1
    lines = r.stdout.splitlines()
    assert "SURFACES FAIL web" in lines
    assert "SURFACES FAIL api" in lines
    assert "SURFACES FAIL docs" not in lines
    assert (tmp_path / "docs.marker").exists()


def test_o35_rows_without_an_automated_check_are_skipped(run_script, tmp_path):
    cfg = _config(tmp_path, [_row("manual", ""), _row("web", "touch web.marker")])
    r = run_script("surface-checks.sh", "--config", str(cfg), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert _last(r.stdout) == "SURFACES OK"
    assert (tmp_path / "web.marker").exists()


def test_o35_no_surfaces_configured_is_ok(run_script, tmp_path):
    p = tmp_path / "cfg.md"
    p.write_text("# Config\n\n## Review\n\n- x\n", encoding="utf-8")
    r = run_script("surface-checks.sh", "--config", str(p), cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert _last(r.stdout) == "SURFACES OK"


def test_o35_default_config_is_the_installed_workflow_config(run_script, tmp_path):
    (tmp_path / ".claude" / "workflow").mkdir(parents=True)
    (tmp_path / ".claude" / "workflow" / "config.md").write_text(
        "## Surfaces\n\n" + "\n".join([HEADER, SEP, _row("web", "exit 1")]) + "\n",
        encoding="utf-8")
    r = run_script("surface-checks.sh", cwd=tmp_path)
    assert r.returncode == 1
    assert _last(r.stdout) == "SURFACES FAIL web"


def test_o35_epic_gate_step_in_batch_implement_runs_surface_checks(payload_text):
    text = payload_text("claude/skills/batch-implement/SKILL.md")
    start = text.index("## 4. Finish the epic")
    step1 = text[start:text.index("2. **Final review.**", start)]
    assert "surface-checks.sh" in step1
