# Agent memory

The agents `/batch-implement` runs have a persistent memory: `memory: project` in their
frontmatter. Each one has `.claude/agent-memory/<agent name>/MEMORY.md`, which Claude Code loads
into the agent's context every time it starts (the first 200 lines). It lives in the main
checkout even when the agent works in a worktree, and it is committed, so every run and every
machine inherits it.

Its purpose is narrow: **an agent that hit a wall once should not hit it again.** A command that
is denied here, a tool that can't do what it looks like it can, a gate that fails for a
non-obvious reason — and the way that works instead.

## When to write a line

Only after something **failed or blocked you**, **you found what works**, and **the next run of
you would hit it again**. All three.

Not:
- a fact about one task (a prop name, a ticket's quirk) — it's wrong for the next task;
- anything your agent file, `config.md`, `CLAUDE.md` or `project.md` already says;
- a guess, a preference, or something that went fine;
- a fact about the product's code (an invariant, a domain rule): that belongs in
  `project.md`, which the operator writes. Put it in your report's `NOTES` instead.

## How to write it

One line, under about 200 characters, in this shape:

```
- <do this / don't do that, with what works instead> — <why, one clause> (<task key>, <yyyy-mm-dd>)
```

For example:

```
- Branch with `git worktree add`, not `git checkout -b`: checkout is denied in settings.json (E5-T3, 2026-09-23)
```

1. Read `MEMORY.md` first. If a line already covers it, correct that line instead of adding one.
2. Change the file with `Edit` only, never `Write`. Agents of the same kind run in parallel and
   share this file. If someone changed it since you read it, `Edit` fails and you re-read;
   `Write` would silently drop their line.
3. At most two lines per task. Keep everything in `MEMORY.md`, with no extra files, so the
   whole memory loads and the curator sees all of it.

## Who keeps it clean

Each agent owns its own memory. At the end of every epic, `/batch-implement` runs the
`memory-curator`, which keeps, tightens, merges or deletes lines against the rules above, and
never adds new ones. It commits the result on the epic branch, so its changes show in the epic's
PR.
