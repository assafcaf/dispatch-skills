---
name: batch-implement
description: Implement a batch of planned tasks test-first. Unblocked tasks run in parallel in isolated worktrees - tests designed first, then code written against them - and each merges only when the definition of done holds. Tracker status moves as it goes. Run as /batch-implement <epic key | task keys | plan path | outcomes>.
argument-hint: "<epic key | task keys… | plan path | outcomes in quotes> [--mode owner|workflow|spine]"
disable-model-invocation: true
---

# Tasks → tested, merged code

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` and
`.claude/workflow/definition-of-done.md`.

`--mode owner|workflow|spine` picks how tasks run. Without it, the mode defaults to
`.claude/workflow/config.md`'s Execution → Mode.

`spine` is not available yet: report that and stop.

`workflow` needs the Workflow tool. When it is unavailable, fall back to `owner` and log
`Ruling: workflow mode unavailable, ran as owner — the Workflow tool is missing — none, owner
mode is the default`.

You orchestrate and never write product code yourself. You run three layers of agents:

| Agent | Does | Dispatched by |
|---|---|---|
| `task-planner` | Waves, file conflicts, interface mismatches, risks | You, once, before the first wave |
| `ticket-owner` | One task from `doing` to `done`: its tests, its code, its gates, its ticket and run-log entry | You, one per task |
| `test-designer` | The task's failing tests + stubs, committed red | Its ticket owner |
| `code-writer` | Makes those tests pass, suite and lint green | Its ticket owner |
| `tracker` | Every tracker read and write | You only: the ledger's one writer. Owners never dispatch it. Local ledger updates go through `ledger.sh` |
| `memory-curator` | Keeps the agents' persistent memory clean: keeps, tightens, merges or deletes lessons, never adds them | You, once, at the end of the epic |

You pick the waves, answer what the owners can't settle, run the serial resources, and finish
the epic. A task's detail stays with its owner: you act on one report per task, not every step
of it. Owners also stop in between, at `SUBMITTED`, and each `merge-task.sh` you run in the
background ends with a notification of its own; act on it as 3c says, then end that turn. That is the
point of the layer — every turn you take re-reads your whole context, so a
task's forty small steps cost far less in an owner's short context than in yours. There is no
code review: a task is done when the definition of done holds.

**Names and addresses.** Give every dispatch a description that names what it works on:
`<task key>-owner`. Owners name theirs `<task key>-tests` and `-code`. The name is for people reading logs; messages are routed by the agent id each
dispatch returns, so keep every owner's id, and reply to a message at its
`from` address.

**Wait for notifications; never poll.** An agent's report arrives on its own when it stops.
A `sleep`, an `echo`, or a status check while you wait re-reads your whole context for nothing.

**Keep going without check-ins.** After the start confirmation, don't pause between tasks or
waves. When the tickets don't settle something, decide it and log
`Ruling: <decision> — <why> — <cost if wrong>`. Only these need the operator, as a question:
- an irreversible action outside this flow
- a security-sensitive action
- changing shared state other than the epic branch and its tickets (`main`, a serial
  resource's current state, other tickets)
- a baseline that is already red

**A question parks one task, not the run.** Send the operator a push notification with the
task key and the question, and append it to the run log as `QUESTION <KEY>: <question>` with
`bash .claude/workflow/bin/run-log.sh <run id> "QUESTION <KEY>: <question>"`. Then park only
that task: its owner waits for your answer, and its dependents wait with it — they are not
ready until it is done. A question that belongs to no one task (a red baseline) uses the epic
key. Never call `AskUserQuestion`
for a question: it blocks the whole session until someone answers.

**Everything else keeps moving while a task is parked.** Keep dispatching ready tasks, running
`merge-task.sh` for each `SUBMITTED` report. The operator answers by typing into this
session while it runs: log the answer as a `Ruling:` line, `SendMessage` it to the parked
owner, which resumes from where it stopped, and fill any slot the unparked task's dependents
open.

**Pause only when nothing is runnable.** When every task left is parked, blocked, failed or
waiting on one of those, and no owner or merge is still in flight, pause the whole run: send one more push
notification saying the run is paused and which questions hold it, append `PAUSED: <keys>` to
the run log, and end your turn. The next answer resumes the run.

**Log every halt with `halt-log.sh`.** When you park a task, and when you pause the run, run
`bash .claude/workflow/bin/halt-log.sh <run id> <KEY> <class> "<cause>" pending`, with `-` as
the key for a run-wide pause. It appends one line to `.claude/agent-memory/orchestrator/HALTS.md`
in the main checkout. The class names where the fix belongs: `pad` (this workflow), `project`
(the product, its tickets or spec), `machine` (this host: a tool, a port, a permission rule) or
`harness` (Claude Code itself). When the halt resolves, log a second line with the same run id,
key, class and cause, and what unblocked it in place of `pending`.

**Never override the weakened-tests gate.** No ruling lets a merge accept a test that
`weakened-tests.sh` flags, even when the spec calls for the rename or deletion. The owner keeps
the old test title with a body that asserts the new truth, and the gate passes as it is. An
override reads as a CI bypass to a permission classifier, which then denies every later step
toward that merge. Never edit your own permission settings to get past a denial either: give
the operator the rule to add.

## 1. Load the work

| Input | Tasks |
|---|---|
| Epic key | `tracker` `read-epic`, then `read-task` for each child that isn't done |
| Task keys | Those tasks, plus any unfinished blockers (ask before pulling in extras) |
| Plan path | The plan file's tasks and their recorded keys |
| Outcomes in quotes | One task, no tracker. Run it inline (3d) on the current branch, after asking: current branch, or a worktree? |

**Write each ticket body once,** to `.work/runs/<run id>/tickets/<KEY>.md` in the epic
worktree, with `Write`, as `tracker` returned it. From here every agent gets the file's
absolute path and reads it, rather than being handed the body as text. Each copy retyped into
a prompt is output that someone waits for, three times per task.

The run id is the epic key or a slug; the run log is `.work/runs/<run id>/progress.md` in the
epic worktree. Owners append their own lines to it, so you only ever append too, one line at a
time with `printf '%s
' '<line>' >> <path>`; longer notes go in
`.work/runs/<run id>/orchestrator.md`.

