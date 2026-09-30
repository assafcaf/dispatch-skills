"""E1-T11 (O13, O19): owner mode merges through merge-task.sh run by the orchestrator.

No revert of a revert, no merger agent to stall a merge, and neither a merge failure nor a
tracker FAIL stops the run. Content tests: the skill and agent prose is the product.
"""
from __future__ import annotations

import re

from conftest import PAYLOAD

SKILL = "claude/skills/batch-implement/SKILL.md"
OWNER = "claude/agents/ticket-owner.md"
MERGER = "claude/agents/epic-merger.md"


def blocks(text: str) -> list[str]:
    """Prose paragraphs and list items, with each table row as its own block."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if not para.strip():
            continue
        lines = para.strip().splitlines()
        if all(l.lstrip().startswith("|") for l in lines):
            out.extend(lines)
        else:
            out.extend(i for i in re.split(r"\n(?=\s*(?:[-*]|\d+\.)\s)", para) if i.strip())
    return out


def sentences(text: str) -> list[str]:
    return [s for b in blocks(text) for s in re.split(r"(?<=[.!?:])\s+(?=[A-Z`*])", b) if s.strip()]


def blocks_matching(text: str, *patterns: str) -> list[str]:
    return [b for b in blocks(text) if all(re.search(p, b, re.I) for p in patterns)]


def submitted_row(text: str) -> str:
    rows = [l for l in text.splitlines() if re.match(r"\|\s*Owner `SUBMITTED`", l)]
    assert len(rows) == 1, "reports table has no single `Owner SUBMITTED` row"
    return rows[0]


def operator_list(text: str) -> str:
    """From 'need the operator' to the end of its paragraph: the list of what needs a person."""
    m = re.search(r"need the operator.*?(?=\n\s*\n)", text, re.S)
    assert m, "skill no longer lists what needs the operator"
    return m.group(0)


# O13: no revert of a revert; false positives are resubmitted; reverts only for resources.

def test_o13_no_payload_file_mentions_remerge():
    offenders = [
        p.relative_to(PAYLOAD).as_posix()
        for p in PAYLOAD.rglob("*")
        if p.is_file() and "REMERGE" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []


def test_o13_no_revert_of_a_revert_in_skill_owner_or_merger(payload_text):
    for rel in (SKILL, OWNER, MERGER):
        text = payload_text(rel)
        assert not re.search(r"revert sha|<revert", text, re.I), rel
        assert not re.search(r"false[- ]positive revert", text, re.I), rel


def test_o13_false_positive_rejection_is_resubmitted_with_the_same_task_head(payload_text):
    hits = [
        b
        for rel in (SKILL, OWNER)
        for b in blocks_matching(payload_text(rel), r"false[- ]positive", r"REJECTED")
    ]
    assert hits, "neither skill nor owner handles a false-positive REJECTED"
    assert any(
        re.search(r"\bsame\b", b, re.I)
        and re.search(r"TASK_HEAD|task head", b, re.I)
        and re.search(r"resubmit|re-?run|again", b, re.I)
        for b in hits
    ), hits


def test_o13_false_positive_rejection_does_not_use_the_retry(payload_text):
    hits = [
        b
        for rel in (SKILL, OWNER)
        for b in blocks_matching(payload_text(rel), r"false[- ]positive", r"REJECTED")
    ]
    assert any(
        re.search(
            r"(doesn't|does not|never|without) us(e|es|ing) (up )?(the|its|the task's) retry"
            r"|not (the|a) retry|is free",
            b,
            re.I,
        )
        for b in hits
    ), hits


def test_o13_no_merger_reverted_reply_remains(payload_text):
    for rel in (SKILL, OWNER):
        assert "`REVERTED" not in payload_text(rel), rel


def test_o13_every_revert_in_skill_and_owner_is_for_a_serial_resource(payload_text):
    for rel in (SKILL, OWNER):
        stray = [
            b for b in blocks_matching(payload_text(rel), r"revert")
            if not re.search(r"resource", b, re.I)
        ]
        assert stray == [], f"{rel}: revert outside a serial-resource failure: {stray}"


def test_o13_resource_failure_reverts_with_the_revert_merge_capability(payload_text):
    hits = blocks_matching(payload_text(SKILL), r"MERGED_PENDING_RESOURCE")
    rows = [b for b in hits if b.lstrip().startswith("|")]
    assert rows, "reports table has no MERGED_PENDING_RESOURCE row"
    row = rows[0]
    assert "revert-merge" in row
    assert not re.search(r"message the merger", row, re.I)
    assert "`REVERT " not in payload_text(SKILL)


def test_o13_epic_merger_is_a_stub_pointing_at_merge_task(payload_text):
    text = payload_text(MERGER)
    assert "merge-task.sh" in text
    assert "git revert" not in text
    assert "git merge --no-ff" not in text
    assert not re.search(r"^## A `", text, re.M), "merger still handles messages"


# O19: the orchestrator runs merge-task.sh; a failure retries fresh; tracker FAIL never stops.

def test_o19_orchestrator_runs_merge_task_in_background_for_each_submitted(payload_text):
    row = submitted_row(payload_text(SKILL))
    assert "merge-task.sh" in row
    assert re.search(r"background", row, re.I)


def test_o19_orchestrator_messages_the_owner_merge_task_last_line(payload_text):
    row = submitted_row(payload_text(SKILL))
    assert re.search(r"last line", row, re.I)
    assert re.search(r"owner", row, re.I)


def test_o19_submitted_row_reintroduces_no_sha_check(payload_text):
    row = submitted_row(payload_text(SKILL))
    assert not re.search(r"\bshas?\b", row, re.I), row


def test_o19_merge_error_is_retried_once_from_a_fresh_start(payload_text):
    hits = blocks_matching(payload_text(SKILL), r"`ERROR|exit 2")
    assert hits, "skill never handles merge-task.sh's ERROR / exit 2"
    assert any(
        re.search(r"\bonce\b", b, re.I) and re.search(r"fresh", b, re.I) for b in hits
    ), hits


def test_o19_second_merge_error_is_parked_as_a_question(payload_text):
    hits = blocks_matching(payload_text(SKILL), r"`ERROR|exit 2")
    assert any(re.search(r"question|park", b, re.I) for b in hits), hits


def test_o19_merge_failure_does_not_need_the_operator(payload_text):
    block = operator_list(payload_text(SKILL))
    assert not re.search(r"merger|merge-task|`ERROR", block, re.I), block


def test_o19_no_merger_hold_and_continue_protocol(payload_text):
    text = payload_text(SKILL)
    assert "`CONTINUE`" not in text
    assert not re.search(r"\bholding\b", text, re.I)


def test_o19_skill_dispatches_no_epic_merger(payload_text):
    text = payload_text(SKILL)
    assert not re.search(r"[Dd]ispatch `epic-merger`", text)
    assert not re.search(r"^\|\s*`epic-merger`", text, re.M)
    assert not re.search(r"\bthe merger\b", text, re.I)


def test_o19_owner_hands_over_to_the_orchestrator_not_a_merger(payload_text):
    text = payload_text(OWNER)
    assert not re.search(r"\bmerger\b", text, re.I)


def test_o19_tracker_fail_does_not_need_the_operator(payload_text):
    block = operator_list(payload_text(SKILL))
    assert not re.search(r"tracker", block, re.I), block


def test_o19_tracker_fail_is_never_a_question(payload_text):
    hits = [x for x in sentences(payload_text(SKILL)) if re.search(r"tracker", x) and "FAIL" in x]
    asking = [b for b in hits if re.search(r"question", b, re.I)]
    assert asking == [], asking


def test_o19_tracker_fail_lets_the_run_carry_on(payload_text):
    hits = [x for x in sentences(payload_text(SKILL)) if re.search(r"tracker", x) and "FAIL" in x]
    assert any(
        re.search(r"never stops?|keeps? going|carr(y|ies) on|continues?", b, re.I) for b in hits
    ), hits
