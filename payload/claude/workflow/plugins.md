# Plugins

A plugin is how a project adds behavior to a PAD agent or skill without editing it. PAD's files
stay generic and `/pad-update` keeps replacing them; what only one project needs (an extra
tracker operation, a script against its tracker's REST API) lives in a plugin the project owns.

## Where plugins live

One Markdown file per plugin, at `.claude/pad-plugins/<name>.md`, committed. PAD ships nothing
under `.claude/pad-plugins/`, so `/pad-update` never touches it. A plugin is in force only when
the config's `## Plugins` table lists it:

```markdown
| Plugin | Extends | Adds |
|---|---|---|
| `.claude/pad-plugins/<name>.md` | `<agent or skill>` | <one line: what it adds> |
```

`Extends` names one agent in `.claude/agents/` or one skill in `.claude/skills/`. `preflight.sh`
fails when a listed plugin file is missing or names neither.

## What a plugin file holds

```markdown
# Plugin: <name>

Extends: `<agent or skill>`

## Adds
The operations, request fields or steps it adds, in the format the extended agent or skill
already uses.

## How
How to carry out each addition: the tool call or the script command.

## Scripts
Every script it runs, repo-relative, and the `.claude/settings.json` allow rule each needs.
Omit the section when it runs none.

## Failures
What each failure means and what to report.
```

## Rules

- **Add, never override.** A plugin adds operations or steps. It cannot change an existing
  one's behavior or relax a rule of the agent or skill it extends.
- **Scripts are named, not open-ended.** An agent runs only the scripts its plugins list. An
  agent that gets `Bash` for a plugin uses it for nothing else.
- **Permissions are the operator's.** A plugin names the allow rules its scripts need; the
  operator adds them to `.claude/settings.json`. Prefer allowing read and add operations and
  leaving destructive ones to prompt.
- **Secrets stay out.** A plugin that needs credentials reads them from a gitignored file each
  person creates from a committed example. It never asks for, prints or writes one.

## Which agents and skills read plugins

| Extends | Reads plugins at | Tools |
|---|---|---|
| `tracker` | start, after the config's Tracker section and the adapter | add `Bash` to its `tools:` when a listed plugin has a `## Scripts` section |
