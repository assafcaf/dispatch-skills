#!/usr/bin/env bash
# Append one halt line to the main checkout's .claude/agent-memory/orchestrator/HALTS.md.
#
#   halt-log.sh <run id> <KEY|-> <pad|project|machine|harness> "<cause>" "<resolution>"
#
# The line is `- <yyyy-mm-dd> <run id> <KEY> [<class>] <cause> — <resolution>`, in UTF-8.
# KEY is `-` for a run-wide pause. The resolution may be `pending`; log a second line with
# the real resolution when the halt clears. The file and its directory are created when
# missing; nothing is ever rewritten. The main checkout is the parent of git's common dir,
# so a linked worktree logs to the same file as the main checkout does.
#
# Exit 0: appended. Exit 1: not in a git repository, or the write failed. Exit 64: usage.

set -uo pipefail

usage() {
  echo "usage: halt-log.sh <run id> <KEY|-> <pad|project|machine|harness> <cause> <resolution>" >&2
  exit 64
}

[ $# -eq 5 ] || usage
run="$1"; key="$2"; class="$3"; cause="$4"; resolution="$5"
[ -n "$run" ] && [ -n "$key" ] && [ -n "$cause" ] && [ -n "$resolution" ] || usage
case "$class" in
  pad|project|machine|harness) ;;
  *) usage ;;
esac

# --path-format=absolute would find the common dir directly, but it needs git 2.31.
top="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "halt-log: not a git repository" >&2; exit 1; }
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || {
  echo "halt-log: cannot find the main checkout" >&2; exit 1; }

dir="$main/.claude/agent-memory/orchestrator"
mkdir -p "$dir" || { echo "halt-log: cannot create $dir" >&2; exit 1; }
# Em dash as UTF-8 octal escapes, so the bytes don't depend on this file's or the locale's encoding.
dash="$(printf '\342\200\224')"
# printf with %s: cause and resolution may hold -e, %, backslashes or $, and must land as given.
printf -- '- %s %s %s [%s] %s %s %s\n' \
  "$(date +%Y-%m-%d)" "$run" "$key" "$class" "$cause" "$dash" "$resolution" \
  >>"$dir/HALTS.md" || { echo "halt-log: cannot append to $dir/HALTS.md" >&2; exit 1; }
