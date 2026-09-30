"""O31: tiers are assigned by observable signals; non-TDD work stops being a task.

Content tests: the skill, template and planner prose are the product.
"""
from __future__ import annotations

import re

SKILL = "claude/skills/tickets/SKILL.md"
TEMPLATE = "claude/workflow/ticket-template.md"
PLANNER = "claude/agents/task-planner.md"


def bullet(text: str, lead: str) -> str:
    m = re.search(rf"^- \*\*{re.escape(lead)}.*?(?=^- \*\*|^## |\Z)", text, re.S | re.M)
    assert m, f"no bullet starting {lead!r}"
    return m.group(0)


def paragraphs_with(text: str, *needles: str) -> list[str]:
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [p for p in paras if all(n.lower() in p.lower() for n in needles)]


def test_o31_assign_a_tier_names_the_four_signals(payload_text):
    b = bullet(payload_text(SKILL), "Assign a tier").lower()
    assert "signal" in b
    assert "files touched" in b
    assert "interfaces changed" in b
    assert "outcome count" in b
    assert "standing overlap" in b


def test_o31_tier_section_line_form_is_tier_signal_why(payload_text):
    text = payload_text(SKILL)
    assert "<tier> — <signal>: <why>" in text
    assert "<tier> — <signal>: <why>" in payload_text(TEMPLATE)


def test_o31_template_tiers_table_is_keyed_by_signals(payload_text):
    text = payload_text(TEMPLATE)
    tiers = text[text.index("## Tiers"):].lower()
    assert "files touched" in tiers
    assert "interfaces changed" in tiers
    assert "outcome count" in tiers
    assert "standing overlap" in tiers


def test_o31_docs_only_work_goes_to_the_epic_finish_step(payload_text):
    paras = paragraphs_with(payload_text(SKILL), "docs-only", "finish step")
    assert paras, "SKILL must say docs-only work goes to the epic's finish step"
    assert any("not a task" in p.lower() or "no task" in p.lower() or "instead of a task" in p.lower()
               or "isn't a task" in p.lower() or "not its own task" in p.lower() for p in paras)


def test_o31_device_only_checks_attach_to_feature_task_as_resource_probes(payload_text):
    paras = paragraphs_with(payload_text(SKILL), "device-only", "probe")
    assert paras, "SKILL must attach device-only checks as resource probes"
    assert any("feature task" in p.lower() for p in paras)


def test_o31_tiny_task_folds_only_on_same_files_and_no_blocking(payload_text):
    paras = paragraphs_with(payload_text(SKILL), "fold", "same files")
    assert paras, "SKILL must state when a tiny task is folded into a sibling"
    p = " ".join(paras).lower()
    assert "only" in p
    assert re.search(r"neither\b.*\bblock", p, re.S)


def test_o31_planner_tiers_check_asks_for_the_signal(payload_text):
    text = payload_text(PLANNER)
    step = re.search(r"^6\. \*\*Tier\..*?(?=^\d+\. \*\*|^## )", text, re.S | re.M)
    assert step, "no Tier step"
    s = step.group(0).lower()
    assert "signal" in s
    assert "files touched" in s
    tiers = text[text.index("TIERS:"):].split("\n\n")[0].lower()
    assert "signal" in tiers
