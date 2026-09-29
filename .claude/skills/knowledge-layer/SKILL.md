---
name: knowledge-layer
description: Build or refresh this repo's knowledge layer - a glossary the whole workflow shares, and the working notes an agent cannot infer from the code. Scans for what can be cited, asks you for what cannot. Run as /knowledge-layer at any point in a project's life.
argument-hint: "[refresh]"
disable-model-invocation: true
---

# Repo → knowledge layer

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md`.

Two files, and nothing else:

| File | Is | Format |
|---|---|---|
| `CONTEXT.md` | the glossary, at the repo root | [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md) |
| `.claude/workflow/project.md` | what an agent cannot infer by reading the repo | [PROJECT-FORMAT.md](PROJECT-FORMAT.md) |

The mode is optional and off by default. With it off, every skill and agent behaves exactly as
it did before this skill existed. You can turn it on here at any time, and you do not have to
be running `/setup-workflow` to do it.

## The split that makes this work

You scan for what carries a path. You ask the operator for what does not.

A repository context file written by a model measured **worse than no file at all**
(arXiv 2602.11988: -0.5% on SWE-bench Lite, -2% on AGENTbench, and over 20% added inference
cost). One written by the repo's own developers measured **+4%**. Agents follow a bad context
file rather than ignoring it: the same traces show more files read and more tests run, without
more tasks solved.

So a module path, a declared command and a commit count are yours to write, because each one
resolves or fails `bin/knowledge-paths.sh`. Purpose, invariants and pitfalls are the operator's
words, taken down as given. Never write those three yourself, and never smooth them.

## Entry state

Check `config.md` for a `## Project knowledge` section, then check the two files.

| Section | Files | Run |
|---|---|---|
| absent, or `Mode: off` | either | **Enable** |
| `Mode: on` | both present | **Refresh** |
| `Mode: on` | one or both missing | **Repair** |

`refresh` in `$ARGUMENTS` forces Refresh. Say which one you picked before you start.

## Enable

### 1. Explore

Enough to choose the areas, no more. You are not reading the codebase here; the scanners are.

- Top-level directories, and which have their own tests
- Manifests: `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Makefile`
- Hot spots: `git log --name-only --pretty=format: -n 200 | sort | uniq -c | sort -rn | head -30`
- What already exists: `CLAUDE.md`, `CONTEXT.md`, `docs/decisions/`, `README.md`

### 2. Scan

Dispatch one `knowledge-scanner` per area, **all in one message**, so they run in parallel. An
area is a top-level module, or the repo root for a small repo. Three to six is the usual range;
more areas than that means the areas are too small.

Each returns one block. **Read only the blocks.** Do not open the files yourself: the point of
the fan-out is that the survey's cost stays in the scanners, and a coordinator that reads
source alongside them has paid for the scan twice and still has a full context window of code.
`/batch-implement` keeps `task-planner` at the same arm's length, for the same reason.

Merge the blocks: modules in path order, commands deduplicated, overlaps by descending count,
terms with their `ambiguous` flags kept.

### 3. Grill

Now ask, one question at a time, in the operator's own words. Same discipline as `/spec`'s
grill mode: push back on a vague answer until it is a behavior, a number or a non-goal.

| Section | Ask |
|---|---|
| What this repo is | "What is this for, and who uses it? What is it deliberately not?" |
| Invariants | "What has to stay true that a passing test suite would not catch?" |
| Pitfalls | "What does a new contributor here always get wrong?" |
| Ambiguous terms | For each term the scanners flagged: "`<term>` is used for both `<a>` and `<b>`. Which is it, and what do we call the other?" |

Take the answer as given. Where an answer contradicts what a scanner found, say so and let the
operator settle it: `"You said every write goes through append(), but src/ledger/bulk.py:40
writes directly. Which is true?"` That contradiction is the most valuable thing this skill
produces, and it only surfaces because the two halves came from different places.

An operator who has nothing to say for a section leaves it out. An empty section is honest; an
invented one measured negative.

### 4. Confirm

Show both files in full. The operator edits before anything is written. Say which lines came
from a scanner and which are theirs.

### 5. Write

1. `CONTEXT.md` and `.claude/workflow/project.md`, in their formats. Both with `Write`, and
   any later correction with `Edit` — never a heredoc or `sed`
   (`.claude/workflow/writing-files.md`).
2. The `## Project knowledge` section in `.claude/workflow/config.md`: set `Mode: on`, drop
   the off paragraph, and write this table under it. Add the whole section if the file
   predates this skill.

   | Reader | Reads |
   |---|---|
   | `/spec` | `CONTEXT.md`, so outcomes are written in this project's terms |
   | `/tickets` | `project.md` Module map, for each task's Files and Interfaces |
   | `task-planner` | `project.md` Module map and Standing overlaps, before computing waves |
   | `test-designer` | `CONTEXT.md`, so test names use the project's words |
   | `code-writer` | `CONTEXT.md`, plus `project.md` Invariants and Pitfalls |

   Nothing else reads them. A reader not in this table is a reader paying for context it was
   not given a use for.
3. `bash .claude/workflow/bin/knowledge-paths.sh`. It must pass before you report done.
4. Tell the operator that `/spec`, `/tickets`, `/batch-implement` and the implementer agents
   now read these, and that `/knowledge-layer refresh` re-scans.

## Refresh

Re-run Explore and Scan. Then show a diff, and change nothing until the operator approves it:

```
+ term   Dunning        src/billing/dunning.py, 4 uses
- term   Voucher        no longer appears in the code
! module src/webhooks/  not in the module map
! path   src/legacy/    in the module map, no longer exists
+ overlap db/schema.sql 19 of the last 40 commits
```

**Never rewrite What this repo is, Invariants or Pitfalls.** Show them unchanged, and ask
whether they still hold. A refresh that quietly reworded an invariant has replaced the
operator's knowledge with a model's, which is the failure this whole skill is shaped around.

## Repair

The switch says `on` and a file is missing. Report which, and offer: restore from the last
commit that had it (`git log --oneline -- <path>`), or re-enable from scratch. Do not
silently regenerate: a file deleted on purpose is a decision.

## This skill never writes decisions

`docs/decisions/` is the committed development record, owned by `/spec` and `/batch-implement`
(`docs/decisions/README.md`). Read it, link to it from a term, and leave it alone. A decision
inferred from a scan is a record of a decision nobody made.

## Rationalizations

| Excuse | Reality |
|---|---|
| "The operator is busy, I'll draft the invariants and let them correct it" | Drafted-then-skimmed is the arm that measured -2%. Ask, or leave the section out |
| "I'll read a few source files to check the scanner's work" | Then you have paid for the scan twice. Ask the scanner |
| "More terms make the glossary more useful" | Every term is charged on every task. A term that fails the inference test costs and teaches nothing |
| "This decision is obvious from the code, I'll record it" | `docs/decisions/` is not yours. `/spec` writes it when a decision is actually made |
| "The file is 140 lines but it's all good content" | The gate fails at 120. Under 150 lines is where context files stop being read and start being skimmed |
