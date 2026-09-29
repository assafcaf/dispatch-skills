# PAD

## This repo builds the workflow it runs on

`payload/` is the product: what `install.sh` copies into a project. `.claude/` is an installed
copy of that payload, used to build PAD with its own workflow. Change the workflow in
`payload/`, never in `.claude/`; refresh `.claude/` by re-running `install.sh` only after the
epic that changed the payload has merged, so a run never edits the harness it is running on.

## Delivering work

New work flows through `/spec` (idea → outcomes), `/tickets` (outcomes → tracker tasks) and
`/batch-implement` (tasks → red-then-green, merged code, tracker updated as it goes). The
definition of done is `.claude/workflow/definition-of-done.md`; per-repo settings are in
`.claude/workflow/config.md`. Durable decisions go in `docs/decisions/`.

Keep committed files machine-neutral: no absolute paths, no one OS's shell. Host-specific facts
go in your own gitignored `CLAUDE.local.md`.
