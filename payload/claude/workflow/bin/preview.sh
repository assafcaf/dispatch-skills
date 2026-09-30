#!/usr/bin/env bash
# preview.sh start|stop|restart|status|list [--surface <name>] [--worktree <path>]
#
# Manages a live preview of the epic head. The preview is a row of the `## Surfaces` table in
# <worktree>/.claude/workflow/config.md: `Preview start` (shell command, run in the worktree),
# `Ready when` (shell command that exits 0 once the preview is up) and `Restart when changed`
# (comma-separated repo paths). The pid file is `<git common dir>/pad-preview/<surface>.pid`;
# its content is the preview's pid, so it changes on every restart.
#
# `start` and `restart` poll Ready when for up to 60 s. `list` prints `<surface><TAB><paths>` for
# every surface with a preview (merge-task.sh uses it). A surface with no `Preview start` is a
# no-op for every verb: exit 0, no pid file.
#
# Last line: PREVIEW <running|stopped|failed> <surface>. Exit 0, 1 start failed, 64 usage.

set -uo pipefail

usage() {
  echo "usage: preview.sh start|stop|restart|status|list [--surface <name>] [--worktree <path>]" >&2
  exit 64
}

verb="${1:-}"; [ $# -gt 0 ] && shift
surface=""; wt="."
while [ $# -gt 0 ]; do
  case "$1" in
    --surface) surface="${2:-}"; shift 2 ;;
    --worktree) wt="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
case "$verb" in start|stop|restart|status|list) ;; *) usage ;; esac

timeout="${PAD_PREVIEW_TIMEOUT:-60}"
cfg="$wt/.claude/workflow/config.md"
US=$'\037'

# Surfaces rows as: name US start US ready US restart, cells stripped of blanks and backticks.
rows() {
  [ -f "$cfg" ] || return 0
  awk -F'|' '
    function clean(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); if (s ~ /^`.*`$/) s = substr(s, 2, length(s) - 2); return s }
    { sub(/\r$/, "") }
    /^## / { insec = ($0 ~ /^## Surfaces[ \t]*$/); hdr = 0; next }
    insec && /^\|/ {
      if (!hdr) { for (i = 2; i < NF; i++) col[clean($i)] = i; hdr = 1; next }
      if ($0 ~ /^\|[ \t]*-/) next
      printf "%s\037%s\037%s\037%s\n", clean($(col["Surface"])), clean($(col["Preview start"])), clean($(col["Ready when"])), clean($(col["Restart when changed"]))
    }' "$cfg" | tr -d '\r'
}

if [ "$verb" = list ]; then
  rows | while IFS="$US" read -r n s r c; do
    [ -n "$s" ] && printf '%s\t%s\n' "$n" "$c"
  done
  exit 0
fi

pick=""
while IFS= read -r l; do
  if [ -z "$surface" ] || [ "${l%%"$US"*}" = "$surface" ]; then pick="$l"; break; fi
done <<<"$(rows)"
IFS="$US" read -r name start ready restart <<<"$pick"
[ -n "$surface" ] && name="$surface"
[ -n "$name" ] || { echo "preview.sh: no surface found in $cfg" >&2; exit 64; }
[ -n "$start" ] || exit 0

common="$(git -C "$wt" rev-parse --git-common-dir)" && common="$(cd "$wt" && cd "$common" && pwd)" || exit 64
dir="$common/pad-preview"
pidfile="$dir/$name.pid"

alive() { local p; p="$(cat "$pidfile" 2>/dev/null)"; [ -n "$p" ] && kill -0 "$p" 2>/dev/null; }

do_stop() {
  local p
  p="$(cat "$pidfile" 2>/dev/null)"
  if [ -n "$p" ]; then
    pkill -P "$p" 2>/dev/null
    kill "$p" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$p" 2>/dev/null || break; sleep 0.2; done
    kill -9 "$p" 2>/dev/null
  fi
  rm -f "$pidfile"
}

do_start() {
  if alive; then echo "PREVIEW running $name"; return 0; fi
  mkdir -p "$dir"
  rm -f "$pidfile"
  (cd "$wt" || exit 1; nohup bash -c "$start" >"$dir/$name.log" 2>&1 </dev/null & echo $! > "$pidfile")
  local waited=0
  while :; do
    if ! alive; then
      rm -f "$pidfile"; tail -n 20 "$dir/$name.log" >&2
      echo "PREVIEW failed $name"; return 1
    fi
    if [ -z "$ready" ] || (cd "$wt" && bash -c "$ready") >/dev/null 2>&1; then
      echo "PREVIEW running $name"; return 0
    fi
    [ "$waited" -ge $((timeout * 5)) ] && break
    sleep 0.2; waited=$((waited + 1))
  done
  do_stop
  echo "preview.sh: $name not ready after ${timeout}s" >&2
  echo "PREVIEW failed $name"; return 1
}

case "$verb" in
  start) do_start; exit $? ;;
  stop) do_stop; echo "PREVIEW stopped $name" ;;
  restart) do_stop; do_start; exit $? ;;
  status) if alive; then echo "PREVIEW running $name"; else rm -f "$pidfile"; echo "PREVIEW stopped $name"; fi ;;
esac
exit 0
