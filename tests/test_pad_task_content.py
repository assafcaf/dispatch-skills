"""E1-T18: the pad-task workflow, its "Workflow mode" section, and the owner's lost-agent rule.

Content tests: O18 is level content. O21 and O22 are level live (see the ticket's live probe);
what is host-testable of them is the workflow file's shape, the scripts it calls through the
gate-runner, the argument names it reads, the result lines it returns, and the skill's section.
"""
from __future__ import annotations

import re

from conftest import PAYLOAD

PAD_TASK = "claude/workflows/pad-task.js"
SKILL = "claude/skills/batch-implement/SKILL.md"
OWNER = "claude/agents/ticket-owner.md"


def pad_task(payload_text) -> str:
    assert (PAYLOAD / PAD_TASK).is_file(), "payload/claude/workflows/pad-task.js is missing"
    return payload_text(PAD_TASK)


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def workflow_mode_section(text: str) -> str:
    m = re.search(r"^(#{2,4}) [^\n]*Workflow mode[^\n]*\n(.*?)(?=^#{2,4} |\Z)", text, re.S | re.M)
    assert m, 'SKILL.md has no "Workflow mode" section'
    return m.group(2)


def lost_agent_paragraphs(text: str) -> list[str]:
    return [p for p in paragraphs(text) if "worktree" in p.lower() and "lost" in p.lower()]


def statement_with(text: str, needle: str) -> str:
    """The source from the first `needle` to the end of its call: up to 8 lines, or a `;`."""
    i = text.find(needle)
    assert i >= 0, f"{needle} is not called"
    window = "\n".join(text[i:].splitlines()[:8])
    return window


# O18: a lost agent is re-dispatched once, and that is not the retry.


def test_o18_owner_redispatches_an_agent_whose_worktree_is_lost_once_from_its_last_commit(
    payload_text,
):
    paras = [p.lower() for p in lost_agent_paragraphs(payload_text(OWNER))]
    assert paras, "ticket-owner.md has no rule for an agent whose worktree is lost"
    assert any("once" in p and "last commit" in p for p in paras)


def test_o18_owner_lost_agent_redispatch_does_not_use_the_retry(payload_text):
    paras = [p.lower() for p in lost_agent_paragraphs(payload_text(OWNER))]
    assert any(
        re.search(r"(doesn't|does not|never) use[s]? the retry|not the retry", p) for p in paras
    )


def test_o18_workflow_redispatches_an_agent_that_returns_null(payload_text):
    lines = pad_task(payload_text).splitlines()
    null_checks = [
        i for i, line in enumerate(lines) if re.search(r"===?\s*null|null\s*===?|\?\?", line)
    ]
    assert null_checks, "pad-task.js never checks an agent() result for null"
    assert any(
        "agent(" in "\n".join(lines[max(0, i - 10) : i + 11]) for i in null_checks
    ), "no agent() re-dispatch next to the null check"


# O21: pad-task's shape — stages, scripts through the gate-runner, arguments, result lines.


def test_o21_workflow_reads_every_documented_argument(payload_text):
    text = pad_task(payload_text)
    for name in (
        "key",
        "ticket",
        "run",
        "epicBranch",
        "epicWorktree",
        "epicHead",
        "tier",
        "commands",
        "testPaths",
        "models",
        "ruling",
    ):
        assert re.search(rf"\b{name}\b", text), f"pad-task.js never reads args.{name}"


def test_o21_workflow_reads_every_command_and_both_models(payload_text):
    text = pad_task(payload_text)
    for name in ("setup", "named", "full", "lint", "typecheck", "retry"):
        assert re.search(rf"\b{name}\b", text), f"pad-task.js never reads {name}"


def test_o21_workflow_dispatches_test_designer_and_code_writer(payload_text):
    text = pad_task(payload_text)
    assert "test-designer" in text
    assert "code-writer" in text


