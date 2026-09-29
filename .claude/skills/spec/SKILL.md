---
name: spec
description: Turn an idea into a spec with testable outcomes, by brainstorming together or by grilling the operator. Run as /spec [grill] <idea | ticket key | file>.
argument-hint: "[grill] <idea | ticket key | file>"
disable-model-invocation: true
---

# Idea → spec

Input: `$ARGUMENTS`. If it starts with `grill`, use grill mode; otherwise brainstorm mode. If
it names a ticket or file, read it first. Read `.claude/workflow/config.md` for paths.

The product of this skill is a list of **outcomes**, observable results each provable by a
test (`.claude/workflow/definition-of-done.md`, "An outcome"). Everything else in the spec
exists to make those outcomes right. Don't write code here.

## 1. Size it, and say which size you picked

| Size | Signal | Artifact |
|---|---|---|
| **Small** | Changes a flow that already exists in this repo; one or two outcomes | No spec file. Agree the outcomes in chat, then suggest `/batch-implement` with them |
| **Feature** | New behavior across a few modules, or an interface others use | A spec file, then `/tickets` |
| **Too big** | Several independent subsystems | Split into features first, agree the order, then spec the first one |

When unsure, take the larger size. If hidden complexity shows up later, step up and say so.

## 2. Understand before asking

Read the code, docs and recent commits the idea touches. Never ask the operator something the
repo can answer. If the repo has a glossary (`CONTEXT.md`, written by `/knowledge-layer` when
the config's `## Project knowledge` section is `Mode: on`), use its terms exactly, and say so
when an outcome needs a word the glossary does not have.

## 3. Converge

Ask one question at a time. Use AskUserQuestion when the answer is a choice; lead with your
recommended option.

**Brainstorm mode** (collaborative):
- Clarify purpose, constraints and what success looks like.
- Propose 2–3 approaches with trade-offs, recommend one and say why. Cut features the goal
  doesn't need.
- Present the design in short sections (components and their interfaces, data flow, error
  cases, how each outcome gets tested) and confirm each before the next.

**Grill mode** (adversarial):
- Map the idea as a tree of decisions and walk it depth-first. Resolve each decision before
  opening its children.
- For each decision, ask the hardest question it raises, and give the answer you would pick.
  Push back on vague words ("fast", "robust", "handle errors") until each is a number, a
  behavior or a non-goal.
- Probe the failure paths: what happens when the input is empty, huge or malformed, a
  dependency is down, the run is killed halfway.
- Stop when every leaf is decided or explicitly deferred.

## 4. Write the spec (Feature size)

Save to `.work/specs/<yyyy-mm-dd>-<slug>.md` with `Write`, not a heredoc
(`.claude/workflow/writing-files.md`):

```markdown
# <Title>
Status: draft | approved   ·   Tracker: <epic key, once it exists>

## Problem
Who needs what, and why now. Three sentences at most.

## Outcomes
- [O1] Given …, when …, then …. (level: unit | integration | <resource tag>)

## Non-goals

## Design
Components, the interfaces between them (exact names), data flow, error handling.

## Decisions
- <decision> — because <reason>. Rejected: <alternative> (<why>).

## Risks and unknowns
What could make an outcome wrong, and how the plan finds out early.
```

Check it before showing it:
- no TBD or TODO
- no two sections contradict each other
- every outcome is observable and names its level
- every design element serves an outcome

Then ask the operator to review the file. Iterate until they approve, then set
`Status: approved`.

## 5. Record what should outlive the spec

Working specs are not committed (`spec_commit: ask` in config).
- **Record durable decisions.** If the spec settled a decision a future reader of the code
  would need (an interface, a data format, a trade-off, a rejected approach), write
  `docs/decisions/NNNN-<slug>.md` in the format of `docs/decisions/README.md`. Show it and
  commit it once approved.
- **Ask once about promotion:** "Promote the full spec to `docs/specs/`?" Default no.

## 6. Hand off

Feature size: suggest `/tickets <spec path>`. Small size: list the agreed outcomes and suggest
`/batch-implement` with them.
