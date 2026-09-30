"""O27, O28: the code-writer starts only after red is proven; the designer proves its own red.

Content tests: the agents' prose is the product, so these read it. They assert only what O27 and
O28 need, not the git moves (rebase, cherry-pick) that E1-T3 rewrites in the same files.
"""
from __future__ import annotations

import re

DESIGNER = "claude/agents/test-designer.md"
WRITER = "claude/agents/code-writer.md"
OWNER = "claude/agents/ticket-owner.md"

OBJECTION = 'BLOCKED: test <id> contradicts ticket line "<quote>"'


def flat(text: str) -> str:
    """Lowercased, markdown emphasis dropped, whitespace collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def headings(text: str) -> list[str]:
    return [h.lower() for h in re.findall(r"^#+ +(.*)$", text, re.M)]


def procedure_steps(text: str) -> dict[int, str]:
    m = re.search(r"^## Procedure\s*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "no Procedure section"
    parts = re.split(r"^(\d+)\. ", m.group(1), flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


# --- O27: no early start ---

def test_o27_owner_no_longer_starts_the_code_writer_early(payload_text):
    text = payload_text(OWNER)
    assert "PREPARED" not in text
    assert "PEER <id>" not in text
    assert "started with the test-designer" not in text
    assert "early" not in flat(text)


def test_o27_code_writer_has_no_early_start_or_prepared_stop(payload_text):
    text = payload_text(WRITER)
    assert "PREPARED" not in text
    assert not any("early start" in h for h in headings(text))
    assert "early start" not in flat(text)


def test_o27_peer_channel_is_gone_from_all_three_agents(payload_text):
    for path in (OWNER, WRITER, DESIGNER):
        text = payload_text(path)
        assert not any("your peer" in h for h in headings(text)), path
        assert "PEER:" not in text, path
        assert "at most two exchanges" not in flat(text), path


# --- O27: dispatched only after red, with the sha ---

def test_o27_owner_dispatches_code_writer_only_after_red_is_proven(payload_text):
    text = flat(payload_text(OWNER))
    assert re.search(r"code-writer[^.]*only after red is proven", text) or re.search(
        r"only after red is proven[^.]*code-writer", text
    )


def test_o27_owner_dispatch_carries_the_red_sha(payload_text):
    assert "RED: <" in payload_text(OWNER).replace("`", "").split("Procedure")[1].split(
        "READY"
    )[0]


def test_o27_owner_proves_red_before_the_code_writer_is_dispatched(payload_text):
    steps = procedure_steps(payload_text(OWNER))
    proof = min(n for n, s in steps.items() if "verify-red.sh" in s)
    dispatch = [
        n for n, s in steps.items() if "dispatch" in flat(s) and "code-writer" in flat(s)
        and "RED:" in s.replace("`", "")
    ]
    assert dispatch, "no step dispatches the code-writer with RED:"
    assert min(dispatch) >= proof
    early = [
        n for n, s in steps.items()
        if n < proof and "dispatch" in flat(s) and "code-writer" in flat(s)
    ]
    assert not early, f"code-writer dispatched before red proof in step(s) {early}"


def test_o27_code_writer_takes_the_red_sha_from_its_dispatch(payload_text):
    steps = procedure_steps(payload_text(WRITER))
    take = flat(steps[1] + steps[2])
    assert "red:" in take or "red <sha>" in take
    assert "early start" not in take


# --- O27: objection routing ---

def test_o27_code_writer_reports_objection_in_the_agreed_form(payload_text):
    assert OBJECTION in payload_text(WRITER).replace("`", "")


def test_o27_owner_routes_the_objection_to_the_test_designer(payload_text):
    text = payload_text(OWNER).replace("`", "")
    assert OBJECTION in text
    paras = [p for p in re.split(r"\n\s*\n", text) if OBJECTION in p]
    assert any("test-designer" in p or "-tests" in p for p in paras)


def test_o27_designer_does_not_take_objections_directly_from_the_code_writer(payload_text):
    text = flat(payload_text(DESIGNER))
    assert "an objection" not in text
    assert "your owner starts a code-writer" not in text


# --- O28: designer proves its own red ---

def test_o28_designer_last_step_runs_verify_red_on_its_red_commit(payload_text):
    steps = procedure_steps(payload_text(DESIGNER))
    last = steps[max(steps)]
    assert "verify-red.sh" in last
    assert "red commit" in flat(last)


def test_o28_designer_reports_only_after_red_ok(payload_text):
    steps = procedure_steps(payload_text(DESIGNER))
    last = flat(steps[max(steps)])
    assert "red ok" in last
    assert "only after" in last or "until" in last


def test_o28_verify_red_comes_after_the_commit_step(payload_text):
    steps = procedure_steps(payload_text(DESIGNER))
    commit = [n for n, s in steps.items() if "commit once" in flat(s)]
    assert commit and max(commit) < max(steps)
