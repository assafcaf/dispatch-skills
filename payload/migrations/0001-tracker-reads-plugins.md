# 0001 — The tracker reads project plugins

Applies when: `.claude/agents/tracker.md` has no `**Plugins.**` paragraph.

## Steps

`.claude/agents/tracker.md` is the project's own file, so `/pad-update` does not change it.

1. In `.claude/agents/tracker.md`, after the paragraph that ends "comes from there.", add the
   `**Plugins.**` paragraph from PAD's `payload/claude/agents/tracker.md`, unchanged.
2. In its Request block, add the line `    | <an operation a listed plugin adds>` under the
   `OP:` line.
3. If the tracker body holds operations or rules that only this project uses, move them into a
   plugin under `.claude/pad-plugins/` (`.claude/workflow/plugins.md`) and list it in the
   config's `## Plugins` table. If that plugin runs scripts, add `Bash` to the tracker's
   `tools:` and name, in the pull request, the allow rules its `## Scripts` section lists.
4. Run `/setup-workflow upgrade` to add the `## Plugins` section to `config.md`.

## Check

`grep -c '\*\*Plugins\.\*\*' .claude/agents/tracker.md` prints `1`, and
`bash .claude/workflow/bin/preflight.sh` reports no `version` or `plugins` failure.
