"""Baseline smoke test: the payload ships every skill and agent the installer copies.

E1-T1 builds the real harness (throwaway git repos driving payload scripts); this file only
keeps the suite non-empty and green so a run has a baseline to compare against.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "payload" / "claude"

SKILLS = ["batch-implement", "knowledge-layer", "setup-workflow", "spec", "tickets"]
AGENTS = [
    "code-writer",
    "epic-merger",
    "knowledge-scanner",
    "memory-curator",
    "task-planner",
    "test-designer",
    "ticket-owner",
    "tracker",
]


def test_every_skill_has_a_skill_file():
    missing = [s for s in SKILLS if not (PAYLOAD / "skills" / s / "SKILL.md").is_file()]
    assert missing == []


def test_every_agent_has_an_agent_file():
    missing = [a for a in AGENTS if not (PAYLOAD / "agents" / f"{a}.md").is_file()]
    assert missing == []


def test_gate_scripts_are_present():
    for script in ["verify-red.sh", "weakened-tests.sh", "knowledge-paths.sh"]:
        assert (PAYLOAD / "workflow" / "bin" / script).is_file(), script
