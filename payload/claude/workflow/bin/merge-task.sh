#!/usr/bin/env bash
# Merge a submitted task into the epic branch only after its merged tree passes the gate.
#
#   merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup "<cmd>"]
#                 --gate "<cmd>" --lint "<cmd>" <KEY> <RED> <TASK_HEAD> "<GOAL>"
#
# Last line: MERGED <sha> | REJECTED <KEY>: <reason> | CONFLICT <KEY>: <paths>.
# Exit 0 MERGED, 1 otherwise, 2 infrastructure failure (push, dirty tree).

echo "merge-task.sh: not implemented" >&2
exit 1
