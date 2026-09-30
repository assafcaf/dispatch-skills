# 0002. Setup proves the delivery path, and each step of a run is a script

Date: 2026-09-30 · Status: accepted · Tracker: E1

## Context
A retrospective of ten `/batch-implement` epics on one project found that a task's own work is
short, but runs lost hours elsewhere: one question froze a whole run overnight, prompts prescribed
git commands the settings denied, the ledger was unreachable from worktrees, the full suite ran
about four times per task and overloaded the host into flaky reverts, owner agents busy-waited, and
defects no gate could see shipped. `/setup-workflow` wrote a snapshot but never proved the delivery
path worked.

## Decision
- Prompts name git capabilities ("the `<capability>` move"); `config.md` maps each to a command,
  and `check-moves.sh` proves the settings allow it.
- Every mechanical step is a script with one last-line result: `ledger.sh`, `run-log.sh`,
  `task-submit.sh`, `merge-task.sh` (gate before commit, merge lock, suite slots, one flake rerun),
  `render-evidence.sh`, `preview.sh`, `halt-log.sh`, `surface-checks.sh`, `preflight.sh`,
  `rehearse.sh`, `load-probe.sh`.
- The orchestrator is the only ledger writer and runs `merge-task.sh` itself; the epic-merger
  agent is retired in owner mode. `--mode workflow` runs each task as one `pad-task` Workflow call.
- A question parks one task, not the run. Tiers pick the gates; the code-writer starts only once
  red is proven. Surfaces and review checkpoints make each capability reachable and seen.
- Setup ends in a rehearsal, repeats as a preflight at every run start, runs as separate
  sub-runs, and records the PAD version (`VERSION` 0.2.0).

## Alternatives rejected
- Keep prompts prescribing raw git commands: each project's settings differ, so they get denied.
- Keep a merger agent between owners and the epic branch: it stalled and was a second place to
  run the same gates.

## Consequences
Runs no longer depend on prose agents getting mechanical steps right, and a broken setup fails
before any agent starts. The full suite grew to ~390 tests and ~7 minutes, which every merge pays.
`preflight.sh` keeps a hand-maintained copy of the config sections, because `install.sh` doesn't
ship `config.example.md`.

## Outcome
All 29 tasks landed on `epic/E1-pad-run-hardening` (head 6850722): full suite 390 passed, lint ok.

Departures from the spec:
- Live outcomes T12 O15, T18 O21/O22 and T26 O42 were not verified. The operator deferred them to
  the PR because no separate live session was available during the run. T18's Workflow entry point
  `({args, agent})` and `agent()` option names were assumed, not checked against the real tool.
- T4 landed without a `Merge E1-T4` commit: its code-writer lost its worktree and committed on the
  epic branch, and the operator accepted it in place. T10's stray red commit was reverted instead.
- `ticket-owner.md` step 8 still tells owners to write the done line that `render-evidence.sh`
  now writes.

The run was built on the previous installed harness, which it did not change. That harness's
failures during the run, recorded in the PR for follow-up: code-writers repeatedly lost their
worktrees; owners stopped and were never woken by their agents' reports; and the test-changed
check misreads a red commit that was merged in rather than fast-forwarded.
