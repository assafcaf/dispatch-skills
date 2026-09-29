---
name: setup-workflow
description: Wire this repo's delivery workflow to a machine and a tracker - detect the environment and the test stack, verify the tracker connection, write the config and the tracker agent, and check the harness is sound. Run once per machine, and again when the tracker or the toolchain changes.
argument-hint: "[jira | github | local]"
disable-model-invocation: true
---

# Set up the workflow here

Input: `$ARGUMENTS` names the tracker adapter; ask if it's missing. Nothing in this skill
creates a ticket or changes product code. Report findings as a checklist: what is ready, what
you fixed, what the operator must do.

## 1. The machine

Detect rather than assume; this repo is worked on from more than one kind of machine. Run the
checks, then write what you found to `CLAUDE.local.md` (gitignored, loaded into every session
in this checkout — never commit it).

| Check | How |
|---|---|
| OS and shell | `uname -s -r` (or `$OS`), and which shell this session runs |
| Toolchain | `git --version`, `gh --version`, and the versions of whatever the config's commands call |
| Suite | the configured setup and full-suite commands: record the pass/skip counts and the runtime here |
| Serial resources | for each one in the config, does its runner reach it from here? |
| Tracker CLI | `gh auth status` when the adapter is `github` |
| Text-file writes | the escape hatch in `.claude/workflow/writing-files.md` — see below |

**The text-file escape hatch.** That doc sends an agent to an interpreter heredoc when only
the shell will do, and names `CLAUDE.local.md` as where the working invocation is recorded.
Settle it here rather than leaving every run to find out. Which of `python3`, `python` or
`py -3` actually runs — a stub that exits "Permission denied" counts as not running — and does
non-ASCII survive a round trip: write a file containing `→`, then read it back, in two
separate commands. Where the write succeeds but echoing it back raises `UnicodeEncodeError`,
record that: the exit code is `1` for a write that worked, and an agent that doesn't know it
undoes a correct edit.

Write only facts that differ between machines, in this shape:

```markdown
# Local environment (not committed)

Observed <yyyy-mm-dd> by /setup-workflow.

- OS / shell: <…>
- Suite here: `<command>` → <n> passed, <m> skipped, ~<t>s
- <platform quirks that cost someone an hour here, e.g. path or shell differences>
- Text-file escape hatch: `<python3 | python | py -3>`; stdout <does | does not> need
  `sys.stdout.reconfigure(encoding='utf-8')` before printing non-ASCII
- Serial resources: <tag: reachable / unreachable>
```

Anything true on every machine belongs in `CLAUDE.md` or a skill instead, not here.

## 2. The stack

`config.md`'s **Commands** section ships as the installer's pytest defaults
(`config.example.md`); nothing detects the real stack for you. Do that here, every time this
runs — a repo can change stacks between visits.

- **Detect the runner.** Look for a manifest: `pyproject.toml` / `setup.cfg` → pytest,
  `package.json` → whatever its `test` script or devDependencies name (vitest, jest), `go.mod`
  → `go test`, `Cargo.toml` → `cargo test`. Ask the operator if none matches, or more than one
  does.
- **Fill in the table.** Setup, run-named-tests, full-suite and lint commands that actually
  work here — confirm each by running it, same as step 1's suite check.
- **Settle the exit-code contract.** The red gate needs to tell "ran and failed" apart from
  "never ran" (`definition-of-done.md`, item 2). Run the detected runner against a file with a
  failing assertion and against a file with an import error, and compare the exit codes.
  - **Different codes** (pytest: `1` vs `2`): record them in the Commands table's Red means row
    as they are. No wrapper needed.
  - **Same code** (vitest, jest, `go test` and `cargo test` all exit `1` for both): a task
    whose test file fails to import would otherwise certify as red with no assertion executed.
    Write a wrapper that restores the split, using `.claude/workflow/bin/vitest-gate.sh` as a
    worked example — adapt its output-matching to what the detected runner actually prints
    (its own "no test files" and "failed to load" wording), not vitest's. Put the wrapper in
    `.claude/workflow/bin/` and point the Commands table's run/full-suite rows at it instead of
    the runner directly. Verify it against all three cases: a passing run, a real failure, and
    an import error.
