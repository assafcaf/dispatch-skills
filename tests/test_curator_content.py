"""E1-T13 O17: the curator routes halts and lessons into separate groups."""
from __future__ import annotations

import re

CURATOR = "claude/agents/memory-curator.md"
BATCH = "claude/skills/batch-implement/SKILL.md"


def report_block(text: str) -> str:
    return text.split("## Report", 1)[1]


def test_o17_curator_reads_halts_md(payload_text):
    assert "HALTS.md" in payload_text(CURATOR)


def test_o17_report_has_local_candidates_field(payload_text):
    assert re.search(r"^LOCAL_CANDIDATES:", report_block(payload_text(CURATOR)), re.M)


def test_o17_report_has_repeated_rulings_field(payload_text):
    assert re.search(r"^REPEATED_RULINGS:", report_block(payload_text(CURATOR)), re.M)


def test_o17_curator_routes_by_halt_class(payload_text):
    body = payload_text(CURATOR)
    for cls in ("pad", "project", "machine"):
        assert f"`{cls}`" in body, cls
    assert "CLAUDE.local.md" in body


def test_o17_repeated_rulings_become_a_question_for_tickets(payload_text):
    body = payload_text(CURATOR)
    assert re.search(r"same reason", body) and "/tickets" in body


def test_o17_pr_body_lists_groups_separately(payload_text):
    step = payload_text(BATCH).split("**Push and open a draft PR**", 1)[1].split("7. **Report", 1)[0]
    for field in ("PROJECT_MD_CANDIDATES", "UPSTREAM_FIXES", "LOCAL_CANDIDATES", "REPEATED_RULINGS"):
        assert field in step, field
