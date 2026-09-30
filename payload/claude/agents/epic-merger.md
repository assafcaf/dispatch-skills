---
name: epic-merger
description: Retired. Tasks now land on the epic branch through .claude/workflow/bin/merge-task.sh, which /batch-implement runs itself; do not dispatch this agent.
tools: Read
model: sonnet
memory: project
effort: low
---

This agent is retired. `/batch-implement` no longer dispatches a merger: for each `SUBMITTED`
task it runs `bash .claude/workflow/bin/merge-task.sh` in the background and messages the
task's owner the script's last line. The script takes the merge lock, checks the submission,
merges, gates the merged tree and pushes, so no agent sits between a task and its merge.

If you were dispatched anyway, do nothing and stop with
`FAIL: epic-merger is retired; run merge-task.sh instead`.
