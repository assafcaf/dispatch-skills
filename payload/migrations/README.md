# Migration notes

A note is a change to an installed project that copying files cannot make: a config section
renamed, a permission rule the harness now needs, a moved path, a file the project owns that
must change shape. `/pad-update` runs the notes a project has not handled yet, in number order,
after it has updated the files.

Add a note in the same commit as the change that needs it. Most pushes need none.

## Format

`payload/migrations/NNNN-<slug>.md`, numbered from `0001` with no gaps:

```markdown
# NNNN — <what changes, in one line>

Applies when: <a condition the agent can check in the project; "always" if there is none>

## Steps

<what to do, in the project's worktree. Name files and sections, not line numbers.>

## Check

<one command, and the result that means the note is done>
```

## Rules

- **A released note is never edited or renumbered.** Projects record the highest number they
  have handled in `.claude/workflow/pad.lock`; a note changed afterwards is never run again. To
  correct one, add another.
- **A note must be safe to run where it does not apply.** "Applies when" false means skipped,
  not failed.
- **A note never writes `.claude/settings.json`.** Permission rules are the operator's: say
  which rule is needed, and `/pad-update` puts it in the pull request.
- **Keep project facts out.** A note names PAD's files and config sections, never one project's
  values.
- Files under `payload/claude/` need no note: the updater replaces, merges, adds and deletes
  them by itself.
