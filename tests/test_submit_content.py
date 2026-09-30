"""E1-T16: the owner runs task-submit before submitting; the orchestrator no longer checks shas."""
from __future__ import annotations

import re

OWNER = "claude/agents/ticket-owner.md"
SKILL = "claude/skills/batch-implement/SKILL.md"


def step5(text: str) -> str:
    m = re.search(r"^5\. \*\*Check the report\.\*\*(.*?)(?=^6\. )", text, re.M | re.S)
    assert m, "no step 5 'Check the report'"
    return m.group(1)


def test_owner_step5_runs_task_submit_with_shas_and_test_paths(payload_text):
    body = step5(payload_text(OWNER))
    assert "task-submit.sh" in body
    assert "epic head" in body
    assert "--test-paths" in body


def test_owner_step5_acts_on_submit_fail_before_submitting(payload_text):
    body = step5(payload_text(OWNER))
    assert "SUBMIT FAIL" in body
    assert "before" in body and "submit" in body.lower()


def test_orchestrator_has_no_check_every_sha_paragraph(payload_text):
    text = payload_text(SKILL)
    assert "Check every sha" not in text
    assert "cat-file -t" not in text


def test_orchestrator_has_no_pre_relay_review(payload_text):
    assert not re.search(r"pre-relay", payload_text(SKILL), re.I)
