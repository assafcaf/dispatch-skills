# Definition of done

Done is a list of outcomes met, each shown by a test. Nobody's opinion of the code enters into
it. Every item below is checked mechanically by `/batch-implement` and its agents; commands come from `config.md`.

## An outcome

An outcome is one observable result at a boundary someone outside the code cares about: a
response, a file on disk, an exit code, a record in the manifest, an error the caller sees.

- Written as "Given <state>, when <action>, then <observable result>".
- Names its test level: `unit`, `integration` (real components, host-runnable), or a serial
  resource tag from `config.md`.
- Testable by one or more tests whose names say the outcome.

"Refactor X", "add a helper" and "improve logging" are not outcomes. They are means, and
belong inside a task whose outcome needs them.

## A task is done when

1. **Every outcome has a test**, written before the code that satisfies it, and the reports
   map each outcome to its test ids.
2. **Red was proven.** The task's first commit adds only the tests and the stubs they need
   to run. `.claude/workflow/bin/verify-red.sh` shows those tests failing at that commit, with
   the configured red exit code. Outcomes on a serial resource are proven green there instead
   (item 4), since they can't run on the host.
3. **Green on the epic branch.** After merging, the outcome tests pass, the full suite passes
   and lint is clean.
4. **Serial-resource outcomes passed** where their resource lives, run by the orchestrator at
   the merged commit, with the output kept in the run log.
5. **Nothing was weakened.** No commit after the red commit changed a test file, and the
   task's diff adds no `skip`, `xfail` or disabled test, deletes no existing test, and leaves
   no `TODO` in code it adds (`.claude/workflow/bin/weakened-tests.sh`).
6. **The tracker says so.** Status moves to done, with a comment naming the merge commit
   (pushed), the red commit, the commands run and their results.

A task that touched files outside its declared list is still done if 1–6 hold. Its ticket
owner records the extra files in the run log and the tracker comment, so the PR reader
sees them.

## An epic is done when

1. Every task is done.
2. The full suite and lint pass at the epic branch head.
3. The development record (`docs/decisions/`) has an Outcome section for this epic: what was
   built, what changed from the spec, and why.
4. The epic branch is pushed and a draft PR is open, linking the epic.
5. The epic is in the review status, and the run's rulings are listed in the PR body.
