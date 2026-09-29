# Workflow config

Read by `/spec`, `/tickets`, `/batch-implement` and the agents in `.claude/agents/`. Everything
specific to this repository lives here, so the skills and agents stay project-agnostic. The
installer wrote this from your answers; `/setup-workflow` fills in what it can discover
(statuses, transition ids, the commands that actually run here) and checks the rest. After
that it is yours: edit it when the project changes.

## Tracker

- **Adapter:** `local`. Operations are in `.claude/workflow/trackers/local.md`. Tickets live in
  the main checkout's `.work/tickets/<EPIC>/` (gitignored), never in a worktree's copy.
- **Statuses:** the frontmatter values `todo`, `doing`, `review`, `done`. No transition ids. A
  task that passes the definition of done moves to done; the epic moves to review when its PR
  opens.
- **Blocking link:** `blocked_by` in frontmatter.
- **Label for agent-created tickets:** `agent-planned`.

## Agents

Roles are agents in `.claude/agents/`, so each carries its own tools. Change a model here, not
in the agent file.

| Role | Agent | Model | Notes |
|---|---|---|---|
| Tracker | `tracker` | `haiku` | The only agent with tracker tools. Every ticket read and write goes through it |
| Planning | `task-planner` | `sonnet` | Read-only. Runs once per `/batch-implement` run |
| Task ownership | `ticket-owner` | `sonnet` | One per task. Runs the task's test-designer and code-writer, proves red, gates the branch, moves the ticket |
| Merging | `epic-merger` | `sonnet` | One per run. The epic branch's only writer: re-checks, merges one task at a time, gates, pushes |
| Tests | `test-designer` | `sonnet` | Its own worktree, dispatched by the ticket owner. Writes the failing tests and stubs |
| Code | `code-writer` | `sonnet` | Its own worktree, dispatched by the ticket owner. Cherry-picks the red commit; may not change tests |
| Knowledge scan | `knowledge-scanner` | `sonnet` | Read-only. Several at once, and only during `/knowledge-layer` |
| Memory curation | `memory-curator` | `sonnet` | Once per epic, at the end. Keeps the agents' memory clean; never adds a lesson |

### Tiers

`/tickets` gives every task a tier (`.claude/workflow/ticket-template.md`, "Tiers"). The tier
picks the flow and the models; the Tests and Code rows above are the `standard` defaults.

| Tier | Flow | Test-designer | Code-writer | Retry |
|---|---|---|---|---|
| `small` | one `code-writer` in solo mode: red commit, then green | — | `sonnet` | `opus`, standard flow |
| `standard` | `test-designer`, with a `code-writer` started alongside that implements once red is proven | `sonnet` | `sonnet` | `opus` code-writer |
| `complex` | as standard, wider reading brief | `opus` | `opus` | `opus` code-writer |

A ticket with no `## Tier` section is `standard`; one labelled `complex` is `complex`.

**Thinking effort** is set in an agent file's `effort:` field, and a dispatch can't override it,
so it can't follow a task's tier. The coordinators, whose work is the same in every task, have
one: `ticket-owner` `medium` (it makes the occasional ruling), `epic-merger` `low`. The test
and code agents inherit the session's effort; their tier brief ("Effort by tier") is what
scales their reading and thinking.

**Memory.** `test-designer`, `code-writer`, `ticket-owner`, `epic-merger` and `tracker` have
`memory: project`: each keeps lessons in `.claude/agent-memory/<agent>/MEMORY.md`, committed and
loaded on every start. The rules are in `.claude/workflow/agent-memory.md`, and
`memory-curator` enforces them at the end of each epic.

## Tracker updates during a run

So progress is visible without reading the terminal:

| When | Task | Comment |
|---|---|---|
| Wave starts | → doing | run id and epic branch |
| Red proven (standard, complex) | — | red sha, test count and files. A small task puts it in the done comment |
| Merged and gates green | → done | at most five lines: merge and red shas, red and green commands with results, files outside the ticket's list. The full evidence is in `.work/runs/<run id>/<KEY>.md` |
| Gate failed or blocked | stays doing | what failed, and what is needed |
| Epic finished | epic → review | PR URL |

## Paths