**Resuming in a new session.** If the run log exists, the earlier run's agents are gone. A task
with a `done`, `failed` or `blocked` line keeps it. A task in the doing status with none of
those starts over — remove any worktree and branch from its earlier attempt
(`git worktree list`) — and that doesn't use up its retry. A task whose `Merge <KEY>` commit is
on the epic branch but has no `done` line isn't restarted: gate the epic head, push, and
record it done (3f).

**After compaction in the same session,** the agents are still running: restart nothing. The
run log's `agents:` lines give you back each owner's id; trust the run log and
`git log` over your memory.

## 2. Start

1. **Plan.** Dispatch `task-planner` with the ticket bodies. Reconcile its waves with the
   tickets' own edges; log a ruling for each disagreement you settle. Drop the edges it lists
   under `EDGES TO DROP` unless you can name a use it missed, and take its `TIERS`
   suggestions unless the ticket says why not; log both as rulings. Its `CONTRADICTIONS`,
   `GAPS` and `RISKS` may change the models you choose or send you back to `/tickets`.
2. **Confirm once.** Show the waves with each task's tier, the critical path, the epic branch
   name, the planner's conflicts, contradictions and gaps, and that you will push that branch
   and update the tracker as tasks land. Wait for yes.
3. **Enter the epic worktree.** Create it if missing (`git fetch origin`, then
   `git worktree add .claude/worktrees/<KEY> -b <epic branch> origin/HEAD`), then
   Never call `EnterWorktree`: it
   moves your session and strands the agents you resume. Reach the epic worktree with
   `git -C .claude/worktrees/<KEY> <command>`, and pass that path to every agent.
4. **Check the base setting:** `.claude/settings.json` must set `worktree.baseRef` to `head`,
   or agents branch from the default branch and miss earlier tasks. Stop if it's missing. Even
   when set, `head` is the orchestrator's head: if you don't sit in the epic worktree it
   resolves to the default branch, so owners have their agents check their base (ticket-owner,
   Base check).
