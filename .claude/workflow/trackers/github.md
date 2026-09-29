# Tracker adapter: GitHub Issues

Through the `gh` CLI, against the current repository. Untested in this repo, which uses Jira.
Check each command on first use and fix this file if one has changed.

| Operation | How |
|---|---|
| Read one | `gh issue view <n> --json number,title,body,state,labels` |
| List an epic's tasks | `gh api repos/{owner}/{repo}/issues/<epic>/sub_issues --jq '.[].number'` |
| Find existing by label | `gh issue list --label <label> --search "<text> in:title" --json number,title` |
| Create epic | `gh issue create --title <t> --body-file <f> --label epic,<label>` |
| Create task | `gh issue create --title <t> --body-file <f> --label <label>`, then attach it: `gh api -X POST repos/{owner}/{repo}/issues/<epic>/sub_issues -F sub_issue_id=<task issue id>` (the numeric `id` from `gh api repos/{owner}/{repo}/issues/<n> --jq .id`, not its number) |
| Blocked-by edge | the task body's `## Blocked by` section lists `#<n>`; this is the source of truth |
| Update a ticket | `gh issue edit <n> --body-file <f>` (and `--title` when given) |
| Move status | todo = open with no label; doing = label `in-progress`; review = label `in-review`; done = `gh issue close <n> --reason completed` |
| Comment | `gh issue comment <n> --body-file <f>` |
