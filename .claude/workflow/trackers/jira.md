# Tracker adapter: Jira

Through the `atlassian` MCP server. Every call takes `cloudId` from `config.md`. Bodies are
Markdown (`contentFormat: markdown` / `responseContentFormat: markdown`). If the tools are not
available in the session, say so and stop; do not fall back to another tracker.

| Operation | How |
|---|---|
| Read one | `getJiraIssue` with `fields: [summary, description, status, issuetype, parent, issuelinks, labels]` |
| List an epic's tasks | `searchJiraIssuesUsingJql`, `jql: parent = <EPIC> ORDER BY created ASC` |
| Find existing by label | `jql: project = <PROJECT> AND labels = <label> AND summary ~ "<text>"` |
| Create epic | `createJiraIssue` with `projectKey`, `issueTypeName: <epic type>`, `summary`, `description`, `contentFormat: markdown`, `additional_fields: {"labels": [<label>]}` |
| Create task | same, with `issueTypeName: <task type>`, `parent: <EPIC>` and the ticket body as `description`. In a team-managed project `parent` takes the epic key for a Task; a company-managed one may use an Epic Link field instead — `/setup-workflow` checks which |
| Blocked-by edge | `createIssueLink`, `type: Blocks`, **`inwardIssue`: the blocker**, **`outwardIssue`: the blocked task** |
| Read blocked-by | in `issuelinks`, entries of type `Blocks` that carry an `inwardIssue` are this task's blockers |
| Update a ticket | `editJiraIssue` with `fields: {"description": <BODY>}` (and `summary` when the request carries one), `contentFormat: markdown` |
| Move status | `getTransitionsForJiraIssue`, then `transitionJiraIssue` with the id whose `to.name` is the configured status |
| Comment | `addCommentToJiraIssue` with `commentBody` and `contentFormat: markdown` |

The ticket body's `## Blocked by` section and the `Blocks` links must agree. If they don't, the
links win; record the mismatch as a ruling.
