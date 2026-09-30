#!/usr/bin/env bash
# Merge a submitted task into the epic branch only after its merged tree passes the gate.
#
#   merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup "<cmd>"]
#                 --gate "<cmd>" --lint "<cmd>" [--test-paths "<pathspecs>"]
#                 <KEY> <RED> <TASK_HEAD> "<GOAL>"
#
# Order: task-submit.sh -> git merge --no-ff --no-commit -> setup (only when a dependency manifest
# or lockfile changed) -> gate -> lint -> commit "Merge <KEY>: <GOAL>" -> push -u origin <branch>.
# Setup, gate and lint run with the epic worktree as their working directory. A failure before
# the commit aborts the merge, so the epic head and tree are exactly as they were.
#
# Last line: MERGED <sha> | REJECTED <KEY>: <reason> | CONFLICT <KEY>: <paths> | ERROR <KEY>: ...
# Exit 0 MERGED, 1 REJECTED or CONFLICT, 2 infrastructure failure (push, dirty tree), 64 usage.
# A failed push keeps the gated merge commit locally: push it again, don't re-merge.

set -uo pipefail

usage() {
  echo "usage: merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup \"<cmd>\"] --gate \"<cmd>\" --lint \"<cmd>\" [--test-paths \"<pathspecs>\"] <KEY> <RED> <TASK_HEAD> \"<GOAL>\"" >&2
  exit 64
}

wt=""; branch=""; setup=""; gate=""; lint=""; paths="tests/"
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --worktree) wt="${2:-}"; shift 2 ;;
    --branch) branch="${2:-}"; shift 2 ;;
    --setup) setup="${2:-}"; shift 2 ;;
    --gate) gate="${2:-}"; shift 2 ;;
    --lint) lint="${2:-}"; shift 2 ;;
    --test-paths) paths="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ "${#pos[@]}" -eq 4 ] && [ -n "$wt" ] && [ -n "$branch" ] && [ -n "$gate" ] && [ -n "$lint" ] ||
  usage
key="${pos[0]}"; red="${pos[1]}"; head="${pos[2]}"; goal="${pos[3]}"

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
g() { git -C "$wt" "$@"; }
infra() { echo "ERROR $key: $1"; exit 2; }
log="$(mktemp)"
trap 'rm -f "$log"' EXIT

# Infrastructure: the epic worktree must be on its branch with no uncommitted tracked change.
[ "$(g symbolic-ref -q --short HEAD 2>/dev/null)" = "$branch" ] ||
  infra "$wt is not on branch $branch"
g rev-parse -q --verify MERGE_HEAD >/dev/null && infra "a merge is already in progress in $wt"
[ -z "$(g status --porcelain --untracked-files=no)" ] || infra "epic worktree $wt is dirty"
before="$(g rev-parse HEAD)"

# Submission rules, before the tree is touched. A task cut from an earlier epic head is checked
# against the head it was cut from; the merge below then finds any conflict.
base="$(g merge-base "$before" "$head" 2>/dev/null)" || base="$before"
out="$(cd "$wt" && bash "$bin/task-submit.sh" "$base" "$red" "$head" --test-paths "$paths" 2>&1)"
if [ $? -ne 0 ]; then
  reason="$(printf '%s\n' "$out" | tail -n 1)"
  echo "REJECTED $key: ${reason#SUBMIT FAIL }"
  exit 1
fi

abort() { g merge --abort >/dev/null 2>&1 || g reset -q --merge >/dev/null 2>&1; }

if ! g merge --no-ff --no-commit "$head" >"$log" 2>&1; then
  conflicts="$(g diff --name-only --diff-filter=U | tr '\n' ' ')"
  abort
  if [ -n "$conflicts" ]; then
    echo "CONFLICT $key: ${conflicts% }"
    exit 1
  fi
  tail -n 40 "$log"
  infra "git merge failed without a conflict"
fi

# Run one step in the epic worktree; on failure print its tail, abort the merge and reject.
step() {
  local name="$1" cmd="$2"
  (cd "$wt" && bash -c "$cmd") >"$log" 2>&1 && return 0
  local code=$?
  tail -n 40 "$log"
  abort
  echo "REJECTED $key: $name failed (exit $code)"
  exit 1
}

if [ -n "$setup" ]; then
  manifests='^(.*/)?(package\.json|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|uv\.lock|Pipfile|Pipfile\.lock|setup\.py|setup\.cfg|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|composer\.json|composer\.lock)$'
  if g diff --cached --name-only "$before" | grep -Eq "$manifests"; then
    step setup "$setup"
  fi
fi
step gate "$gate"
step lint "$lint"

g commit -q --no-edit -m "Merge $key: $goal" >"$log" 2>&1 || {
  tail -n 40 "$log"; abort; infra "git commit failed"; }
sha="$(g rev-parse HEAD)"

g push -q -u origin "$branch" >"$log" 2>&1 || {
  tail -n 40 "$log"
  infra "push failed; merge $sha is committed locally on $branch"
}

echo "MERGED $sha"
