<!-- Offered by /setup-workflow for this repo's CLAUDE.md. Paste what you want; drop the rest. -->

## Delivering work

New work flows through `/spec` (idea → outcomes), `/tickets` (outcomes → tracker tasks) and
`/batch-implement` (tasks → red-then-green, merged code, tracker updated as it goes). The
definition of done is `.claude/workflow/definition-of-done.md`; per-repo settings are in
`.claude/workflow/config.md`. Durable decisions go in `docs/decisions/`.

Keep committed files machine-neutral: no absolute paths, no one OS's shell. Host-specific facts
go in your own gitignored `CLAUDE.local.md`.

## Writing

Applies to replies, commit messages, PR bodies, tickets and docs alike.

- Lead with the result. No preamble, no restating the question, no closing summary of what you
  just said.
- Say the thing once. If a sentence survives deletion without loss, delete it.
- Facts carry the claim: the command, the number, the `file:line`. "Robust", "comprehensive",
  "significantly improved" carry none.
- Say plainly what you did not do, did not run, or could not check.
- Cut the tells: "It's not just X, it's Y", "Let's dive in", "Here's the thing", three-item
  flourishes, a bold adjective per bullet, and an em dash where a full stop works.
- Prose for reasoning, a table for more than three parallel facts. Not both for the same
  content.
