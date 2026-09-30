"""E1-T27: preflight reports a checkout whose core.autocrlf and .gitattributes disagree (O44).

The check is named `line-endings`. A disagreement is `core.autocrlf=true` with a `.gitattributes`
that forces `eol=lf`, or `core.autocrlf` false/input with one that forces `eol=crlf`.
"""
from __future__ import annotations

import pytest

from conftest import git
from test_preflight import assert_failed, failures, install, last, preflight  # noqa: F401

SKILL = "claude/skills/setup-workflow/SKILL.md"


def configure(repo, autocrlf, attributes):
    install(repo)
    git("config", "core.autocrlf", autocrlf, cwd=repo)
    if attributes is not None:
        (repo / ".gitattributes").write_text(attributes + "\n", encoding="utf-8")
        git("add", ".gitattributes", cwd=repo)
        git("commit", "-q", "-m", "attributes", cwd=repo)


@pytest.mark.parametrize("autocrlf,attributes", [
    ("true", "* text=auto eol=lf"),
    ("true", "*.sh text eol=lf"),
    ("false", "* text eol=crlf"),
    ("input", "* text=auto eol=crlf"),
])
def test_o44_autocrlf_and_gitattributes_that_disagree_fail_the_line_endings_check(
    repo, preflight, autocrlf, attributes  # noqa: F811
):
    configure(repo, autocrlf, attributes)
    assert_failed(preflight(repo), "line-endings", "autocrlf", ".gitattributes")


@pytest.mark.parametrize("autocrlf,attributes", [
    ("true", "* text=auto eol=crlf"),
    ("input", "* text=auto eol=lf"),
    ("false", "* text=auto eol=lf"),
    ("false", None),
    ("input", None),
])
def test_o44_autocrlf_and_gitattributes_that_agree_pass_preflight(
    repo, preflight, autocrlf, attributes  # noqa: F811
):
    configure(repo, autocrlf, attributes)
    result = preflight(repo)
    assert not any(c == "line-endings" for c, _ in failures(result)), result.stdout
    assert last(result) == "PREFLIGHT OK", result.stdout


def test_o44_setup_proposes_a_gitattributes_and_waits_for_approval(payload_text):
    text = payload_text(SKILL)
    assert "load-probe.sh" in text
    assert "line-endings" in text
    lower = text.lower()
    at = lower.index(".gitattributes")
    assert "approv" in lower[max(0, at - 400): at + 600], "no approval around .gitattributes"
