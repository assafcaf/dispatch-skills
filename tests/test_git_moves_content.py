"""O1 (and O3's prose): prompts name git moves as capabilities, never as commands settings deny.

Content tests: the agents' and skills' prose is the product, so these read it. A command is an
inline code span, or a line of a fenced block, that starts with `git `. The deny rules come from
`settings.example.json`; the capabilities from the `## Git moves` table of `config.example.md`.
The convention a prompt follows is "run the `<capability>` move from `config.md`'s Git moves".

`epic-merger.md` is left out of the raw-command check only: its merge steps belong to E1-T11,
which rewrites them in the same epic. It is still held to the deny check.
"""
from __future__ import annotations

import json
import re

from conftest import PAYLOAD

SETTINGS = "claude/settings.example.json"
CONFIG = "claude/workflow/config.example.md"
WRITER = "claude/agents/code-writer.md"
DESIGNER = "claude/agents/test-designer.md"
OWNER = "claude/agents/ticket-owner.md"
MERGER = "claude/agents/epic-merger.md"
MEMORY_RULES = "claude/workflow/agent-memory.md"

PLACEHOLDER = re.compile(r"<[^<>]+>")
VALUE = "pad0placeholder9value"


def prompt_files() -> list[str]:
    """Every agent and skill file of the payload, plus agent-memory.md (its example line)."""
    agents = sorted((PAYLOAD / "claude" / "agents").glob("*.md"))
    skills = sorted((PAYLOAD / "claude" / "skills").rglob("*.md"))
    files = [p.relative_to(PAYLOAD).as_posix() for p in agents + skills]
    assert files, "no agent or skill files found"
    return files + [MEMORY_RULES]


