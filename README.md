# dispatch-skills

A Claude Code workflow that takes an idea to merged, tested code: a spec of testable outcomes,
tickets in your tracker, then parallel implementation where every task's tests are written
first, proven to fail, and made to pass by a different agent that cannot edit them. The tracker
is updated as agents work, so progress is visible there.

```
/setup-workflow          →  config + tracker agent     once per machine: connection, metadata, status line
/knowledge-layer         →  CONTEXT.md + project.md    optional: a glossary, and what an agent cannot infer
/spec [grill] <idea>     →  .work/specs/…md            outcomes: Given/When/Then, each testable
/tickets <spec>          →  epic + tasks in tracker    outcome-sliced, blocking edges, waves
/batch-implement <epic>  →  epic branch + draft PR     tests designed, then code, in parallel
```

Every skill is user-invoked only (`disable-model-invocation`), so nothing starts on its own.

> **Status: new, and not yet run end to end.** Each gate script is behavior-tested and the
> installer is tested per tracker, but no epic has yet gone all the way through
> `/batch-implement`. Try it on a small epic first. What is unverified is listed
> [below](#not-yet-verified).

## How you use it

Three commands, three approval points, and one long unattended stretch at the end.

| Step | You run | You approve | Then it runs unattended |
|---|---|---|---|
| 1 | `/spec [grill] <idea>` | the outcomes, then the spec file | — |
| 2 | `/tickets <spec>` | the wave table | publishing the epic and its tasks |
| 3 | `/batch-implement <epic>` | the waves and the epic branch, once | every wave, through to the draft PR |

`/setup-workflow` comes before all of it, once per machine. `/knowledge-layer` is optional and
can be run at any point; see [below](#the-knowledge-layer).

**1. Idea → outcomes.** `/spec <idea>` brainstorms: purpose and constraints, then two or three
approaches with trade-offs, then the design in short sections you confirm one at a time.
`/spec grill <idea>` is the adversarial version. It maps the idea as a tree of decisions and
walks it depth-first, asking the hardest question each one raises, pushing back on "fast",
"robust" and "handle errors" until each is a number, a behavior or a non-goal, and probing the
failure paths — empty input, a dependency down, the run killed halfway. It stops when every
leaf is decided or explicitly deferred. Grill when you know roughly what you want and need the
holes found; brainstorm when you don't know yet.

It sizes the work first and tells you which size it picked. A small change skips the spec file
and goes straight to `/batch-implement` with the agreed outcomes; something spanning several
independent subsystems is split before anything is specced.

A feature-sized spec lands in `.work/specs/<date>-<slug>.md`: problem, outcomes, non-goals,
design, decisions, risks. Every outcome reads "Given …, when …, then …" and names its test
level (`unit`, `integration`, or a serial-resource tag). You review the file, and it is marked
approved only when you say so. Working specs are not committed, so anything a future reader of
the code would otherwise reverse-engineer — an interface, a data format, a rejected approach —
is written to `docs/decisions/NNNN-<slug>.md` and committed instead.

**2. Outcomes → the ledger.** `/tickets <spec path>` slices the spec vertically: each task
delivers one to three outcomes end to end and is testable on its own, never split by layer. It
declares the files each task will touch, but adds a blocking edge only where one task uses what
another builds, never merely because two share a file, so tasks run in parallel. It pins exact
interface names into both sides of every dependency, because an implementer only ever sees its
own ticket. And it gives every task a tier — `small`, `standard` or `complex` — that sets how
much process the task gets. A small one is a single agent writing a red commit then a green
one. A complex one gets separate test and code authors on the stronger model. For standard and
complex tasks the code-writer starts alongside the test-designer and reads the code while the
tests are written. It implements only once red is proven, and may ask the test-designer what a
test means, or object that one contradicts the ticket. The ticket settles any dispute, never
how hard a test is to pass.

You get one wave table, and it stops there. **Nothing is published before you approve it.**

Then it publishes through `tracker`, the ledger keeper: the only agent holding the tracker's
tools, so every skill and every other agent goes through it and the ledger has a single writer.
It refuses to create a duplicate epic or task, which is what lets a half-finished run be
re-run rather than unpicked.

**3. Tickets → tested, merged code.** `/batch-implement <epic key>` creates the epic branch and
works the waves. `task-planner` goes first, and its gaps can send you back to `/tickets`. Then
you confirm once — the waves, the epic branch, and that it will push that branch and move
tickets as tasks land — and after that it does not pause between tasks or waves. It stops only
for an irreversible or security-sensitive action, a change to shared state outside the epic
branch, a baseline that is already red, every remaining task being blocked, or the ledger
failing. Anything the tickets left unsettled it decides and logs as
`Ruling: <decision> — <why> — <cost if wrong>`. The agents it runs and the gates every task
must pass are [below](#how-a-run-works).

**4. What you get back.** The epic branch pushed, and a draft PR whose body carries the task
table, every ruling, anything failed or blocked, and what was not verified. The ledger updated
task by task as the run went, with the PR URL commented on the epic. An Outcome section
appended to the epic's `docs/decisions/` entry: what was built, where it departed from the
spec, and why.

## How a run works

`/batch-implement` orchestrates three layers of agents and writes no product code itself:

```
orchestrator (/batch-implement)
├── task-planner                 once, before wave 1
├── E3-merger     (epic-merger)  once per run: the epic branch's only writer
├── E3-T4-owner   (ticket-owner) one per task
│   ├── E3-T4-tests  (test-designer)
│   ├── E3-T4-code   (code-writer)
│   └── E3-T4-tracker (tracker)
└── E3-T7-owner   …
```

| Agent | Tools | Does |
|---|---|---|
| `task-planner` | read-only | Before wave 1: waves, file conflicts, interface mismatches, gaps |
| `ticket-owner` | dispatches, red proof, run log | One task from In Progress to Done: runs its test-designer and code-writer (or one solo code-writer for a small task), proves red, retries once, hands it to the merger, moves its ticket |
| `test-designer` | its own worktree | Writes the task's failing tests and stubs, commits them red. Answers the code-writer's questions, and fixes a test only if it contradicts the ticket |
| `code-writer` | its own worktree | Starts alongside the test-designer and reads the code, then cherry-picks the red commit once it is proven and makes the tests pass. Cannot change the tests, but may ask about them or object against the ticket |
| `epic-merger` | the epic worktree | Takes ready tasks one at a time: re-checks the tests, merges, runs the suite and lint, pushes, reverts a merge that turns the branch red |
| `tracker` | the tracker's only | Every ticket read and write, for whoever needs one, with an evidence comment at each step |
| `memory-curator` | the agents' memory | Once, at the end of the epic: keeps the agents' lessons accurate and short, never adds one |

The orchestrator acts on one report per task, when it is finished or needs a ruling. The
detail of a task — forty-odd git, gate and ledger steps — happens in its owner's short
context instead of the orchestrator's long one, which every orchestrator turn re-reads. Agents
are named after what they work on (`E3-T4-owner`), so the logs read as a tree; messages route
by the agent id each dispatch returns.

Each wave of unblocked tasks runs in parallel. A task merges into the epic branch only when:

- `verify-red.sh` shows its tests failing at the test-only commit, on an assertion rather than
  an import error;
- the code-writer's commits changed no test file, and `weakened-tests.sh` finds no added skip,
  xfail or TODO and no deleted test;
- the full suite and lint pass on the epic branch after the merge, which the merger checks after
  every single merge, so a red is always one task's.

There is no per-task code review. The tests are the contract, which is why they are written by
a different agent from the one satisfying them, and proven to fail before any code exists.
Outcomes that need a shared resource (a GPU machine, a device) run one task at a time, after
merge.

## Install

```bash
cd my-project
npx github:assafcaf/dispatch-skills
# or
uvx --from git+https://github.com/assafcaf/dispatch-skills dispatch-skills
```

It installs the skills and agents, then asks where your tickets live:

```
1) Jira            — via the atlassian MCP server        [default]
2) GitHub Issues   — via the gh CLI
3) local files     — markdown under .work/tickets/, not committed
```

Every question has a flag, so an unattended install answers them up front:

```bash
npx github:assafcaf/dispatch-skills --tracker jira --key ENG --jira-site acme
npx github:assafcaf/dispatch-skills --tracker github --gh-repo acme/widgets
npx github:assafcaf/dispatch-skills --tracker local
```

`--dry-run` shows every action without taking one. Re-running is safe: identical files are
skipped, and files that are yours once written are never overwritten.

Then restart Claude Code and run **`/setup-workflow`**. It checks the tracker connection,
discovers what the installer can't (statuses, transition ids, how tasks attach to epics), runs
the config's commands, installs the status line, asks whether you want the knowledge layer, and offers a short
section for your `CLAUDE.md`.

## Updating

PAD keeps changing. In an installed project, run **`/pad-update`** to bring the harness up to
PAD's latest commit (or `/pad-update <ref>` for a named one). It clones PAD, and on a branch:

- updates every file PAD ships, with a three-way merge against the PAD commit the project was
  installed from (`.claude/workflow/pad.lock`): untouched files are replaced, files only the
  project changed are kept, files both changed are merged, and you are asked only about a real
  conflict;
- deletes files PAD retired, unless the project changed them;
- runs the migration notes in `payload/migrations/` the project has not handled yet: the
  changes copying files cannot make;
- brings `config.md` up to the new version, runs preflight and the rehearsal, and opens a pull
  request that lists what changed and what is left for you (permission rules are never written
  for you).

A project installed before `/pad-update` existed has no lock and no such skill. Get the skill
by re-running the installer once, or by copying `payload/claude/skills/pad-update/` into
`.claude/skills/`; the first run finds the commit the harness came from by comparing files and
asks you to confirm it.

When a push to PAD needs more than file copies in the projects that use it, add a note:
`payload/migrations/README.md` has the format.

## What lands where

```
.claude/skills/{spec,tickets,batch-implement,setup-workflow,knowledge-layer,pad-update}/
.claude/workflow/pad.lock               the PAD commit the harness came from; committed
.claude/agents/{tracker,task-planner,ticket-owner,test-designer,code-writer,epic-merger,memory-curator,knowledge-scanner}.md
.claude/agent-memory/<agent>/MEMORY.md  each agent's lessons, committed; created as agents learn
.claude/workflow/config.md              ← yours: tracker, commands, paths, models, resources
.claude/workflow/definition-of-done.md
.claude/workflow/ticket-template.md
.claude/workflow/testing.md             how outcome tests are written
.claude/workflow/writing-files.md       which tool writes a prose file, and why not a heredoc
.claude/workflow/agent-memory.md        what an agent may write to its memory, and how
.claude/workflow/trackers/{jira,github,local}.md
.claude/workflow/bin/{verify-red,weakened-tests,vitest-gate,knowledge-paths}.sh
.claude/workflow/claude-md-snippet.md   offered to your CLAUDE.md by /setup-workflow
.claude/statusline.py                   model, branch, context, cost, run and epic progress
.claude/settings.json                   ← yours: worktree.baseRef + permissions (never overwritten)
docs/decisions/README.md                ← yours: the committed development record
CONTEXT.md                              ← yours: the glossary, if the layer is on
.claude/workflow/project.md             ← yours: the notes agents cannot infer, if it is on
.gitignore                              + .work/ .claude/worktrees/ CLAUDE.local.md .claude/settings.local.json
```

`.claude/workflow/config.md` is configuration, not documentation. Its **Commands** section is
what every gate runs; it ships with pytest's defaults, and `/setup-workflow` detects your
actual stack and makes it true of your repo — including a gate wrapper where the runner needs
one, `bin/vitest-gate.sh` is a worked example (see `config.example.md`'s Commands section for
why).

Working specs, plans and run logs live in gitignored `.work/`. Decisions a future reader would
otherwise reverse-engineer go in `docs/decisions/`. Facts true of one machine go in a
gitignored `CLAUDE.local.md`, which `/setup-workflow` writes.

## Agent memory

The agents a run uses — `test-designer`, `code-writer`, `ticket-owner`, `epic-merger` and
`tracker` — each keep a memory (`memory: project`), which Claude Code loads every time the agent
starts. An agent writes a line only after something failed or blocked it, it found what works,
and its next run would hit the same wall: one line, with the task key and date
(`.claude/workflow/agent-memory.md`). A denied command, a tool limit, a gate that fails for a
non-obvious reason — each is learned once.

A memory written by the model it guides can drift into noise, and agents follow bad guidance
rather than ignoring it. So at the end of each epic, `memory-curator` checks every line: still
true, not a one-task fact, not said elsewhere, short. It deletes, tightens, merges or moves
lines, never adds any, and commits the result on the epic branch. Its changes are listed in the
PR, along with anything it found that belongs in `project.md` (the operator's to write) or that
is really a harness bug to fix upstream.

This is separate from the knowledge layer below. Memory is what an agent learned about doing
its job here; `project.md` is what the operator knows about the product.

## The knowledge layer

Optional, and off unless you turn it on. `/knowledge-layer` writes two files:

| File | Carries |
|---|---|
| `CONTEXT.md` | the glossary: one word per concept, and the synonyms it beats |
| `.claude/workflow/project.md` | module map, invariants, standing overlaps, pitfalls |

It is built in two halves, because only one half is safe to generate. Read-only
`knowledge-scanner` agents fan out over the repo and report what carries a path: modules,
declared commands, term candidates, and the files recent commits keep touching. Everything that
cannot be cited (what the repo is for, what must stay true, what newcomers get wrong) is asked
of you and written down in your words.

That split is not caution for its own sake. A repository context file written by a model
measured **worse than no file at all** ([arXiv 2602.11988][ctx]: -0.5% on SWE-bench Lite, -2%
on AGENTbench, and over 20% added inference cost per task); one written by the repo's own
developers measured **+4%**. Agents obey a wrong context file rather than ignoring it.

`bash .claude/workflow/bin/knowledge-paths.sh` fails when a path either file names has gone, or
when either grows past its ceiling. `/batch-implement` ends an epic by naming what the layer was
missing, which is the half with evidence behind it: guidance tuned against observed agent
failures beats one-shot generation ([arXiv 2606.20512][pr]).

Turn it on at any time with `/knowledge-layer`, re-scan with `/knowledge-layer refresh`, and
turn it off by setting `Mode: off` in the config. With it off every skill and agent behaves
exactly as it did before the layer existed.

[ctx]: https://arxiv.org/abs/2602.11988
[pr]: https://arxiv.org/abs/2606.20512

## Settings it needs

`worktree.baseRef: head` is required. Without it, implementer worktrees branch from your
default branch instead of the epic branch and miss every earlier task. The shipped
`settings.json` also allows the git commands a run uses unattended, and denies branch
switching, stash, `reset --hard`, force-push and pushes to `main`/`master`. If you already have
a settings file, the installer leaves it alone and `/setup-workflow` merges these in with your
approval.

## Not yet verified

- An epic run end to end through `/batch-implement`.
- That an isolated subagent's worktree branches from the orchestrating session's worktree HEAD
  (the Claude Code docs say it does; untested here).
- That the `tracker` subagent can use the parent session's MCP tools (the docs say `tools:`
  accepts `mcp__<server>`; if not, `tracker` reports it and a run stops rather than letting
  the tracker drift from the code).
- The GitHub and local adapters.
- Agent memory in a real run: that memory stays in the main checkout for worktree-isolated
  agents (the docs say so), and that `memory-curator` keeps it useful.
- `/knowledge-layer` end to end on a real repo. Its gate script is exercised against
  passing, missing-path, over-ceiling and mode-off cases; the scan-and-grill flow is not.

## Licence

MIT — see [LICENSE](LICENSE). Third-party attribution is in [NOTICE](NOTICE).

### A Windows note

Git Bash rewrites POSIX-looking arguments into Windows paths before a native program sees them,
so `--project /home/me/app` reaches `node` already mangled. From Git Bash, pass a Windows-style
path (`--project D:/code/app`) or prefix the command with `MSYS_NO_PATHCONV=1`. From
PowerShell, cmd, macOS or Linux there is nothing to do.