def test_o21_workflow_runs_stages_in_order_red_submit_merge_evidence(payload_text):
    text = pad_task(payload_text)
    order = ["verify-red.sh", "task-submit.sh", "merge-task.sh", "render-evidence.sh"]
    positions = []
    for script in order:
        assert script in text, f"pad-task.js never runs {script}"
        positions.append(text.index(script))
    assert positions == sorted(positions), f"stages out of order: {order} at {positions}"


def test_o21_workflow_runs_scripts_only_through_the_gate_runner(payload_text):
    text = pad_task(payload_text)
    assert "gate-runner" in text
    assert "RUN: " in text
    assert not re.search(r"child_process|execSync|spawnSync|\bspawn\(|\bexec\(", text)


def test_o21_workflow_proves_red_with_verify_red_deps(payload_text):
    call = statement_with(pad_task(payload_text), "verify-red.sh")
    assert "--deps" in call
    assert "--lockfile" in call


def test_o21_workflow_submits_with_epic_head_and_test_paths(payload_text):
    call = statement_with(pad_task(payload_text), "task-submit.sh")
    assert "--test-paths" in call


def test_o21_workflow_merges_with_worktree_branch_gate_lint_and_test_paths(payload_text):
    call = statement_with(pad_task(payload_text), "merge-task.sh")
    for flag in ("--worktree", "--branch", "--gate", "--lint", "--test-paths"):
        assert flag in call, f"merge-task.sh call lacks {flag}"


def test_o21_workflow_writes_ledger_run_log_and_evidence(payload_text):
    text = pad_task(payload_text)
    assert re.search(r"ledger\.sh[^\n]*status", text), "no ledger.sh <KEY> status call"
    assert "run-log.sh" in text
    call = statement_with(text, "render-evidence.sh")
    for flag in ("--run", "--key", "--red", "--merge", "--outcomes"):
        assert flag in call, f"render-evidence.sh call lacks {flag}"


def test_o21_workflow_returns_done_with_a_seven_char_merge_sha(payload_text):
    text = pad_task(payload_text)
    assert re.search(r"['\"`]DONE ", text), "no DONE result line"
    assert re.search(r"DONE [^\n]{0,60}merge ", text), "DONE line lacks 'merge <sha7>'"
    assert re.search(r"(slice|substring|substr)\(0,\s*7\)", text), "merge sha not cut to 7"


def test_o21_workflow_returns_failed_with_a_reason(payload_text):
    assert re.search(r"['\"`]FAILED ", pad_task(payload_text)), "no FAILED result line"


def test_o21_workflow_returns_needs_ruling_with_a_question(payload_text):
    assert re.search(r"['\"`]NEEDS_RULING ", pad_task(payload_text)), "no NEEDS_RULING line"


def test_o21_skill_workflow_mode_calls_pad_task_once_per_ready_task(payload_text):
    section = workflow_mode_section(payload_text(SKILL))
    assert "Workflow(" in section and "pad-task" in section
    assert re.search(r"\bonce\b|\bone `?Workflow`? call", section)


def test_o21_skill_workflow_mode_names_every_argument(payload_text):
    section = workflow_mode_section(payload_text(SKILL))
    for name in (
        "key",
        "ticket",
        "run",
        "epicBranch",
        "epicWorktree",
        "epicHead",
        "tier",
        "commands",
        "testPaths",
        "models",
        "ruling",
    ):
        assert re.search(rf"\b{name}\b", section), f"Workflow mode section lacks {name}"


def test_o21_skill_workflow_mode_lists_the_three_result_lines(payload_text):
    section = workflow_mode_section(payload_text(SKILL))
    assert "DONE <KEY> merge <sha7>" in section
    assert "FAILED <KEY> <reason>" in section
    assert "NEEDS_RULING <KEY> <question>" in section


# O22: a NEEDS_RULING result is resumed with the ruling, not restarted.


def test_o22_skill_workflow_mode_resumes_a_ruling_from_its_run_id(payload_text):
    section = workflow_mode_section(payload_text(SKILL))
    paras = [p for p in paragraphs(section) if "NEEDS_RULING" in p or "resumeFromRunId" in p]
    assert any("resumeFromRunId" in p and "ruling" in p for p in paras)