5. **Baseline.** Run setup, then `bash .claude/workflow/bin/preflight.sh` in the epic worktree.
   It proves the setup still holds: git moves and every unattended command allowed, knowledge
   paths resolve, config sections match the PAD version, dependency directory, agent models,
   executable scripts, `.gitignore`. On `PREFLIGHT FAILED <n>`, stop before any wave and show
   the operator its `PREFLIGHT FAIL` lines (an old PAD version names `/setup-workflow upgrade`).
   Then run the full suite and lint. Log the results with the head sha. Red
   means stop: later failures can't be attributed. Once green, start each configured preview with
   `bash .claude/workflow/bin/preview.sh start --surface <name> --worktree <epic worktree>` (a
   surface with no `Preview start` is a no-op), so each merge shows up live for the operator. Don't
   restart it yourself: `merge-task.sh` stops a running preview before setup and starts it again
   whenever a merge touches the surface's `Restart when changed` paths.

## 3. Run waves until no task is left

**a. Fill the free slots.** Ready tasks are those not done whose blockers are all done. Start
them in key order up to the parallelism limit, skipping only a task the planner listed under
`CONFLICTS` with one already running. Sharing a file is not a conflict: `merge-task.sh`
merges additions to one file, and a real conflict comes back as `CONFLICT` and is rebased. Don't wait
for a whole wave to close. Whenever an owner reports `DONE`, `FAILED` or `BLOCKED`, start
whatever is ready now. The waves are the plan's order, not a barrier.

