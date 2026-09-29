# project.md format

`.claude/workflow/project.md`, committed. What an agent needs to know about this repo that it
cannot work out by reading it.

`config.md` holds the settings a run executes. This file holds the things a run would otherwise
get wrong.

## Shape

```markdown
# <Project>: working notes

Mode: on   ·   Last scanned: <yyyy-mm-dd>

## What this repo is
<Two or three sentences. What it is for, who uses it, what it is not.>

## Module map
| Path | Owns |
|---|---|
| `src/ordering/` | Order intake and the state machine from submitted to fulfilled |
| `src/billing/` | Invoice generation and dunning |

## Commands
The gates live in `config.md`'s Commands table. Only what that table cannot say goes here.
- `src/ml/` tests need the fixtures built first: `make fixtures`

## Invariants
- Every write to the ledger goes through `append()`. Direct writes bypass the checksum.

## Standing overlaps
Files that most tasks touch, so `/tickets` and `task-planner` watch them for real conflicts and
put shared wiring in them into one task. Touching one is not by itself a blocking edge.
| Path | Recent commits touching it |
|---|---|
| `db/schema.sql` | 19 of the last 40 |

## Pitfalls
- The dev server caches the schema at boot. A migration needs a restart, not a reload.
```

## Sections, and who writes each

| Section | Written by | Carries |
|---|---|---|
| What this repo is | operator | purpose, users, non-goals |
| Module map | scanner | one row per module, each with a path |
| Commands | scanner | only what `config.md`'s table cannot express |
| Invariants | operator | what must hold, and breaks quietly when it does not |
| Standing overlaps | scanner | path plus the commit count that earned it |
| Pitfalls | operator | what a new contributor gets wrong here |

**The operator's three sections may not be written by an agent.** A context file written by a
model measured worse than no file at all (arXiv 2602.11988: -0.5% on SWE-bench Lite, -2% on
AGENTbench); one written by the repo's own developers measured +4%. An invariant is exactly the
kind of claim a model writes fluently and wrongly, and a wrong invariant is obeyed rather than
ignored: the same study found agents follow context files faithfully, reading and testing more,
without succeeding more.

The scanner's three sections are safe to generate because every row carries a path that either
resolves or fails the gate.

## Rules

- **The inference test.** Before a line goes in: could an agent learn this by reading the repo?
  If yes, cut it. "The tests are in `tests/`" is not knowledge.
- **Never duplicate `config.md`.** The Commands section cross-references it. Two copies of a
  test command drift, and the copy an agent happens to read is the one that breaks the run.
- **No decisions.** `docs/decisions/` owns those. Link, do not restate.
- **Name the cost.** A pitfall that does not say what goes wrong is a rule nobody can apply.

## Ceiling

120 lines. `bin/knowledge-paths.sh` fails the file above it.

Under 150 lines is the working consensus for a repository context file, and the cost of
exceeding it is measured rather than aesthetic: context files add over 20% to inference cost per
task (arXiv 2602.11988), charged on every task whether the file earned it or not.

## Growing it

Add a line when an agent got something wrong that this file would have prevented. Delete a line
when the convention changes. `/batch-implement` runs `/knowledge-layer refresh` at the end of an
epic for exactly this: it adds a term two tasks used that the glossary lacks and a file every
task touched that is not a standing overlap, and puts a blocker whose answer was already an
invariant in the PR body for you.

That loop is the part with evidence behind it. Guidance tuned against observed agent failures
outperforms one-shot generation (arXiv 2606.20512); a file that is written once and never
corrected is the arm that measured negative.
