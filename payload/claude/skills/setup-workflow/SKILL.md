---
name: setup-workflow
description: Wire this repo's delivery workflow to a machine and a tracker - detect the environment and the test stack, verify the tracker connection, write the config and the tracker agent, and check the harness is sound. Run once per machine, and again when the tracker or the toolchain changes.
argument-hint: "[jira | github | local | moves | surfaces | load | capabilities | rehearse | upgrade]"
disable-model-invocation: true
---

# Set up the workflow here

Input: `$ARGUMENTS` names the tracker adapter (`jira`, `github` or `local`), or one sub-run
from the table below; ask if it's missing. With no sub-run, setup runs every step in order.
Nothing in this skill creates a ticket or changes product code. Report findings as a checklist:
what is ready, what you fixed, what the operator must do.

A sub-run redoes only its own step and skips all the others, so fixing one part of setup does
not mean running all of it again. It reads the tracker adapter from the config, so a sub-run
does not ask for the tracker. For an unknown argument, anything else than a tracker or a sub-run
named here, stop and ask, naming the sub-runs.

| Argument | Redoes |
|---|---|
| `moves` | step 5, only its `check-moves.sh` run: the permission rules the Git moves need |
| `surfaces` | step 7b: rescan the config's surface rows |
| `load` | step 7c: calibrate suite slots again |
| `capabilities` | step 7e: what Claude Code features this machine has |
| `rehearse` | step 8: the closing dry run of the delivery path |
| `upgrade` | step 7f: bring the config up to the installed PAD version |

Preflight names these sub-runs in its failures (`/setup-workflow upgrade`); run the one it names.

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
- Workflow tool: <available | not available> (Execution → Mode `<workflow | owner>`)
- Push notifications: <test push confirmed received | not confirmed> on <yyyy-mm-dd>
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
tools from the template's table: for Jira, the eight Jira tools the adapter's operations use,
never the whole `mcp__atlassian` server; `Bash` for GitHub; `Read, Edit, Write, Glob` for local.
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
- The Git moves are allowed: run `bash .claude/workflow/bin/check-moves.sh`. It proves each row
  of the config's Git moves table against the effective settings; report each row it fails,
  with the permission rule that would allow it.
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

## 7b. Surfaces

The config's `## Surfaces` rows come from a scan, not from guesswork: the operator is asked only
for what a scan cannot know. The scan's `SURFACES:` section gives one line
`<surface> | <entry path> | <how invoked>` per candidate.

Dispatch one `knowledge-scanner` agent over the repo root, put each entry path in the Entry
point column, and ask the operator for the other columns. This runs even when knowledge mode is
off: the rows belong to the config, not to the knowledge layer. Then run `knowledge-paths.sh`,
which fails on an entry point that does not resolve.

## 7c. Load probe

Calibrate how many suites can run at once. Run, with the config's full suite command:

```bash
bash .claude/workflow/bin/load-probe.sh <N> -- <full suite cmd>
```

It runs the suite alone, then N copies at once, and lists the tests that failed only under load.
Its last line, `SUGGEST slots=<n> parallelism=<n>`, gives the suite slots to propose to the
operator. Write them only once the operator accepts. Leave parallelism `none` unless the operator
asks for a cap: the slots already bound how many suites load the host at once.

## 7d. Line endings

Preflight's `line-endings` check fails when `core.autocrlf` and the repo's `.gitattributes`
disagree. When it does, or when the repo has no `.gitattributes` and the operator is on Windows,
propose a `.gitattributes` (for example `* text=auto eol=lf`) and show it in full. Never write it
without the operator's approval: it renormalizes files, and the operator decides. Once approved,
write it and commit it on its own.

## 7e. Capabilities

Find out which Claude Code features this machine has, and record them.

- **Workflow tool.** Check whether the Workflow tool is available in this session's tools. When
  it is available, set the config's Execution → Mode to `workflow` in `config.md`; when it is
  not, set it to `owner`. Ask before changing a Mode the operator already set by hand.
- **Push notifications.** Send a test push notification to the operator's phone (Remote
  Control connected), then ask the operator to confirm they received it. Record the answer: an
  operator who did not receive it, or does not answer, is recorded as not confirmed.

Write both results to `CLAUDE.local.md` (the `Workflow tool:` and `Push notifications:` lines
of step 1's template), replacing the lines already there.

## 7f. Upgrade

Bring an existing config up to the installed PAD. Run `bash .claude/workflow/bin/preflight.sh`
and read its `version` failure: it names the sections missing from `config.md`. Add each
missing section from `.claude/workflow/config.example.md`, keeping every value already in the
config and leaving its other sections as they are. Then set the config's `PAD version:` line
to the installed version in `.claude/workflow/VERSION`, and run preflight again: the `version`
check must pass.

## 8. Rehearsal

The closing step: run it after every other step, once the config and the harness are final.
From the main checkout, with its work committed:

```bash
bash .claude/workflow/bin/rehearse.sh
```

It runs the mechanical delivery path in throwaway worktrees — move onto the epic head, a
trivial red, `verify-red`, a trivial green, `task-submit`, `merge-task` into a throwaway epic
branch (pushed, then deleted from `origin`), a preview restart of the configured preview, and a
ledger write from a worktree to a temporary ticket — and prints `STEP <name> PASS|FAIL
<detail>` for each. It removes every branch, worktree and ledger change it made, whether a step
passed or not. The last line is `REHEARSAL OK` or `REHEARSAL FAILED <n>`.

- `REHEARSAL OK`: the delivery path works on this machine. Setup is done.
- `REHEARSAL FAILED <n>`: setup is **not** done. Quote each failing `STEP` line, fix what it
  names (a permission rule, the preview command, an unreachable `origin`, a ledger path), and
  run the rehearsal again. `rehearse.sh --keep` leaves the worktrees and branches for
  inspection; remove them afterwards.

## 9. Report

One checklist, ending with the rehearsal result: quote its last line. Report setup as done only
when the rehearsal printed `REHEARSAL OK`; on `REHEARSAL FAILED <n>`, report setup as not done
and list the failing steps. For anything unresolved, name the command the operator should run.
Finish with the flow they can now use: `/spec` → `/tickets` → `/batch-implement`. Where the
knowledge layer is on, say that `/knowledge-layer refresh` re-scans it when the repo moves.
