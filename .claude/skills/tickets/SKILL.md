---
name: tickets
description: Turn an approved spec into a work plan of outcome-based tasks with blocking edges, and publish it as an epic and tasks in the configured tracker. Run as /tickets <spec path | epic key>.
argument-hint: "<spec path | epic key>"
disable-model-invocation: true
---

# Spec → tickets

Input: `$ARGUMENTS`. Read, in order:
1. `.claude/workflow/config.md`
2. `.claude/workflow/ticket-template.md`
3. `.claude/workflow/definition-of-done.md`
4. the spec

When `.claude/workflow/config.md` has a `## Project knowledge` section set to `Mode: on`, read
`.claude/workflow/project.md`'s Module map as well: it is what each task's Files field is
otherwise guessing at.

Every tracker read and write goes through the `tracker` agent, which owns the tracker's tools
and its adapter. You never call the tracker directly.

An epic key means: ask `tracker` to `read-epic` and `read-task` its children, read the linked
spec, and plan only what's missing.

Nothing is published before the operator approves the plan.

## 1. Decompose along outcomes

- **Slice vertically.** Each task delivers one to three of the spec's outcomes end to end and
  is testable on its own. Never split by layer ("models", then "API", then "tests").
- **Cover every outcome.** Each spec outcome lands in exactly one task. Setup, config and
  docs work goes inside the task whose outcome needs it.
- **Declare files.** List the files each task will likely touch, and mark an edit that
  rewrites existing code rather than adding to it. Sharing a file is **not** a blocking edge:
  git merges separate additions to one file (a route, a prop, an import) on its own, and a
  real conflict is caught at merge and rebased. An edge for a shared file serialises the
  epic — a hub file like an app root or router is in almost every task, so every task ends
  up in its own wave.
- **Block only on use.** `Blocked by` means this task uses a name, a behaviour or data that
  the other one builds. If two tasks would rewrite the same code, give that code to one
  task and let the other consume it. If every task wires into one hub file, put the wiring
  in a final task.
- **Pin interfaces.** When a later task uses what an earlier one builds, write the exact
  names and signatures into both tasks' `Interfaces`, and the edge. Implementers see only
  their own ticket. A task that passes new props or arguments to something another task is
  changing is using it, even when the ticket only says "wire".
- **Keep outcomes consistent.** Two tasks must not assert different behaviour for the same
  screen, function or record. Where they meet, one owns the behaviour and the other's outcome
  names it.
- **Tag resources.** Mark outcomes that need a serial resource from the config, by its tag.
- **Assign a tier.** Every task gets `small`, `standard` or `complex`, with one line saying
  why (`ticket-template.md`, "Tiers"). The tier decides how many agents run the task and on
  which model, so be honest in both directions. A one-field change marked `standard` pays
  for two agents and a hand-off it didn't need. A cross-module change marked `small` loses
  the independent test author.
- **Size to one session:** as a rule of thumb, at most 3 outcomes and about 5 files.

## 2. Compute waves and show the plan

A task is in wave *n* when all its blockers are in earlier waves. Present one table and stop
for approval:

| Wave | Task | Tier | Outcomes | Blocked by | Files | Tags |
|---|---|---|---|---|---|---|

Below it, list any spec outcome with no task (there should be none), any decision you made
that the spec didn't state, and the longest chain of blocking edges. If that chain holds more
than about half the tasks, look again at each edge on it: an edge that exists only because
two tasks share a file is not a real one.

## 3. Write the plan file

After approval, write `.work/plans/<slug>.md`: the table, then every task's full body in the
ticket template. The plan file is how a re-run avoids duplicating tickets.

Write it with `Write`, not a heredoc — this is the longest prose file any skill here produces
and the one `.claude/workflow/writing-files.md` was written about.

## 4. Publish through the adapter

Send `tracker` one request per step, and record every key it returns in the plan file before
the next step. `tracker` refuses to duplicate an existing epic or task, so a re-run continues
where the last one stopped.

1. **Create the epic** (`create-epic`), or reuse the key you were given. Its description holds
   the problem, the outcomes and the spec path: the working spec is not committed, so the
   outcomes have to live in the tracker too.
2. **Create each task** (`create-task` with the epic as `KEY`) in wave order, body from the
   template.
3. **Replace placeholders.** Now that keys exist, rewrite each `Blocked by` and `Interfaces`
   section to name real keys, and send the corrected bodies back as `update` operations.
4. **Create every blocking edge** (`link`, with the blocker as `BLOCKER`).
5. **Record the epic key** in the spec's header (`Tracker: <key>`).

If `tracker` reports `FAIL`, stop and report what exists, with the keys from the plan file.

## 5. Hand off

Print the epic key, the wave table with keys, and: `/batch-implement <epic key>`.
