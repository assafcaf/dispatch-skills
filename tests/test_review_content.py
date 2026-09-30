"""E1-T22: batch-implement has a Review checkpoints section (O34)."""
from __future__ import annotations

import re

SKILL = "claude/skills/batch-implement/SKILL.md"


def checkpoints(payload_text) -> str:
    text = payload_text(SKILL)
    m = re.search(r"^(#{2,4}) Review checkpoints[ \t]*$", text, re.M)
    assert m, "no 'Review checkpoints' section"
    rest = text[m.end():]
    end = re.search(r"^#{1,%d} \S" % len(m.group(1)), rest, re.M)
    return rest[: end.start()] if end else rest


def test_o34_section_uses_the_configured_review_cadence(payload_text):
    body = checkpoints(payload_text)
    assert "Cadence" in body
    for option in ("after-first-wave", "per-wave", "end-only", "none"):
        assert option in body


def test_o34_packet_is_written_to_review_n_file_in_the_run_dir(payload_text):
    assert ".work/runs/<id>/review-<n>.md" in checkpoints(payload_text)


def test_o34_packet_lists_every_required_part(payload_text):
    body = checkpoints(payload_text).lower()
    for part in ("merged since the last", "surfaces", "how to look", "unverified", "operator-run"):
        assert part in body, part


def test_o34_operator_is_notified_by_push_notification(payload_text):
    body = checkpoints(payload_text).lower()
    assert "notif" in body
    assert "review packet" in body


def test_o34_checkpoint_does_not_stop_the_run(payload_text):
    body = checkpoints(payload_text).lower()
    assert re.search(r"without stopping|does not stop|never stop|doesn't stop|not stop", body)


def test_o34_each_finding_becomes_a_fix_task_with_its_own_red_test(payload_text):
    body = checkpoints(payload_text)
    assert "fix-<slug>" in body
    assert re.search(r"finding", body, re.I)
    assert re.search(r"red test", body, re.I)
    assert re.search(r"same run", body, re.I)


def test_o34_final_review_at_end_of_epic_is_left_unchanged(payload_text):
    body = checkpoints(payload_text).lower()
    assert "final review" in body