**b. Dispatch one `ticket-owner` per task, in one message,** so they run in parallel. Name each
`<task key>-owner`, and append `agents: <task key>-owner <id>` to the run log. Each prompt carries: the ticket file's absolute path (not its text), the task key,
the task's tier (`small` | `standard` | `complex` from its `## Tier` section; a ticket with
none is `standard`, and one labelled `complex` is `complex`), the run id and epic branch, the
setup, named-tests, full-suite and lint commands, the config's test paths, that tier's models
and the retry model (per the config's Tiers table), any interface correction from an earlier
owner's `INTERFACES`.

From here each owner proves red, gates its branch and hands it to you. You land it with
`merge-task.sh`, which takes the merge lock, so tasks merge one at a time, each gated on the head
the one before produced. You don't repeat the owner's checks.

**c. Act on the reports.** Owners stop with a short block, and each `merge-task.sh` run ends
with one last line. Act only on:

| Report | You |
|---|---|
| Owner `SUBMITTED` | Run `bash .claude/workflow/bin/merge-task.sh --worktree <epic worktree> --branch <epic branch> --setup "<setup>" --gate "<full suite>" --lint "<lint>" --test-paths "<test paths>" <KEY> <RED> <TASK_HEAD> "<GOAL>"` with the `READY` block's values, in the background (`run_in_background`), and end your turn. When it exits, `SendMessage` the owner its last line unchanged (`MERGED …`, `REJECTED …` or `CONFLICT …`), except in the two cases below |
| `merge-task.sh` `REJECTED` whose failing tests all sit in files the task didn't touch and doesn't import | A false positive: the script already reran them once. Resubmit it once: rerun `merge-task.sh` in the background with the same `RED` and the same `TASK_HEAD`. This doesn't use the task's retry, and the owner hears only the rerun's last line |
| `merge-task.sh` exit 2 (`ERROR <KEY>: …`) | Infrastructure, not the task. Run it once more, from a fresh start in the background; when the error says the merge is committed locally, the fresh start is the config's `push-epic` move instead, and the owner then gets `MERGED <sha>`. A second `ERROR` is a question (above): park that task. It never uses the task's retry |
| Owner `NEEDS_RULING` | Decide it, log `Ruling: <decision> — <why> — <cost if wrong>`, and `SendMessage` the answer to the owner. If it needs the operator, it's a question (above): park the task |
| Owner `MERGED_PENDING_RESOURCE` | Run its `RESOURCE_PROBES`, one at a time across the whole run, with the configured runner, at the merge sha — from a throwaway `git worktree add --detach`, because other merges keep landing in the epic worktree meanwhile. Keep the output in the run log. Pass: message the owner `RESOURCE PASSED` with the output tail. Fail: once no `merge-task.sh` is running, revert that merge in the epic worktree with the config's `revert-merge` move (`## Git moves`), run the full suite and lint there, push with `push-epic`, then message the owner `RESOURCE FAILED` with the output. A serial-resource failure after a merge is the only reason a merge is ever reverted |
| Owner `DONE`, `FAILED`, `BLOCKED` | Record it (3f) from the owner's report, then fill the free slot (a). A failed or blocked task's dependents wait; everything else continues |

Every other last line goes to the owner as it is, and into the log; the owner handles its own
retry. A flake that forces reruns is fixed at its cause (`.claude/workflow/testing.md`, "Pass
under load"), not rerun again.

**d. Inline instead** when the whole run is one task: skip the owner, and do every role
yourself, landing it with `merge-task.sh`, in order, in the epic worktree (or the current branch for quoted
outcomes). Same gates, same run-log line, and the same tracker comments when there is a
tracker.

**e. Record each finished task** when its owner reports `DONE`, `FAILED` or `BLOCKED`.
1. For a `DONE` task, run `.claude/workflow/bin/render-evidence.sh --run <id> --key <KEY>
   --red <sha> --merge <sha> --outcomes "<O ids>" --red-result "<cmd -> result>"
   --green-result "<cmd -> result>"`, adding `--files-outside "<paths>"` from the owner's
   `FILES_OUTSIDE` and `--rulings "<text>"` for yours. It writes `<KEY>.md`, appends the run-log
   line and prints the PR-table row; don't write those by hand. For `FAILED` or `BLOCKED`, one
   `run-log.sh` line with the key, your rulings and the owner's `INTERFACES` is enough.
2. Refresh the progress snapshot, unless the adapter is `local` — there the status line reads
   the ticket files directly and a snapshot would only go stale. Overwrite
   `.work/progress.json` in the **main checkout**, not this worktree
   (`git rev-parse --git-common-dir`, then its parent), with the epic's standing counts on one
   line: `{"epic":"<epic key>","done":<n>,"total":<n>,"doing":["<task key>"],"updated":"<ISO-8601 UTC>"}`.
   `total` is the epic's task count, `done` and `doing` the tasks in those configured statuses;
   the status line prints `epic` and `doing` verbatim, so use the tracker's own keys. A
   snapshot older than six hours is shown as stale, so never carry an old `updated` forward.
   Nothing else reads this file — if the write fails, note it and carry on.

**f. Write the ledger.** You are the only ledger writer; owners report and never dispatch
`tracker`. At dispatch (b), record `doing` with a comment naming the run id, the epic branch
and the tier. On an owner's report, record from its `LEDGER_COMMENT` line: `DONE` moves the
task to `done`; `FAILED` and `BLOCKED` comment it and leave the status at `doing`. With the
`local` adapter run `bash .claude/workflow/bin/ledger.sh <KEY> status <doing|done> "<comment>"`
(or `ledger.sh <KEY> comment "<text>"`) from the epic worktree; with any other adapter,
dispatch `tracker`. A `tracker` `FAIL` never stops the run: log the write it missed with
`run-log.sh`, carry on, and make the missed writes again before you open the PR (step 4).

## Workflow mode

With `--mode workflow` (or Execution → Mode `workflow`), the saved workflow `pad-task`
(`.claude/workflows/pad-task.js`) replaces the owner and your merges. Steps 1, 2 and 4 are the
same, and so are the question, halt-log and ruling rules; section 3 changes as follows.

For each ready task (3a), make one `Workflow` call, once per task, in the background. Don't
write the ledger or the evidence for it: the workflow does.

```
Workflow({name: 'pad-task', args: {key, ticket, run, epicBranch, epicWorktree, epicHead, tier,
  commands: {setup, named, full, lint, typecheck}, testPaths, models: {tier, retry}, ruling?}})
```

`key` is the task key, `ticket` the ticket file's absolute path, `run` the run id,
`epicBranch` and `epicWorktree` the epic branch and its worktree path, `epicHead`
`git -C <epic worktree> rev-parse HEAD` now, `tier` from the ticket (3b), `commands` the
config's setup, named-tests, full-suite, lint and typecheck commands (add `deps` and `lockfile`
from its Dependency directory and Lockfile rows when set), `testPaths` the config's test paths,
`models` the tier's model and the retry model, and an optional `goal`, the ticket's goal line,
for the merge commit. `ruling` is only for a resumed run (below).

The workflow runs test-designer → red proof → code-writer → `task-submit.sh` →
`merge-task.sh` → ledger, run log and evidence, every script through the `gate-runner` agent.
It applies the retry rules itself (ticket-owner.md, "One retry"; an agent that returns `null`
is re-dispatched once and doesn't use the retry), and returns one result line:

| Result | You |
|---|---|
| `DONE <KEY> merge <sha7>` | Nothing to record: ledger, run log and evidence are written. Refresh the progress snapshot (3e.2), then fill the free slot (3a) |
| `FAILED <KEY> <reason>` | Its dependents wait; everything else continues. Fill the free slot |
| `NEEDS_RULING <KEY> <question>` | Decide it, or park the task as a question (above) |

Answer a `NEEDS_RULING` by resuming that run, not by starting a new one: call `Workflow` again
with `resumeFromRunId` set to its run id and the same args plus `ruling: "<your ruling>"`, and
log the `Ruling:` line. The steps already completed replay from cache; only the step that asked
and the rest run.

## Review checkpoints

Read `Cadence` under `## Review` in `.claude/workflow/config.md`: `after-first-wave`,
`per-wave`, `end-only` or `none`. At each checkpoint the cadence names (after the first wave,
after every wave, or never for `end-only` and `none`), write a review packet to
`.work/runs/<id>/review-<n>.md`, with `<n>` counting up from 1. The packet lists:

- what merged since the last checkpoint (task keys and merge shas);
- the surfaces those tasks touched;
- how to look at each surface: the command or URL to open it;
- what is unverified: outcomes no gate or check covered;
- what is operator-run: serial resources and live checks only the operator can do.

Then send the operator a push notification saying the review packet is ready, using the same
notification path as a parked question (above). A checkpoint does not stop the run: keep
filling slots and running waves without stopping while the operator reads.

Each finding the operator returns becomes a `fix-<slug>` task in the same run, with its own red
red test first, and goes through `merge-task.sh` like any task. The final review at the end of the
epic (step 4) is unchanged.

## 4. Finish the epic

Once every owner has reported and no `merge-task.sh` is running, you may commit and push on the
epic branch yourself. Final-review fixes (step 2) land through `merge-task.sh` like any task, so refresh the knowledge layer and write the development record after they land.

1. **Full gates** at the epic head, then `bash .claude/workflow/bin/surface-checks.sh`: any
   `SURFACES FAIL <surface>` line fails the gate. Then stop each preview started at the baseline with
   `bash .claude/workflow/bin/preview.sh stop --surface <name> --worktree <epic worktree>`, so it
   holds no file in the worktree.
2. **Final review.** If config sets a level, run `/code-review <level>`; fix only correctness
   findings, test-first: one `ticket-owner` per fix, dispatched with a slug instead of a ticket
   key, landed by `merge-task.sh`. In an inline run, fix them inline.
3. **Knowledge refresh.** Only when the config's `## Project knowledge` section is `Mode: on`.
   Run `/knowledge-layer refresh` against the epic head. Approve its cited lines (terms,
   modules, paths, overlaps) as a ruling; What this repo is, Invariants and Pitfalls stay as
   they are. A doubt about them, or a blocker whose answer was already an Invariant, goes in
   the PR body for the operator. Commit the result on the epic branch. Do not edit those
   files yourself: a line the operator did not write is the kind that measures worse than no
   line at all.
4. **Development record.** Append an Outcome section to the epic's `docs/decisions/` entry, or
   create one per `docs/decisions/README.md`: what was built, where it departed from the spec,
   and why. Use `Edit` to append and `Write` to create, not a heredoc
   (`.claude/workflow/writing-files.md`). Commit it.
5. **Curate the agents' memory.** Dispatch `memory-curator` as `<epic key>-memory` with the
   epic worktree's path, the epic branch and the run log's path, and wait for its report.
   Agents added lessons to their memory during the run (`.claude/workflow/agent-memory.md`).
   The curator keeps, tightens, merges or deletes them, and commits the result on the epic
   branch. A `BLOCKED` doesn't stop the epic: note it for the PR body.
6. **Push and open a draft PR** (`gh pr create --draft`) whose body has the epic link, a table
   of tasks (key, outcomes, merge sha), the rulings, failed or blocked tasks, what was not
   verified, and an **Agent memory** section: the curator's `CHANGED` lines, its
   `PROJECT_MD_CANDIDATES` (for the operator to add to `project.md` or drop), its
   `UPSTREAM_FIXES`, its `LOCAL_CANDIDATES` (for `CLAUDE.local.md`) and its
   `REPEATED_RULINGS` (questions for the next `/tickets`), each group listed separately. Then have `tracker` move the epic to the review status and comment the PR
   URL. Stop the local app if you started one.
7. **Report:** the PR URL, done / failed / blocked counts, and every `Ruling:` line — those are
   the decisions you made on the operator's behalf.
