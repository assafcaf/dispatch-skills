#!/usr/bin/env bash
# Fail if the knowledge layer has drifted from the repo: a path it names no longer exists, or
# a file has grown past its ceiling.
#
# A module map is read by every agent in a run and believed. When a directory is renamed and
# the map is not, the map does not go quiet: it sends each agent to a path that is not there.
# Ceilings are checked here too, because context files cost over 20% more inference per task
# (arXiv 2602.11988) and a file nobody trims is charged on every task whether it earns it or
# not.
#
#   knowledge-paths.sh [--root <dir>]
#
# Checks CONTEXT.md and .claude/workflow/project.md. A path is any backtick span holding no
# whitespace and at least one `/`; URLs and globs are skipped. Bare filenames are skipped,
# because prose says `config.md` far more often than it cites a file.
#
# Ceilings default to 100 lines for CONTEXT.md and 120 for project.md; override with
# CONTEXT_MAX and PROJECT_MAX.
#
# Exit 0: clean, or the mode is off and there is nothing to check. Exit 1: problems printed.
# Exit 64: usage.

set -uo pipefail

root=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root) root="${2-}"; shift 2 ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "usage: knowledge-paths.sh [--root <dir>]" >&2; exit 64 ;;
  esac
done

if [ -z "$root" ]; then
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "knowledge-paths: not a git repository, and no --root given" >&2; exit 64; }
fi
[ -d "$root" ] || { echo "knowledge-paths: no such directory: $root" >&2; exit 64; }

# A temp file rather than process substitution: `< <(...)` is not available in every bash this
# runs under, and Git Bash on Windows is one of them.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

config="$root/.claude/workflow/config.md"
context="$root/CONTEXT.md"
project="$root/.claude/workflow/project.md"

# The switch lives in config.md. A config with no Project knowledge section predates the
# knowledge layer, which is the same thing as having it off.
mode=off
if [ -f "$config" ] \
   && sed -n '/^## Project knowledge/,/^## /p' "$config" | grep -qiE '^Mode:[[:space:]]*on'; then
  mode=on
fi

if [ "$mode" = off ]; then
  echo "knowledge-paths: mode off, nothing to check"
  exit 0
fi

rc=0
checked=0

for f in "$context" "$project"; do
  rel="${f#"$root"/}"
  if [ ! -f "$f" ]; then
    echo "knowledge-paths: mode is on but $rel is missing (run /knowledge-layer)"
    rc=1
    continue
  fi

  case "$rel" in
    CONTEXT.md) max="${CONTEXT_MAX:-100}" ;;
    *)          max="${PROJECT_MAX:-120}" ;;
  esac
  lines="$(wc -l <"$f" | tr -d '[:space:]')"
  if [ "$lines" -gt "$max" ]; then
    echo "knowledge-paths: $rel is $lines lines, ceiling is $max"
    rc=1
  fi

  grep -oE '`[^`[:space:]]+`' "$f" | tr -d '`' | sort -u >"$tmp/paths" || true
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    case "$p" in
      *://*|*'*'*|*'?'*) continue ;;
      */*) ;;
      *) continue ;;
    esac
    checked=$((checked + 1))
    if [ ! -e "$root/$p" ]; then
      echo "knowledge-paths: $rel names $p -- no such file or directory"
      rc=1
    fi
  done <"$tmp/paths"
done

[ "$rc" -eq 0 ] && echo "knowledge-paths: ok ($checked paths resolve)"
exit "$rc"
