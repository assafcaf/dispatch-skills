#!/usr/bin/env bash
# Append one line to a run's log in the main checkout, from any worktree or subdirectory.
#
#   run-log.sh <run id> <line>
#
# The log is <main checkout>/.work/runs/<run id>/progress.md. Its directory is created when
# missing. The line is written literally, followed by a newline; nothing is ever rewritten.
# The main checkout is the parent of git's common dir, so a linked worktree logs to the same
# file as the main checkout does.
#
# Exit 0: appended. Exit 1: not in a git repository, or the write failed. Exit 64: usage.

set -uo pipefail

usage() { echo "usage: run-log.sh <run id> <line>" >&2; exit 64; }

[ $# -eq 2 ] || usage
run="$1"
line="$2"
[ -n "$run" ] || usage

# From the top of this worktree, --git-common-dir is either absolute or relative to it.
# --path-format=absolute would say this directly, but it needs git 2.31.
top="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "run-log: not a git repository" >&2; exit 1; }
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || {
  echo "run-log: cannot find the main checkout" >&2; exit 1; }

dir="$main/.work/runs/$run"
mkdir -p "$dir" || { echo "run-log: cannot create $dir" >&2; exit 1; }
# printf, not echo: a line may start with -e or hold backslashes, and must land as given.
printf '%s\n' "$line" >>"$dir/progress.md" || {
  echo "run-log: cannot append to $dir/progress.md" >&2; exit 1; }
