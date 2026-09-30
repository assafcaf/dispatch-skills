"""O14 / O16: a question parks one task and the run keeps going; every halt is logged.

Content tests: the batch-implement skill's prose is the product, so these read it.
"""
from __future__ import annotations

import re

SKILL = "claude/skills/batch-implement/SKILL.md"
AGENT_MEMORY = "claude/workflow/agent-memory.md"


def paragraphs(text: str) -> list[str]:
    """Blocks of text separated by blank lines (a list or table stays with its block)."""
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def paragraphs_with(text: str, *needles: str) -> list[str]:
    return [p for p in paragraphs(text) if all(n.lower() in p.lower() for n in needles)]


def test_o14_question_is_logged_as_question_line_in_run_log(payload_text):
    hits = paragraphs_with(payload_text(SKILL), "QUESTION <KEY>:")
    assert hits, "skill never names the `QUESTION <KEY>: <question>` run-log line"
    assert any("run-log.sh" in p for p in hits)


def test_o14_question_sends_a_push_notification(payload_text):
    assert paragraphs_with(payload_text(SKILL), "QUESTION <KEY>:", "push notification")


def test_o14_question_parks_only_the_affected_task_and_its_dependents_wait(payload_text):
    hits = paragraphs_with(payload_text(SKILL), "QUESTION <KEY>:", "park")
    assert hits
    assert any("dependents" in p.lower() for p in hits)


def test_o14_other_tasks_keep_dispatching_and_merging_while_one_is_parked(payload_text):
    hits = paragraphs_with(payload_text(SKILL), "park", "merg")
    assert any(re.search(r"dispatch", p, re.I) for p in hits)


def test_o14_orchestrator_never_calls_ask_user_question(payload_text):
    lines = [l for l in payload_text(SKILL).splitlines() if "AskUserQuestion" in l]
    assert lines, "skill never rules out AskUserQuestion"
    offending = [l for l in lines if not re.search(r"\b(never|not|no|don't)\b", l, re.I)]
    assert offending == []


def test_o14_run_pauses_only_when_nothing_is_runnable_and_notifies_again(payload_text):
    hits = paragraphs_with(payload_text(SKILL), "pause", "runnable")
    assert hits, "skill never says the run pauses only when nothing is runnable"
    assert any("notif" in p.lower() for p in hits)


def test_o14_old_stop_and_ask_rule_is_gone(payload_text):
    assert not re.search(r"stop and ask", payload_text(SKILL), re.I)


def test_o16_skill_logs_every_halt_with_halt_log_sh(payload_text):
    hits = paragraphs_with(payload_text(SKILL), "halt-log.sh")
    assert hits, "skill never calls halt-log.sh"
    assert any("park" in p.lower() for p in hits)
    assert any("pause" in p.lower() for p in hits)


def test_o16_skill_logs_a_second_halt_line_when_the_halt_resolves(payload_text):
    hits = paragraphs_with(payload_text(SKILL), "halt-log.sh")
    assert any("pending" in p for p in hits)


def test_o16_agent_memory_documents_orchestrator_halts_file(payload_text):
    hits = paragraphs_with(payload_text(AGENT_MEMORY), "orchestrator/HALTS.md")
    assert hits, "agent-memory.md never documents orchestrator/HALTS.md"
    assert any("halt-log.sh" in p for p in hits)
    for cls in ("pad", "project", "machine", "harness"):
        assert any(cls in p for p in hits), cls
