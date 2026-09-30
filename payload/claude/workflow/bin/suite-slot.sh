#!/usr/bin/env bash
# Run a full-suite command holding one of N suite slots, so parallel tasks can't overload the host.
#
#   suite-slot.sh [--priority merge] -- <cmd...>
#
# Slots are directories `<git common dir>/pad-locks/slots/<i>` (mkdir is atomic everywhere; Git
# Bash has no flock), each holding the owner's pid, so a slot whose owner died is reclaimed.
# N comes from PAD_SUITE_SLOTS, else `Suite slots: <n>` in the repo's .claude/workflow/config.md,
# else 2. A `--priority merge` run marks itself waiting under pad-locks/merge-waiting/; while any
# merge run waits, task-side runs don't take a free slot.
#
# Exits with <cmd>'s exit code; 64 on usage, 2 outside a git repo.

set -uo pipefail

usage() { echo "usage: suite-slot.sh [--priority merge] -- <cmd...>" >&2; exit 64; }

priority=task
while [ $# -gt 0 ]; do
  case "$1" in
    --priority) [ "${2:-}" = merge ] || usage; priority=merge; shift 2 ;;
    --) shift; break ;;
    *) usage ;;
  esac
done
[ $# -gt 0 ] || usage

common="$(git rev-parse --git-common-dir 2>/dev/null)" &&
  common="$(cd "$common" && pwd)" || { echo "suite-slot.sh: not inside a git repository" >&2; exit 2; }

slots="${PAD_SUITE_SLOTS:-}"
if [ -z "$slots" ]; then
  cfg="$(git rev-parse --show-toplevel 2>/dev/null)/.claude/workflow/config.md"
  if [ -f "$cfg" ]; then
    slots="$(grep -m1 -i 'suite slots' "$cfg" | sed -n 's/.*[Ss]uite slots[^0-9]*\([0-9][0-9]*\).*/\1/p')"
  fi
fi
case "$slots" in ''|*[!0-9]*) slots=2 ;; esac
[ "$slots" -ge 1 ] || slots=1

locks="$common/pad-locks"
waiting="$locks/merge-waiting"
mkdir -p "$locks/slots" "$waiting"

held=""
marker=""
cleanup() {
  [ -n "$marker" ] && rm -f "$marker"
  [ -n "$held" ] && rm -rf "$held"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A lock dir whose recorded owner is gone is removed. A dir without a pid yet is being taken.
reap() {
  local pid
  pid="$(cat "$1/pid" 2>/dev/null)" || return 0
  [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null && rm -rf "$1"
}

merge_waiting() {
  local f pid
  for f in "$waiting"/*; do
    [ -e "$f" ] || continue
    pid="$(cat "$f" 2>/dev/null)"
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then rm -f "$f"; continue; fi
    return 0
  done
  return 1
}

take() {
  local i
  for i in $(seq 1 "$slots"); do
    if mkdir "$locks/slots/$i" 2>/dev/null; then
      echo $$ > "$locks/slots/$i/pid"
      held="$locks/slots/$i"
      return 0
    fi
    reap "$locks/slots/$i"
  done
  return 1
}

if [ "$priority" = merge ]; then
  marker="$waiting/$$"
  echo $$ > "$marker"
fi

while :; do
  if [ "$priority" = merge ] || ! merge_waiting; then
    take && break
  fi
  sleep 0.1
done
if [ -n "$marker" ]; then rm -f "$marker"; marker=""; fi

"$@"
code=$?
exit "$code"
