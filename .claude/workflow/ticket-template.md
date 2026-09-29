# Task ticket body

`/tickets` writes every task in this shape, and `/batch-implement` parses it. Keep the headings exactly.

```markdown
## Goal
One sentence: what a user of the code can do after this task that they couldn't before.

## Outcomes
- [O1] Given <state>, when <action>, then <observable result>. (level: unit | integration | <resource tag>)
- [O2] ...

## Tier
small | standard | complex — one word, then one line saying why.

## Files
Likely touched, one per line. Mark an edit that rewrites existing code (not just adds to it)
with `(rewrites <what>)`: that is what the planner checks for real conflicts.
- `path/to/module.py`
- `tests/test_module.py`

## Interfaces
- Consumes: exact names and signatures this task uses from earlier tasks.
- Produces: exact names and signatures later tasks rely on.

## Blocked by
Task keys, or "none". Only tasks whose output this one uses — a name, a behaviour, data.
Sharing a file is not a reason.

## Out of scope
What a reasonable implementer might add but must not.

## Spec
Path to the spec (and to its decision record, if one exists).
```

Sizing: one implementer session. As a rule of thumb, at most 3 outcomes and about 5 files.
Split anything larger along its outcomes, not along technical layers.

## Tiers

The tier sets how much process a task gets. Each step costs minutes, and a small change
should not pay for a large one's safeguards.

| Tier | When | How `/batch-implement` runs it |
|---|---|---|
| `small` | One outcome (two at most), about 1–3 files, extends a pattern the code already has — a field, a prop, a rule, a copy change — and produces no interface another task consumes | One `code-writer` in solo mode writes the red commit, then the green one. Red is still proven by `verify-red.sh`, and the merger still checks that no test was weakened. The ticket moves only to doing and to done |
| `standard` | The default: one to three outcomes, a new module or behaviour that follows known patterns | A `test-designer` writes the red commit, and a separate `code-writer` makes it pass |
| `complex` | Design judgment across modules, a new interface other tasks consume, persistence or migration, concurrency, or a serial resource | As `standard`, on the stronger models and with a wider reading brief |

When unsure between two tiers, take the larger. The models per tier are in `config.md`.
