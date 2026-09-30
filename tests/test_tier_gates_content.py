"""O24: each tier runs only the gates it needs.

Content tests: the agents' prose and the config's Commands table are the product, so these read
them. small and standard: designer runs named tests and typecheck; code-writer runs named tests,
typecheck and lint; complex adds one full suite before submission. The merge gate (full suite
and lint) is the epic-merger's and already exists.
"""
from __future__ import annotations

import re

DESIGNER = "claude/agents/test-designer.md"
WRITER = "claude/agents/code-writer.md"
CONFIG = "claude/workflow/config.example.md"


def numbered_step(text: str, number: int) -> str:
    """The text of procedure step `number` (from 'N. **' to the next numbered step or heading)."""
    m = re.search(rf"^{number}\. \*\*.*?(?=^\d+\. \*\*|^## )", text, re.S | re.M)
    assert m, f"no step {number}"
    return m.group(0)


def paragraphs_with(text: str, *needles: str) -> list[str]:
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [p for p in paras if all(n.lower() in p.lower() for n in needles)]


def test_o24_designer_step_runs_typecheck_with_the_named_tests(payload_text):
    step = numbered_step(payload_text(DESIGNER), 5).lower()
    assert "typecheck" in step
    assert "named tests" in step


def test_o24_designer_runs_the_full_suite_only_for_complex(payload_text):
    step = numbered_step(payload_text(DESIGNER), 5).lower()
    assert "complex" in step
    assert "full suite" in step
    # small and standard are named as the tiers that do not run it
    assert "small" in step and "standard" in step


def test_o24_code_writer_gate_step_names_named_tests_typecheck_and_lint(payload_text):
    step = numbered_step(payload_text(WRITER), 4).lower()
    for needle in ("named tests", "typecheck", "lint"):
        assert needle in step, needle


def test_o24_code_writer_runs_the_full_suite_only_for_complex(payload_text):
    step = numbered_step(payload_text(WRITER), 4).lower()
    assert "complex" in step
    assert "full suite" in step


def test_o24_code_writer_effort_note_no_longer_runs_full_suite_for_every_tier(payload_text):
    text = payload_text(WRITER).replace("**", "")
    hits = paragraphs_with(text, "iterate on the named tests only")
    assert hits, "the iterate-on-named-tests paragraph is gone"
    assert all("complex" in p.lower() for p in hits)


def test_o24_config_commands_table_has_a_typecheck_row(payload_text):
    assert re.search(r"^\| Typecheck \|", payload_text(CONFIG), re.M)


def test_o24_config_commands_table_has_dependency_directory_and_lockfile_rows(payload_text):
    text = payload_text(CONFIG)
    assert re.search(r"^\| Dependency directory \|", text, re.M)
    assert re.search(r"^\| Lockfile \|", text, re.M)
