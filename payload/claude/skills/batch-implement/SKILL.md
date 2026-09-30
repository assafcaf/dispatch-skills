---
name: batch-implement
description: Implement a batch of planned tasks test-first. Unblocked tasks run in parallel in isolated worktrees - tests designed first, then code written against them - and each merges only when the definition of done holds. Tracker status moves as it goes. Run as /batch-implement <epic key | task keys | plan path | outcomes>.
argument-hint: "<epic key | task keys… | plan path | outcomes in quotes>"
disable-model-invocation: true
---

# Tasks → tested, merged code

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` and
`.claude/workflow/definition-of-done.md`.

You orchestrate and never write product code yourself. You run three layers of agents:

| Agent | Does | Dispatched by |
|---|---|---|
| `task-planner` | Waves, file conflicts, interface mismatches, risks | You, once, before the first wave |
| `epic-merger` | The epic branch's only writer: re-checks, merges, gates, pushes, reverts | You, once, after the baseline |
| `ticket-owner` | One task from `doing` to `done`: its tests, its code, its gates, its ticket and run-log entry | You, one per task |
| `test-designer` | The task's failing tests + stubs, committed red | Its ticket owner |
| `code-writer` | Makes those tests pass, suite and lint green | Its ticket owner |
| `tracker` | Every tracker read and write | You only: the ledger's one writer. Owners never dispatch it. Local ledger updates go through `ledger.sh` |
| `memory-curator` | Keeps the agents' persistent memory clean: keeps, tightens, merges or deletes lessons, never adds them | You, once, at the end of the epic |

You pick the waves, answer what the owners can't settle, run the serial resources, and finish
the epic. A task's detail stays with its owner: you act on one report per task, not every step
of it. Owners and the merger also stop in between — `SUBMITTED`, the merger's per-merge line —
and each stop reaches you as a notification; end that turn without a tool call. That is the
point of the layer — every turn you take re-reads your whole context, so a
task's forty small steps cost far less in an owner's short context than in yours. There is no
code review: a task is done when the definition of done holds.

**Names and addresses.** Give every dispatch a description that names what it works on:
`<epic key>-merger`, `<task key>-owner`. Owners name theirs `<task key>-tests` and `-code`. The name is for people reading logs; messages are routed by the agent id each
dispatch returns, so keep the merger's id and every owner's id, and reply to a message at its
`from` address.

**Wait for notifications; never poll.** An agent's report arrives on its own when it stops.
A `sleep`, an `echo`, or a status check while you wait re-reads your whole context for nothing.

**Keep going without check-ins.** After the start confirmation, don't pause between tasks or
waves. When the tickets don't settle something, decide it and log
`Ruling: <decision> — <why> — <cost if wrong>`. Stop and ask only for:
- an irreversible action outside this flow
- a security-sensitive action
- changing shared state other than the epic branch and its tickets (`main`, a serial
  resource's current state, other tickets)
- a baseline that is already red
- every remaining task being blocked or failed
- `tracker` reporting `FAIL`, or its tools being unavailable: the run's record would silently
  stop matching the code
- the merger stopping with `FAIL`: it holds every task it hasn't answered until you send it
  `CONTINUE`

**Never override the weakened-tests gate.** No ruling lets the merger accept a test that
`weakened-tests.sh` flags, even when the spec calls for the rename or deletion. The owner keeps
the old test title with a body that asserts the new truth, and the gate passes as it is. An
override reads as a CI bypass to a permission classifier, which then denies every later step
toward that merge. Never edit your own permission settings to get past a denial either: give
the operator the rule to add.

**Check every sha before acting on it.** `git cat-file -t <sha>` must print `commit` for each
`RED` and `TASK_HEAD` an agent reports. Agents have reported full shas with the right prefix
and a wrong tail.

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
on the epic branch but has no `done` line isn't restarted: gate the epic head, push, and have
record it done (3f). Start a new merger (2.6).

**After compaction in the same session,** the agents are still running: restart nothing. The
run log's `agents:` lines give you back the merger's id and each owner's; trust the run log and
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
5. **Baseline.** Run setup, the full suite and lint. Log the results with the head sha. Red
   means stop: later failures can't be attributed. Once green, if a row of the config's `## Surfaces`
   sets a `Preview start` command, start it in the background from the epic worktree, so each merge shows up
   live for the operator. Restart it (after setup) when a merge changes a dependency manifest,
   lockfile or build config, or the page goes stale.
6. **Start the merger.** Dispatch `epic-merger` as `<epic key>-merger` with the epic branch,
   the run id, the setup, full-suite and lint commands, and the test paths. Append
   `agents: <epic key>-merger <id>` to the run log. It stops with `STARTED`; a `FAIL` means stop
   and ask. There is one merger per session: the epic branch's `git log` is its whole state, so
   a new session starts a fresh one, and nothing else does.

