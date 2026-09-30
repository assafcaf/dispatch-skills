"""E1-T20: config.example.md describes surfaces, review cadence and resource classes."""
from __future__ import annotations

import re

CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/batch-implement/SKILL.md"

SURFACE_COLUMNS = [
    "Surface", "Entry point", "Test drives it by", "Person looks by", "Automated check",
    "Preview start", "Ready when", "Restart when changed", "Cannot show",
]


def section(text: str, heading: str) -> str:
    """Body of the `## <heading>` section, up to the next `## ` heading."""
    m = re.search(r"^## " + re.escape(heading) + r"[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"no '## {heading}' section"
    return m.group(1)


def header_cells(body: str) -> list[str]:
    for line in body.splitlines():
        if line.lstrip().startswith("|"):
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise AssertionError("no table in section")


def test_o32_config_has_surfaces_table_with_every_column(payload_text):
    body = section(payload_text(CONFIG), "Surfaces")
    assert header_cells(body) == SURFACE_COLUMNS


def test_o32_config_no_longer_has_local_app_section(payload_text):
    assert not re.search(r"^## Local app", payload_text(CONFIG), re.M)


def test_o32_review_cadence_defaults_to_after_first_wave_and_lists_the_options(payload_text):
    body = section(payload_text(CONFIG), "Review")
    assert re.search(r"Cadence:\**\s*`?after-first-wave`?", body)
    for option in ("after-first-wave", "per-wave", "end-only", "none"):
        assert option in body


def test_o32_batch_implement_skill_no_longer_refers_to_local_app(payload_text):
    assert "Local app" not in payload_text(SKILL)


def test_o45_serial_resources_table_has_class_column(payload_text):
    body = section(payload_text(CONFIG), "Serial resources")
    assert "Class" in header_cells(body)


def test_o45_serial_resources_explains_both_classes_and_review_packets(payload_text):
    body = section(payload_text(CONFIG), "Serial resources")
    assert "automated" in body
    assert "operator-run" in body
    assert "review packet" in body.lower()
