"""Plugins: project-owned additions to PAD agents, so a project never edits PAD's own files.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

import re

from conftest import PAYLOAD

PLUGINS = "claude/workflow/plugins.md"
CONFIG = "claude/workflow/config.example.md"
TRACKER = "claude/agents/tracker.md"
TEMPLATE = "claude/skills/setup-workflow/tracker-agent-template.md"


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}[ \t]*$", text, re.M)
    assert m, f"no '## {heading}' section"
    rest = text[m.end():]
    end = re.search(r"^## \S", rest, re.M)
    return rest[: end.start()] if end else rest


def test_plugins_live_under_a_directory_pad_update_never_touches(payload_text):
    text = payload_text(PLUGINS)
    assert ".claude/pad-plugins/" in text
    assert "never touches" in text
    assert not (PAYLOAD / "claude" / "pad-plugins").exists()


def test_a_plugin_file_names_what_it_extends_adds_and_runs(payload_text):
    text = payload_text(PLUGINS)
    for part in ("Extends:", "## Adds", "## How", "## Scripts", "## Failures"):
        assert part in text, part


def test_config_example_has_an_empty_plugins_table(payload_text):
    body = _section(payload_text(CONFIG), "Plugins")
    assert "| Plugin | Extends | Adds |" in body
    assert "None installed." in body


def test_tracker_reads_listed_plugins_and_runs_only_their_scripts(payload_text):
    text = payload_text(TRACKER)
    assert "**Plugins.**" in text
    assert "## Plugins" in text
    assert "Use `Bash` only to run a script a plugin" in text
    assert "<an operation a listed plugin adds>" in text


def test_tracker_template_adds_bash_only_for_a_plugin_with_scripts(payload_text):
    text = payload_text(TEMPLATE)
    assert "## Plugins" in text and "## Scripts" in text
    assert "never in this file" in text


def test_a_migration_brings_an_installed_tracker_up_to_plugins(payload_text):
    text = payload_text("migrations/0001-tracker-reads-plugins.md")
    assert "Applies when:" in text
    assert "**Plugins.**" in text
    assert "/setup-workflow upgrade" in text
