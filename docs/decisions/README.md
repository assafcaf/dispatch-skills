# Development record

Why the code is the way it is, one decision at a time. Working specs are not committed. What
outlives them is here: the decisions a future reader of the code would otherwise have to
reverse-engineer, and what each epic actually delivered.

`/spec` writes an entry when a spec settles a durable decision, and `/batch-implement` appends the Outcome
when the epic lands. Add one by hand whenever you make such a decision outside that flow.

## Format

`NNNN-<slug>.md`, numbered in order and never renumbered. Keep each under a page.

```markdown
# NNNN. <Decision, stated as a sentence>

Date: yyyy-mm-dd · Status: accepted | superseded by NNNN · Tracker: <epic key>

## Context
What forced a decision. Facts, not the whole spec.

## Decision
What we chose, precisely enough to check the code against.

## Alternatives rejected
- <alternative>: <why not>

## Consequences
What this makes easy, what it makes hard, what to watch for.

## Outcome
Added when the work lands: what was built (PR link), and where it departed from the decision
above, and why.
```

To change a decision, write a new entry and mark the old one `superseded by NNNN`. Don't
rewrite history.

## Entries

- [0001](0001-lean-agent-harness.md): a lean agent harness, with outcome-tested parallel delivery
