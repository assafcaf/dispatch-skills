"""E1-T24 O37: knowledge-scanner returns surface candidates; /setup-workflow uses it for the
Surfaces rows even when knowledge mode is off."""
from __future__ import annotations

import re

SCANNER = "claude/agents/knowledge-scanner.md"
SETUP = "claude/skills/setup-workflow/SKILL.md"


def response_block(text: str) -> str:
    m = re.search(r"```\n(AREA:.*?)```", text, re.S)
    assert m, "no response block"
    return m.group(1)


def test_o37_scanner_response_block_has_a_surfaces_section(payload_text):
    block = response_block(payload_text(SCANNER))
    assert re.search(r"^SURFACES:\s*$", block, re.M)


def test_o37_scanner_surfaces_line_gives_surface_entry_path_and_how_invoked(payload_text):
    block = response_block(payload_text(SCANNER))
    after = block.split("SURFACES:", 1)[1]
    line = after.splitlines()[1]
    assert re.search(r"<surface>\s*\|\s*<entry path>\s*\|\s*<how invoked>", line), line


def test_o37_scanner_surfaces_section_comes_before_notes(payload_text):
    block = response_block(payload_text(SCANNER))
    assert "SURFACES:" in block and block.index("SURFACES:") < block.index("NOTES:")


def test_o37_scanner_drops_a_surface_it_cannot_cite_a_path_for(payload_text):
    body = payload_text(SCANNER)
    assert re.search(r"surface", body.split("## Check, in this order", 1)[1].split("## Response")[0], re.I)


def test_o37_setup_workflow_uses_the_knowledge_scanner_for_surfaces(payload_text):
    text = payload_text(SETUP)
    assert "knowledge-scanner" in text
    assert "SURFACES" in text


def test_o37_setup_workflow_scans_surfaces_even_when_knowledge_mode_is_off(payload_text):
    text = payload_text(SETUP)
    m = re.search(r"^#+ [^\n]*[Ss]urface[^\n]*$(.*?)(?=^#+ |\Z)", text, re.M | re.S)
    assert m, "no surfaces step in setup-workflow"
    step = m.group(1)
    assert "knowledge-scanner" in step
    assert re.search(r"(mode|knowledge)[^.\n]*\boff\b|\beven (when|if)\b", step, re.I), step
