# Template: `.claude/agents/tracker.md`

Copy to `.claude/agents/tracker.md`, replacing `<…>`. Keep the body as it is: the operations,
rules and response format are what `/tickets`, `/batch-implement` and `ticket-owner` expect. Per-project values
(cloud id, project key, issue types, statuses, transition ids, link type, label) live in
`.claude/workflow/config.md`, so this file stays stable when they change.

Tools by adapter:

| Adapter | `tools:` |
|---|---|
| jira | `Read, mcp__atlassian` |
| github | `Read, Bash` |
| local | `Read, Edit, Write, Glob` |

```markdown
---
name: tracker
description: Performs every read and write against the project's issue tracker (the ledger) for /tickets, /batch-implement and its ticket owners. Owns the tracker's tools and metadata so no other agent needs them.
tools: <per the table above>
model: haiku
memory: project
---

<the body of .claude/agents/tracker.md, unchanged, with the adapter named in the first paragraph>
```
