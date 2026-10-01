---
name: pad-update
description: Bring this repo's installed PAD harness up to the latest PAD - fetch PAD, update the skills, agents and workflow files while keeping this project's edits, run the migration notes PAD ships, bring the config up to date, prove the harness, and open a pull request.
argument-hint: "[<PAD ref>]"
disable-model-invocation: true
---

# Update the PAD harness here

Input: `$ARGUMENTS` is the PAD commit, tag or branch to update to; with none, PAD's default
branch. The update lands on a branch and a pull request; the main checkout's files do not
change. Nothing in this skill creates a ticket or changes product code.

`.claude/workflow/pad.lock` records where the installed harness came from:

```
source: <PAD's clone URL>
commit: <the PAD commit the files came from>
version: <PAD's VERSION at that commit>
migration: <the highest migration note already handled>
```

`bin/pad-update.sh` does the file work and prints one line per file; its header describes every
line. Quote its lines in the report rather than paraphrasing them.

## 1. Check the ground

Stop, and say which, when either is true:

- `git status --porcelain -- .claude` prints anything in the main checkout: the update would be
  cut from a harness that is not committed.
- a `/batch-implement` run is in progress (a run log under the config's run-log path with no
  closing entry, or a live epic worktree an agent is writing in): a run must not have its
  harness changed under it.

## 2. Fetch PAD

Clone PAD, with its history, into a new temporary directory outside the repo: the lock's
`source:`, or `https://github.com/assafcaf/pad` when there is no lock. Every later step runs
**the clone's** `payload/claude/workflow/bin/pad-update.sh`, never the copy installed here: the
installed copy is the old updater.

The target is `$ARGUMENTS`, or the clone's `HEAD`. If the lock's `commit:` is the target, say
the harness is current and stop.

**No lock.** A harness installed before `/pad-update` existed has none. Run the clone's
`pad-update.sh --find-base --project <main checkout>`:

- `BASE <sha> <matched>/<files>`: show the operator the commit's subject and date and the
  score, and ask them to confirm it as the base. Pass it as `--base <sha>` in step 4.
- `BASE NONE ...`: too little matches to guess. Ask the operator for the PAD commit the harness
  was installed from, and stop if they do not know.

## 3. Say what is coming

Print PAD's commit subjects from the base to the target (`git log --oneline <base>..<target>`
in the clone) and the output of `pad-update.sh --dry-run`. Do not ask for approval: the pull
request is the review.

## 4. Update on a branch

Make a worktree on a new branch `pad-update/<target short sha>` from the main checkout's
`HEAD`, with the config's `branch-from-epic-head` Git move, under `.claude/worktrees/`. Run the
updater against it:

```bash
bash <clone>/payload/claude/workflow/bin/pad-update.sh --project <worktree> --to <target> [--base <sha>]
```

Its last line is `UPDATE OK` or `UPDATE CONFLICTS <n>`.

## 5. Rule on each conflict

For every `CONFLICT` line, read three versions: PAD at the base and at the target
(`git show <sha>:payload/claude/<path>` in the clone) and this project's.

- **Markers left in the file.** Work out what this project changed and why (the commit that
  changed it, the config, the decision records) and what PAD changed. When both can hold, write
  the file that has both and remove the markers. When they contradict, show the operator the
  two changes and ask which stands.
- **Deleted upstream, changed here.** Always ask: delete it, or keep it as this project's own.

A `GONE` line is not a conflict, and the updater leaves the file out. Name each one to the
operator all the same: a file missing by accident (an install that predates it, a sync done by
hand) is restored from the clone with `git show <target>:payload/claude/<path>`; one removed on
purpose stays removed.

No file may keep a conflict marker: `grep -rn '^<<<<<<< \|^>>>>>>> ' .claude` must print
nothing before step 6.

## 6. Run the migration notes

Each `MIGRATION <path>` line names a note in the clone, in order. A note is a change that
copying files cannot make; `payload/migrations/README.md` in the clone gives the format. For
each, in the worktree:

1. Read **Applies when**. If it is not true here, record the note as skipped and go on.
2. Follow **Steps**.
3. Run **Check**. If it fails, stop: keep the worktree, report the note and the failure, and do
   not go on to the next note.

A note that changes `.claude/settings.json` is never applied by you: put the rule it asks for
in the pull request body, for the operator. The same goes for a `SETTINGS` line from the
updater: diff `payload/claude/settings.example.json` between base and target in the clone, and
list the rules that are new.

## 7. Bring the config up to date

Run `/setup-workflow`'s **7f. Upgrade** step in the worktree: add the sections `config.md`
lacks, set its `PAD version:` line.

## 8. Commit, then prove it

Commit everything changed under `.claude/` in the worktree as
`Update the harness to PAD <target short sha>`. A script that is new must be executable in the
index: `git ls-files -s .claude/workflow/bin` must show `100755` for every `.sh`; fix one that
is not with `git update-index --chmod=+x <path>`. The rehearsal needs the work committed, so
the commit comes first. Then, in the worktree:

- `bash .claude/workflow/bin/preflight.sh` must pass.
- `bash .claude/workflow/bin/rehearse.sh` must end `REHEARSAL OK`.

A failure here is the update's to fix when the cause is the harness (a missed migration, an
unresolved merge). When the cause is the machine or the project (a permission rule, a dead
preview command), report it and leave the fix to the operator. Either way the lock is not
written until both pass. Commit any fix.

## 9. Record, and open the pull request

1. Write the lock: `bash <clone>/payload/claude/workflow/bin/pad-update.sh --record --project <worktree> --to <target>`,
   and commit it as `Record PAD <target short sha> in pad.lock`.
2. Push the branch and open a pull request against the default branch. Its body:
   - base and target commits, and PAD's commit subjects between them;
   - the updater's lines, grouped: replaced, merged, added, deleted, kept, gone;
   - each conflict and how it was ruled;
   - each migration note: applied, or skipped and why;
   - what is left for the operator: settings rules to add, anything a check reported.

## 10. Clean up and report

Remove the temporary clone. Leave the worktree until the pull request merges. Report the pull
request URL, the counts from the updater's `SUMMARY` line, and what the operator must do.

## When it stops part-way

Anything that fails after step 4 leaves the branch and worktree in place and the lock
unwritten, and the report names the step. Running `/pad-update` again starts from the same
base, so a half-done update is never recorded as done. Remove the leftover worktree and branch
first, or continue in them.
