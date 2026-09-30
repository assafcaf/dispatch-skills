"""O20, O23: /batch-implement --mode, and the gate-runner agent.

Content tests: the skill's prose, the config example and the agent file are the product.
"""
from __future__ import annotations

import re

from conftest import PAYLOAD

GATE_RUNNER = "claude/agents/gate-runner.md"
SKILL = "claude/skills/batch-implement/SKILL.md"
CONFIG = "claude/workflow/config.example.md"


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def gate_runner(payload_text) -> str:
    assert (PAYLOAD / GATE_RUNNER).is_file(), "payload/claude/agents/gate-runner.md is missing"
    return payload_text(GATE_RUNNER)


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def test_o20_argument_hint_offers_mode_owner_workflow_spine(payload_text):
    hint = frontmatter(payload_text(SKILL))["argument-hint"]
    assert "--mode" in hint
    for mode in ("owner", "workflow", "spine"):
        assert mode in hint


def test_o20_mode_defaults_to_config_execution_mode(payload_text):
    paras = [p.lower() for p in paragraphs(payload_text(SKILL)) if "--mode" in p]
    assert any("default" in p and "config.md" in p and "execution" in p for p in paras)


def test_o20_spine_reports_it_is_not_available_yet(payload_text):
    paras = [p.lower() for p in paragraphs(payload_text(SKILL)) if "spine" in p.lower()]
    assert any("not available yet" in p for p in paras)


def test_o20_workflow_falls_back_to_owner_with_a_logged_ruling(payload_text):
    paras = [
        p
        for p in paragraphs(payload_text(SKILL))
        if "workflow" in p.lower() and "fall" in p.lower()
    ]
    assert any(
        "owner" in p and "Ruling:" in p and "Workflow tool" in p and "unavailable" in p.lower()
        for p in paras
    )


def test_o20_config_example_has_execution_mode_owner(payload_text):
    text = payload_text(CONFIG)
    execution = re.search(r"^## Execution\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert execution, "no Execution section"
    assert "Mode:" in execution.group(1)
    assert re.search(r"Mode:\**\s*`?owner", execution.group(1))
    assert "workflow" in execution.group(1).lower()


def test_o23_gate_runner_is_haiku_low_effort_bash_only(payload_text):
    fm = frontmatter(gate_runner(payload_text))
    assert fm["name"] == "gate-runner"
    assert fm["model"] == "haiku"
    assert fm["effort"] == "low"
    assert fm["tools"] == "Bash"


def test_o23_gate_runner_input_and_output_contract(payload_text):
    text = gate_runner(payload_text)
    assert "RUN: <script> <args>" in text
    assert "EXIT <code>" in text
    assert "last line" in text.lower()


def test_o23_gate_runner_is_the_only_way_pad_task_runs_a_script(payload_text):
    text = gate_runner(payload_text).lower()
    assert "pad-task" in text
    assert "only" in text