## 3. Run waves until no task is left

**a. Fill the free slots.** Ready tasks are those not done whose blockers are all done. Start
them in key order up to the parallelism limit, skipping only a task the planner listed under
`CONFLICTS` with one already running. Sharing a file is not a conflict: the merger merges
additions to one file, and a real conflict comes back as `CONFLICT` and is rebased. Don't wait
for a whole wave to close. Whenever an owner reports `DONE`, `FAILED` or `BLOCKED`, start
whatever is ready now. The waves are the plan's order, not a barrier.

**b. Dispatch one `ticket-owner` per task, in one message,** so they run in parallel. Name each
`<task key>-owner`, and append `agents: <task key>-owner <id>` to the run log. Each prompt carries: the ticket file's absolute path (not its text), the task key,
the task's tier (`small` | `standard` | `complex` from its `## Tier` section; a ticket with
none is `standard`, and one labelled `complex` is `complex`), the run id and epic branch, the
setup, named-tests, full-suite and lint commands, the config's test paths, that tier's models
and the retry model (per the config's Tiers table), any interface correction from an earlier
owner's `INTERFACES`. Never the merger's id: only you message the merger. An agent in an
isolated worktree that resumes it leaves it isolated there, unable to run git in the epic
worktree.

From here each owner proves red, gates its branch and hands it to you for
the merger; the merger merges one task at a time and gates the epic head after each merge. You
don't repeat their checks.

**c. Act on the reports.** Owners and the merger each stop with a short block. Act only on:

| Report | You |
|---|---|
| Owner `SUBMITTED` | Check the `READY` block's shas (above). Relay it to the merger unchanged, with one line added: `OWNER: <the owner's id>`. A bad sha goes back to the owner instead |
| Owner `NEEDS_RULING` | Decide it, log `Ruling: <decision> — <why> — <cost if wrong>`, and `SendMessage` the answer to the owner. If it needs the operator, it's one of the stop-and-ask cases above |
| Owner `MERGED_PENDING_RESOURCE` | Run its `RESOURCE_PROBES`, one at a time across the whole run, with the configured runner, at the merge sha — from a throwaway `git worktree add --detach`, because the merger keeps merging in the epic worktree meanwhile. Keep the output in the run log. Pass: message the owner `RESOURCE PASSED` with the output tail. Fail: message the merger `REVERT <key> <merge sha>`, wait for its `REVERTED` line, then message the owner `RESOURCE FAILED` with the output |
| Owner `DONE`, `FAILED`, `BLOCKED` | Record it (3f) from the owner's report, then fill the free slot (a). A failed or blocked task's dependents wait; everything else continues |
| Merger `REVERTED <KEY>` whose failing tests are all in files the task didn't touch and doesn't import | Rerun the full suite at the merge sha from a throwaway `git worktree add --detach`. Green means a false positive: message the merger `REMERGE <KEY> <revert sha>` with `OWNER: <id>`. The re-merge doesn't use the task's retry |
| Merger `FAIL: …; holding …` | Stop and ask. Once the operator has fixed it, message the merger `CONTINUE`; the held owners are still waiting and need nothing from you |

Everything else — the merger's `MERGED` / `REJECTED` / `CONFLICT` and other `REVERTED` lines —
is for the log; the owner already has it and handles its own retry. A flake that forces reruns
is fixed at its cause (`.claude/workflow/testing.md`, "Pass under load"), not rerun again.

**d. Inline instead** when the whole run is one task: skip the owner and the merger, and do
every role yourself, in order, in the epic worktree (or the current branch for quoted
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
dispatch `tracker`. A `tracker` `FAIL` is a stop-and-ask case.

## 4. Finish the epic

Once every owner has reported and the merger has answered every `READY`, the merger is idle and
you may commit and push on the epic branch yourself. Final-review fixes (step 2) go back through
it, so refresh the knowledge layer and write the development record after they land.

1. **Full gates** at the epic head.
2. **Final review.** If config sets a level, run `/code-review <level>`; fix only correctness
   findings, test-first: one `ticket-owner` per fix, dispatched with a slug instead of a ticket
   key, through the same merger. In an inline run, fix them inline.
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
   `PROJECT_MD_CANDIDATES` (for the operator to add to `project.md` or drop), and its
   `UPSTREAM_FIXES`. Then have `tracker` move the epic to the review status and comment the PR
   URL. Stop the local app if you started one.
7. **Report:** the PR URL, done / failed / blocked counts, and every `Ruling:` line — those are
   the decisions you made on the operator's behalf.
