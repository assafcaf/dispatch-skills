# CONTEXT.md format

The repo's glossary, at the repo root, committed. One term, one meaning, chosen on purpose.

Adapted from mattpocock/skills `skills/engineering/domain-modeling/CONTEXT-FORMAT.md`
(MIT, (c) 2026 Matt Pocock). See NOTICE.

## Shape

```markdown
# <Project>

<One or two sentences: what this project is, in its own words.>

## Language

**Order**:
A customer's request for goods, from submission until it is fulfilled or cancelled.
_Avoid_: Purchase, transaction

**Invoice**:
A request for payment sent after delivery. Settles against one Order.
_Avoid_: Bill, payment request
```

One to two sentences per term. Define what it **is**, not what it does. Where several words
compete for one concept, pick one and list the losers under `_Avoid_`, so every agent and every
test name uses the same word.

## Rules

- **Be opinionated.** A glossary that lists synonyms without choosing between them has not done
  its job. `_Avoid_` is the half that changes behavior.
- **Project terms only.** Before adding a term, ask whether it is a concept unique to this
  project or a general programming concept. "Idempotent", "middleware", "worktree" and "retry"
  are general, however much this repo uses them. Only the former belongs.
- **The inference test.** Cut any term the next agent could learn by reading the repo. A
  glossary is not a tour of the codebase.
- **No implementation detail.** Not a spec, not a scratch pad, not a design record. A term's
  entry says what the word means, never which module implements it or how. When you catch
  yourself writing a file path into a definition, the sentence belongs somewhere else.
- **Link a decision, never restate it.** Where a term exists because of a decision, point at
  it: `See docs/decisions/0007-orders-are-event-sourced.md`. One line, no summary.

## What this file never contains

Decisions. `docs/decisions/` is the committed development record, written by `/spec` when a
spec settles something durable and appended by `/batch-implement` when an epic lands
(`docs/decisions/README.md`). `/knowledge-layer` reads it and links into it. It writes nothing
there, ever: a decision inferred from a scan is a record of a decision nobody made.

## Ceiling

100 lines. `bin/knowledge-paths.sh` fails the file above it.

The ceiling is not tidiness. Context files cost over 20% more tokens per task
(arXiv 2602.11988) and that is paid on every task whether the file earns it or not. A glossary
that grows to cover everything stops being read closely and starts being skimmed, which is the
condition the measurement was taken under.

## Where terms come from

| Section | Written by |
|---|---|
| The term and its definition | the operator, in the grilling step |
| The candidate list, and which terms are used two ways | `knowledge-scanner`, from the code |

A scanner proposes; it never writes a definition. The word a team uses for a concept, and
which competing word loses, is not recoverable from source code.