- **Weakened-test patterns.** `weakened-tests.sh` also defaults to pytest syntax (`def test_*`,
  `pytest.mark.skip`). Work out `WEAK_ADDED` and `TEST_DEF` for the detected syntax (see the
  script's header), verify each catches a real case, and record them in the Commands table's
  Weakened tests row so a run knows to export them.

## 3. The tracker

**`jira`:**
1. **Connection.** Call `atlassianUserInfo`. If the tools are missing or unauthorized, stop
   and tell the operator to run `/mcp`, pick `atlassian` and authenticate — the OAuth consent
   opens in a browser, so only they can do it. `.mcp.json` is read at session start, so a
   server added now needs a restart.
2. **Discover, never guess:** `getVisibleJiraProjects` for the cloud id and project (ask which
   project if more than one), `getJiraProjectIssueTypesMetadata` for the epic and task type
   names, `getIssueLinkTypes` for the blocking link, and `getTransitionsForJiraIssue` on any
   existing issue for the status names and transition ids.
3. **How tasks attach to epics.** Read one existing task that has an epic. If its `parent` is
   the epic, the project is team-managed and `createJiraIssue` takes `parent: <EPIC>`. If the
   epic sits in a custom field (usually "Epic Link"), note that field id in the config and in
   the adapter's Create task row.
4. **Record** all of it in `.claude/workflow/config.md`'s Tracker section, transition ids
   included.

**`github`:** confirm `gh auth status` and that the repo has issues enabled. **`local`:** no
connection to check.

Then write `.claude/agents/tracker.md` from
`.claude/skills/setup-workflow/tracker-agent-template.md`: fill in the adapter name and the
tools it needs (`mcp__atlassian` for Jira, `Bash` for GitHub, `Read, Edit, Write` for local).
Everything else the agent reads from the config at run time.

## 4. The status line

`.claude/statusline.py` is committed; where it lives on this machine is not. Install it into
`.claude/settings.local.json` (gitignored), merging with whatever that file already holds
rather than overwriting it:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /absolute/path/to/repo/.claude/statusline.py"
  }
}
```

- Use whichever Python 3 this machine has: `python3`, `python`, `py -3`, or
  `uv run --no-project python`. Check it runs before writing it in.
- Write the checkout's **absolute path with forward slashes**, even on Windows: Git Bash eats
  backslashes in this field and the status line then fails silently.
- If the operator already has a `statusLine` in their user settings, say what this one adds
  (progress through the epic this session is on: live from the run log during
  `/batch-implement`, and from the ledger between runs) and ask before shadowing it for this project. Porting the segment
  into their own status line is often the better trade — it reads two files and calls no API.
- Test it before reporting success:
  `echo '{"model":{"display_name":"test"}}' | python3 .claude/statusline.py`
  should print one line. It takes effect in the next session.

## 5. The harness

Check, fix what you safely can, and report the rest:

- `.claude/settings.json` sets `worktree.baseRef` to `head` — required for parallel waves. If
  the installer found an existing settings file it left it alone and wrote
  `.claude/settings.example.json`; merge its `worktree` key and permission rules in,
  preserving everything already there, and show the operator the diff.
- `.gitignore` covers `.work/`, `.claude/worktrees/`, `CLAUDE.local.md` and
  `.claude/settings.local.json`.
- `.claude/workflow/bin/*.sh` are executable (`git ls-files -s`, mode `100755`).
- The config's commands all run here: setup, full suite, lint. Quote the results.
- Serial resources in the config are reachable, or say which are not.
- The permission rules still cover what `/batch-implement` runs unattended: `git worktree add`
  and `remove`, `add`, `commit`, `cherry-pick`, `merge`, `revert`, `rev-parse`, `fetch`,
  `push origin`, and `gh pr create`; with pushes to the default branch denied. Report anything
  missing rather than adding it — widening permissions is the operator's to approve.

## 6. Project knowledge

Ask once:

> Knowledge-layer mode? (recommended: **on**)

Recommended on because every skill and agent here already works from `CLAUDE.md` alone, and
`CLAUDE.md` is loaded into every session whether a run needs it or not. The knowledge layer
gives a run two files scoped to what it actually reads: a glossary, and the notes an agent
cannot infer from the code.

| Answer | Do |
|---|---|
| **on** | Call the Skill tool with "knowledge-layer" and let it finish, then come back here. It writes `CONTEXT.md`, `.claude/workflow/project.md`, and the `Mode: on` table in the config |
| **off** | Leave the config's `## Project knowledge` section as it is. Nothing changes: off is the behavior everything had before the layer existed |

Off is not a worse answer for a repo whose `CLAUDE.md` is already good. It stays available:
`/knowledge-layer` can be run at any point later, and asks nothing of `/setup-workflow`.

## 7. CLAUDE.md

Offer the sections in `.claude/workflow/claude-md-snippet.md` — how work flows here, and the
writing rules — for the repo's `CLAUDE.md`. Show them, add only what the operator accepts, and
keep each addition short: every line of `CLAUDE.md` loads into every session.

## 8. Report

One checklist. For anything unresolved, name the command the operator should run. Finish with
the flow they can now use: `/spec` → `/tickets` → `/batch-implement`. Where the knowledge
layer is on, say that `/knowledge-layer refresh` re-scans it when the repo moves.
