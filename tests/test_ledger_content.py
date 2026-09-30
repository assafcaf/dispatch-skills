"""O5: the orchestrator is the only ledger writer; owners never dispatch a tracker.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

import re

SKILL = "claude/skills/batch-implement/SKILL.md"
OWNER = "claude/agents/ticket-owner.md"
TRACKER = "claude/agents/tracker.md"
TEMPLATE = "claude/skills/setup-workflow/tracker-agent-template.md"


def _frontmatter(text: str) -> dict[str, str]:
    block = text.split("---")[1]
    return dict(re.findall(r"^(\w+):\s*(.*)$", block, re.M))


def test_o5_batch_implement_never_calls_enter_worktree(payload_text):
    text = payload_text(SKILL)
    offending = [
        line for line in text.splitlines()
        if "EnterWorktree" in line and not re.search(r"\b(never|not|no|don't)\b", line, re.I)
    ]
    assert offending == []


def test_o5_orchestrator_reaches_epic_worktree_with_git_dash_c(payload_text):
    assert "git -C" in payload_text(SKILL)


def test_o5_orchestrator_writes_ledger_through_ledger_sh(payload_text):
    assert "ledger.sh" in payload_text(SKILL)


def test_o5_orchestrator_records_done_failed_blocked_from_owner_report(payload_text):
    text = payload_text(SKILL)
    assert "LEDGER_COMMENT" in text
    assert "TRACKER_PENDING" not in text


def test_o5_ticket_owner_dispatches_no_tracker(payload_text):
    text = payload_text(OWNER)
    assert not re.search(r"[Dd]ispatch `tracker`", text)
    assert "TRACKER_PENDING" not in text


def test_o5_ticket_owner_reports_ledger_comment_line(payload_text):
    assert re.search(r"^LEDGER_COMMENT:", payload_text(OWNER), re.M)


def test_o5_red_proven_ledger_comment_is_gone(payload_text):
    assert "red proven" not in payload_text(OWNER)
    assert "red proven" not in payload_text(SKILL)


def test_o5_only_orchestrator_may_dispatch_tracker(payload_text):
    assert "Anyone who needs one" not in payload_text(SKILL)
    assert "ticket owners" not in payload_text(TRACKER)
    assert "ticket owners" not in payload_text(TEMPLATE)


def test_o5_tracker_agent_pins_haiku(payload_text):
    assert _frontmatter(payload_text(TRACKER))["model"] == "haiku"
    assert "model: haiku" in payload_text(TEMPLATE)