def flat(text: str) -> str:
    """Lowercased, markdown emphasis dropped, whitespace collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def git_commands(text: str) -> list[str]:
    """Each `git ...` command a text spells out: inline code spans and fenced-block lines."""
    parts = re.split(r"^\s*```[^\n]*$", text, flags=re.M)
    candidates: list[str] = []
    for i, part in enumerate(parts):
        if i % 2:
            candidates += part.splitlines()
        candidates += re.findall(r"`([^`\n]+)`", part)
    commands = []
    for c in candidates:
        for piece in re.split(r"&&|\|\||;|\|", c):
            piece = re.sub(r"\s+", " ", piece).strip()
            if piece.startswith("git "):
                commands.append(piece)
    return commands


def git_moves(payload_text) -> dict[str, str]:
    """Capability -> command, from the config example's `## Git moves` table."""
    text = payload_text(CONFIG)
    m = re.search(r"^## Git moves\s*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "no ## Git moves section in config.example.md"
    moves = {}
    for line in m.group(1).splitlines():
        cells = [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in ("Capability", "") or set(cells[0]) <= set("-:"):
            continue
        moves[cells[0]] = cells[1]
    assert moves, "the Git moves table has no rows"
    return moves


def deny_rules(payload_text) -> list[str]:
    rules = json.loads(payload_text(SETTINGS))["permissions"]["deny"]
    assert rules, "settings.example.json denies nothing"
    return rules


def _glob(s: str, g: str) -> bool:
    return re.fullmatch(".*".join(re.escape(x) for x in g.split("*")), s, re.S) is not None


def denied(command: str, rule: str) -> bool:
    """Claude Code's Bash rule forms: exact, `cmd:*` prefix, `*` glob (a trailing ` *` is optional)."""
    cmd = PLACEHOLDER.sub(VALUE, command)
    if rule == "Bash":
        return True
    if not (rule.startswith("Bash(") and rule.endswith(")")):
        return False
    body = rule[5:-1]
    if body.endswith(":*"):
        pre = body[:-2]
        return _glob(cmd, pre) or _glob(cmd, pre + " *")
    if "*" in body:
        return _glob(cmd, body) or (body.endswith(" *") and _glob(cmd, body[:-2]))
    return cmd == body


def fixed_words(command: str) -> list[str]:
    """The words of a move's command before its first placeholder."""
    words = []
    for w in command.split():
        if PLACEHOLDER.search(w) or w.startswith("<"):
            break
        words.append(w)
    return words


def named_moves(text: str) -> list[str]:
    """Capabilities a text asks for in the convention "the `<capability>` move".

    A list works too: "the `a` or `b` move", "the `a`, `b` and `c` moves".
    """
    token = r"`[a-z][a-z0-9-]*`"
    lists = re.findall(
        rf"\bthe\s+((?:{token}\s*(?:,|,?\s*or|,?\s*and)\s*)*{token})\s+moves?\b", text
    )
    return [name for group in lists for name in re.findall(r"`([a-z][a-z0-9-]*)`", group)]


def procedure_steps(text: str) -> dict[int, str]:
    m = re.search(r"^## Procedure\s*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "no Procedure section"
    parts = re.split(r"^(\d+)\. ", m.group(1), flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def base_check(text: str) -> str:
    m = re.search(r"\*\*Base check\.\*\*(.*?)(?:\n\s*\n|\Z)", text, re.S)
    assert m, "no Base check paragraph in ticket-owner.md"
    return m.group(1)


def owner_cleanup(text: str) -> str:
    steps = [s for s in procedure_steps(text).values() if flat(s).startswith("finish.")]
    assert steps, "no Finish step in ticket-owner.md"
    return steps[0]


# --- O1: nothing a prompt prescribes is denied ---


def test_o1_no_prompt_prescribes_a_command_the_example_settings_deny(payload_text):
    rules = deny_rules(payload_text)
    # Hand-checked: the matcher must flag this one, or the scan below proves nothing.
    assert any(denied("git reset --hard <sha>", r) for r in rules)
    hits = [
        f"{path}: `{cmd}` matches {rule}"
        for path in prompt_files()
        for cmd in git_commands(payload_text(path))
        for rule in rules
        if denied(cmd, rule)
    ]
    assert not hits, "\n".join(hits)


def test_o1_agent_memory_example_names_no_denied_command(payload_text):
    rules = deny_rules(payload_text)
    cmds = git_commands(payload_text(MEMORY_RULES))
    assert not [c for c in cmds if any(denied(c, r) for r in rules)]


# --- O1: git moves are named as capabilities, not spelled as commands ---


def test_o1_no_prompt_spells_a_git_moves_command_raw(payload_text):
    moves = git_moves(payload_text)
    hits = []
    for path in prompt_files():
        if path == MERGER:
            continue
        for cmd in git_commands(payload_text(path)):
            words = cmd.split()
            for cap, move in moves.items():
                pre = fixed_words(move)
                if words[: len(pre)] == pre:
                    hits.append(f"{path}: `{cmd}` is the `{cap}` move spelled raw")
    assert not hits, "\n".join(hits)


def test_o1_every_move_a_prompt_names_is_in_the_git_moves_table(payload_text):
    moves = git_moves(payload_text)
    named = {
        (path, cap) for path in prompt_files() for cap in named_moves(payload_text(path))
    }
    assert named, "no prompt names a git move as a capability"
    unknown = sorted(f"{path}: `{cap}`" for path, cap in named if cap not in moves)
    assert not unknown, "\n".join(unknown)


def test_o1_every_prompt_naming_a_move_points_to_config_git_moves(payload_text):
    naming = [p for p in prompt_files() if named_moves(payload_text(p))]
    assert naming, "no prompt names a git move as a capability"
    missing = [p for p in naming if "Git moves" not in payload_text(p)]
    assert not missing, missing


def test_o1_code_writer_takes_the_tests_with_the_take_red_move(payload_text):
    steps = procedure_steps(payload_text(WRITER))
    take = [s for s in steps.values() if "take-red" in named_moves(s)]
    assert take, "no code-writer Procedure step names the `take-red` move"


def test_o1_code_writer_takes_a_follow_up_red_with_the_rebase_red_move(payload_text):
    assert "rebase-red" in named_moves(payload_text(WRITER))


def test_o1_test_designer_rebases_its_red_with_the_rebase_red_move(payload_text):
    text = payload_text(DESIGNER)
    paras = [p for p in re.split(r"\n\s*\n", text) if "rebase" in p.lower()]
    assert any("rebase-red" in named_moves(p) for p in paras)


def test_o1_owner_base_check_names_the_move_onto_sha_move(payload_text):
    assert "move-onto-sha" in named_moves(base_check(payload_text(OWNER)))


def test_o1_owner_cleanup_removes_worktrees_with_the_remove_worktree_move(payload_text):
    assert "remove-worktree" in named_moves(owner_cleanup(payload_text(OWNER)))


def test_o1_owner_cleanup_deletes_branches_with_the_delete_merged_branch_move(payload_text):
    assert "delete-merged-branch" in named_moves(owner_cleanup(payload_text(OWNER)))


# --- O3's prose: the red commit is taken, not copied, so every branch deletes ---


def test_o3_code_writer_never_cherry_picks(payload_text):
    assert "cherry" not in flat(payload_text(WRITER))


def test_o3_code_writer_report_has_no_cherry_picked_red_field(payload_text):
    assert "CHERRY_PICKED_RED" not in payload_text(WRITER)


def test_o3_owner_cleanup_expects_no_branch_to_be_left_undeleted(payload_text):
    step = flat(owner_cleanup(payload_text(OWNER)))
    assert "cherry" not in step
    assert "refuses" not in step
    assert "is left" not in step