| What | Where | Committed |
|---|---|---|
| Working specs | `.work/specs/<yyyy-mm-dd>-<slug>.md` | no |
| Plans (task bodies + tracker keys) | `.work/plans/<slug>.md` | no |
| Run logs for `/batch-implement` | `.work/runs/<run-id>/progress.md` | no |
| Progress snapshot for the status line | `.work/progress.json` | no |
| Development record | `docs/decisions/NNNN-<slug>.md` | yes |
| Promoted specs | `docs/specs/<slug>.md` | yes, only when the operator says so |

`spec_commit: ask`. After a spec is approved, ask once whether to promote it. Default: no.

## Project knowledge

Mode: off

Off is what every skill and agent did before the knowledge layer existed, so leaving it off
changes nothing. Run `/knowledge-layer` to turn it on: it scans the repo for what it can cite,
asks you for what it cannot, writes `CONTEXT.md` and `.claude/workflow/project.md`, and
replaces this paragraph with the table of what each reader reads. Until then, agents work from
`CLAUDE.md` as they always have.

## Commands

Replace these with the commands that work in this repo; `/setup-workflow` runs each one and
reports what fails. The defaults below are pytest's, because they're the easiest stack to show
the contract on — not because the workflow assumes Python. `/setup-workflow`'s stack step
detects the real runner and fills this table in.

| Gate | Command |
|---|---|
| Setup in a fresh worktree | `python -m pip install -q pytest` (no package install: the tests drive `payload/` and `install.sh` from the checkout) |
| Run named tests | `python -m pytest -q {tests}` (`{tests}` = space-separated node ids) |
| Full suite | `python -m pytest -q tests` |
| Lint | `bash scripts/lint.sh` (`bash -n` on every tracked `.sh`, `compileall` on Python; shellcheck is not installed here) |
| Red means | exit code `1`: tests collected, ran, and failed. Collection errors (exit `2`) do not count |
| Test paths | `tests/` |
| Weakened tests | `bash .claude/workflow/bin/weakened-tests.sh <base> <head>` (pytest patterns by default; set `WEAK_ADDED` and `TEST_DEF` for another stack — see the script's header) |

**The exit-code contract.** "Red means" exists to tell "the test ran and failed" apart from
"the test never ran" (`definition-of-done.md`, item 2) — without that split, a task whose test
file fails to import certifies as red with no assertion ever executed. pytest gives this for
free: exit `1` is a failed assertion, exit `2` is a collection error, so its row above is just
those two numbers. Most other runners don't: vitest, jest, `go test` and `cargo test` all exit
`1` for both a failing assertion and a file that fails to load. On those, wrap the runner and
remap its output onto pytest's split before filling in this table — `bin/vitest-gate.sh` is a
worked example (0 passed, 1 real failure, 2 nothing ran); adapt its output-matching to the
runner you actually have rather than reusing vitest's wording. `/setup-workflow`'s stack step
checks which case you're in.

## Serial resources

Outcomes tagged with a resource run one task at a time, by the orchestrator, after merge. Use
this for anything the host can't provide or can't share: a GPU machine, a device, a staging
database.

`live` is **operator-run**: it needs a real Claude Code session, which no host-side test can provide. The orchestrator does not run it; the operator follows the probe in the ticket and pastes the result into the run log.

| Tag | Meaning | How to run |
|---|---|---|
| `live` | an outcome only a real Claude Code session can show (push notifications, the Workflow tool, answering a parked question mid-run) | operator-run: the ticket's probe, performed by the operator in a live session; result pasted into `.work/runs/<run id>/progress.md` |

## Local app

None. Optional: set the command that serves the app in dev mode with hot reload, and
`/batch-implement` runs it from the epic worktree during a run, so each merge shows up live.

| Command | URL |
|---|---|
| `<dev server command>` | `<where to open it>` |

## Execution

- **Branches:** epic branch `epic/<KEY>-<slug>`, in worktree `.claude/worktrees/<KEY>`.
  `.claude/settings.json` must set `worktree.baseRef: head`, so implementer worktrees branch
  from the epic branch.
- **Parallelism:** at most `3` tasks (ticket owners) at once.
- **Final review:** `off`. Set to a `/code-review` level (`low`, `medium`, …) to run one
  review over the finished epic branch before the PR.
- **Publishing:** the merger pushes the epic branch to `origin` after each merge, so tracker comments cite
  fetchable commits. Open the epic PR as a draft. Never merge it.
