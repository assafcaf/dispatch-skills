#!/usr/bin/env bash
# Merge a submitted task into the epic branch only after its merged tree passes the gate.
#
#   merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup "<cmd>"]
#                 --gate "<cmd>" --lint "<cmd>" [--test-paths "<pathspecs>"]
#                 <KEY> <RED> <TASK_HEAD> "<GOAL>"
#
# Order: merge lock -> task-submit.sh -> git merge --no-ff --no-commit -> setup (only when a
# dependency manifest or lockfile changed) -> gate -> lint -> commit "Merge <KEY>: <GOAL>" -> push
# -u origin <branch>. Setup, gate and lint run with the epic worktree as their working directory.
# A failure before the commit aborts the merge, so the epic head and tree are exactly as they were.
#
# The merge lock `<git common dir>/pad-locks/merge` (a mkdir lock holding the owner's pid) is held
# from before the submission checks until exit, so concurrent merges on one repo run one after the
# other, each on the head the previous one produced. The gate runs through
# `suite-slot.sh --priority merge`. A gate whose failures (pytest-style `FAILED <file>::<test>`
# lines) all sit in test files the task neither changed nor imports is rerun once; a green rerun
# counts. A failure naming no test file is not rerun.
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
lock=""
trap 'rm -f "$log"; [ -z "$lock" ] || rm -rf "$lock"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# The merge lock, taken before anything reads the epic worktree. A lock whose owner is gone is
# reclaimed; one with no pid yet is being taken.
common="$(g rev-parse --git-common-dir 2>/dev/null)" &&
  common="$(cd "$wt" && cd "$common" && pwd)" || infra "$wt is not a git worktree"
mkdir -p "$common/pad-locks" || infra "cannot create $common/pad-locks"
until mkdir "$common/pad-locks/merge" 2>/dev/null; do
  owner="$(cat "$common/pad-locks/merge/pid" 2>/dev/null)"
  if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then
    rm -rf "$common/pad-locks/merge"
    continue
  fi
  sleep 0.1
done
lock="$common/pad-locks/merge"
echo $$ > "$lock/pid"

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

# Print the failed step's tail, abort the merge and reject.
reject_step() {
  tail -n 40 "$log"
  abort
  echo "REJECTED $key: $1 failed (exit $2)"
  exit 1
}

# Run one step in the epic worktree; reject on failure.
step() {
  (cd "$wt" && bash -c "$2") >"$log" 2>&1 && return 0
  reject_step "$1" "$?"
}

# The gate, holding a suite slot ahead of task-side runs.
run_gate() {
  (cd "$wt" && bash "$bin/suite-slot.sh" --priority merge -- bash -c "$gate") >"$log" 2>&1
}

# True when the gate output names failing test files and every one is outside the task: not
# changed between <base> and the task head, and importing none of the changed files.
outside_only() {
  local files changed f c stem
  files="$(sed -n 's/^FAILED \([^ :]*\)::.*/\1/p' "$log" | sort -u)"
  [ -n "$files" ] || return 1
  changed="$(g diff --name-only "$base" "$head")"
  for f in $files; do
    printf '%s\n' "$changed" | grep -qxF "$f" && return 1
    [ -f "$wt/$f" ] || return 1
    for c in $changed; do
      stem="$(basename "$c")"
      [ -n "${stem%.*}" ] || continue
      stem="$(printf '%s' "${stem%.*}" | sed 's/[][\.*^$+?(){}|/]/\\&/g')"
      grep -E '(^|[^[:alnum:]_])(import|from|require|include|use)([^[:alnum:]_]|$)' "$wt/$f" |
        grep -qE "(^|[^[:alnum:]_])${stem}([^[:alnum:]_]|$)" && return 1
    done
  done
  return 0
}

if [ -n "$setup" ]; then
  manifests='^(.*/)?(package\.json|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|uv\.lock|Pipfile|Pipfile\.lock|setup\.py|setup\.cfg|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|composer\.json|composer\.lock)$'
  if g diff --cached --name-only "$before" | grep -Eq "$manifests"; then
    step setup "$setup"
  fi
fi
run_gate; code=$?
if [ "$code" -ne 0 ] && outside_only; then
  echo "gate failed only in test files outside $key; rerunning it once"
  run_gate; code=$?
fi
[ "$code" -eq 0 ] || reject_step gate "$code"
step lint "$lint"

g commit -q --no-edit -m "Merge $key: $goal" >"$log" 2>&1 || {
  tail -n 40 "$log"; abort; infra "git commit failed"; }
sha="$(g rev-parse HEAD)"

g push -q -u origin "$branch" >"$log" 2>&1 || {
  tail -n 40 "$log"
  infra "push failed; merge $sha is committed locally on $branch"
}

echo "MERGED $sha"
