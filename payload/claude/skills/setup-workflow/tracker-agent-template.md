# Template: `.claude/agents/tracker.md`

Copy to `.claude/agents/tracker.md`, replacing `<…>`. Keep the body as it is: the operations,
rules and response format are what `/tickets`, `/batch-implement` and `ticket-owner` expect. Per-project values
(cloud id, project key, issue types, statuses, transition ids, link type, label) live in
`.claude/workflow/config.md`, so this file stays stable when they change.

Tools by adapter. Only the ledger's tools: the operations in the adapter file, nothing else
from the same server. The `atlassian` server also carries Confluence; a project that writes
pages gives those tools to an agent of its own, so every ledger call doesn't load them and the
ledger keeper can't write pages.

| Adapter | `tools:` |
|---|---|
| jira | `Read, mcp__atlassian__getJiraIssue, mcp__atlassian__searchJiraIssuesUsingJql, mcp__atlassian__createJiraIssue, mcp__atlassian__editJiraIssue, mcp__atlassian__createIssueLink, mcp__atlassian__getTransitionsForJiraIssue, mcp__atlassian__transitionJiraIssue, mcp__atlassian__addCommentToJiraIssue` |
| github | `Read, Bash` |
| local | `Read, Edit, Write, Glob` |

```markdown
---
name: tracker
description: Performs every read and write against the project's issue tracker (the ledger) for /tickets and /batch-implement. Owns the tracker's tools and metadata so no other agent needs them.
tools: <per the table above>
model: haiku
memory: project
---

<the body of .claude/agents/tracker.md, unchanged, with the adapter named in the first paragraph>
```
