# 0003. A project extends PAD's agents through listed plugin files, never by editing them

Date: 2026-10-08 · Status: accepted · Tracker: none

## Context
A project using the Jira adapter needed the tracker to download and upload ticket attachments.
The `atlassian` MCP tools list attachments but cannot move their bytes, so the operation runs a
project script against Jira's REST API. Written into the project's `tracker.md`, that text is
one project's knowledge in a PAD-shaped file, and the next project rediscovers it. Every
project-specific edit to a PAD file is also a merge `/pad-update` has to keep or flag.

## Decision
A project-specific addition is a plugin: one file under `.claude/pad-plugins/`, owned by the
project and never shipped or touched by PAD, listed in the config's `## Plugins` table with the
agent or skill it `Extends`. The format and rules are `workflow/plugins.md`. A plugin adds
operations and never overrides one; it names every script it runs and the allow rule each
needs, and the operator adds those rules. `preflight.sh`'s `plugins` check fails when a listed
file is missing or extends no agent or skill. The tracker is the first reader: it reads the
plugins that extend it, and gets `Bash` only when one of them runs scripts. Migration `0001`
brings an installed `tracker.md` up to this.

## Alternatives rejected
- Operations written into the project's `tracker.md`: invisible to PAD's upgrades and to other
  projects, and it grows the one file each project must hand-merge.
- Attachment operations in PAD's `trackers/jira.md`: they need a script, credentials and allow
  rules that are the project's; most projects never use them.
- Claude Code plugins (`/plugin`): they package skills and agents for distribution, not an
  addition to one PAD agent that the config lists and preflight checks.

## Consequences
- An agent or skill honours plugins only once its own text says so; `plugins.md` lists which
  do. Adding a reader is a PAD change.
- An agent's `tools:` cannot grow at run time, so a plugin that runs scripts means `Bash` in that
  agent's frontmatter. Its prompt limits `Bash` to the scripts its plugins name.

## Outcome
