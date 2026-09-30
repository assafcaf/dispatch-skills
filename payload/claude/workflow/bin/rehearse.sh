#!/usr/bin/env bash
# Rehearse the mechanical delivery path in throwaway worktrees (E1-T28).
#
#   rehearse.sh [--keep]
#
# Run from a set-up repo's main checkout. It takes the checkout's HEAD as a throwaway epic head,
# and then, in worktrees under a temporary directory:
#
#   move-onto-epic-head  a detached task worktree is moved onto the epic head (`git reset --hard`)
#   red                  a trivial failing test under the configured test path, committed `[red]`
#   verify-red           verify-red.sh proves it red (exit 1)
#   green                a trivial change that makes it pass, committed on top
#   task-submit          task-submit.sh accepts the task branch
#   merge-task           merge-task.sh merges it into a throwaway epic branch and pushes that
#   preview-restart      the first configured surface with a `Preview start` is started, restarted
#                        and stopped (skipped with PASS when none is configured)
#   ledger-write         ledger.sh, run from the task worktree, updates a temporary ticket in the
#                        main checkout's ledger
#
# Prints `STEP <name> PASS|FAIL <detail>` per step, then `REHEARSAL OK` (exit 0) or
# `REHEARSAL FAILED <n>` (exit 1), n = the FAIL lines. Whatever happens it stops the preview it
# started, then removes its worktrees, its local and remote branches and its temporary ticket.
# --keep leaves the worktrees, branches and ticket for inspection (the preview is still stopped).

set -uo pipefail

keep=""
for a in "$@"; do
  case "$a" in
    --keep) keep=1 ;;
    *) echo "usage: rehearse.sh [--keep]" >&2; exit 64 ;;
  esac
done

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fails=0
pass() { echo "STEP $1 PASS ${2:-}"; }
fail() { echo "STEP $1 FAIL ${2:-}"; fails=$((fails + 1)); }
last() { printf '%s\n' "$1" | tr -d '\r' | grep -v '^[[:space:]]*$' | tail -n 1; }
finish() {
  if [ "$fails" -eq 0 ]; then echo "REHEARSAL OK"; exit 0; fi
  echo "REHEARSAL FAILED $fails"; exit 1
}

main="$(git rev-parse --show-toplevel 2>/dev/null)" &&
  epic_head="$(git rev-parse --verify --quiet HEAD 2>/dev/null)" || {
  fail move-onto-epic-head "not inside a git repository with a commit"
  finish
}
main="$(cd "$main" && cd "$(git rev-parse --git-common-dir)/.." && pwd)"
g() { git -C "$main" "$@"; }

# The configured test path (first pathspec of the `Test paths` row, when it is a directory).
cfg="$main/.claude/workflow/config.md"
paths="$(sed -n 's/^| Test paths | *`\([^`]*\)`.*/\1/p' "$cfg" 2>/dev/null | head -n 1)"
[ -n "$paths" ] || paths="tests/"
tdir="${paths%% *}"
case "$tdir" in */) ;; *) tdir="tests/" ;; esac
test_file="${tdir}pad-rehearsal.sh"

id="pad-rehearsal-$$-$(date +%s)"
epic_branch="$id-epic"
tmp="$(mktemp -d)"
epic_wt="$tmp/epic"
task_wt="$tmp/task"
key="PADREHEARSAL$$-T1"
ticket_dir="$main/.work/tickets/${key%%-T*}"
ticket="$ticket_dir/$key.md"
made=()
surface=""
previewing=""
t() { git -C "$task_wt" -c commit.gpgsign=false "$@"; }

cleanup() {
  if [ -n "$previewing" ]; then
    bash "$bin/preview.sh" stop --surface "$surface" --worktree "$epic_wt" >/dev/null 2>&1
  fi
  if [ -n "$keep" ]; then
    echo "rehearse.sh: kept $tmp, branch $epic_branch, ticket $ticket" >&2
    return
  fi
  local w d i
  for w in "$task_wt" "$epic_wt"; do
    [ -d "$w" ] && g worktree remove --force "$w" >/dev/null 2>&1
  done
  g worktree prune >/dev/null 2>&1
  if g rev-parse -q --verify "refs/remotes/origin/$epic_branch" >/dev/null 2>&1; then
    g push -q origin --delete "$epic_branch" >/dev/null 2>&1
    g update-ref -d "refs/remotes/origin/$epic_branch" >/dev/null 2>&1
  fi
  g rev-parse -q --verify "refs/heads/$epic_branch" >/dev/null 2>&1 &&
    g branch -q -D "$epic_branch" >/dev/null 2>&1
  rm -f "$ticket" "$ticket.tmp."* 2>/dev/null
  for ((i = ${#made[@]} - 1; i >= 0; i--)); do
    d="${made[$i]}"
    rmdir "$d" 2>/dev/null
  done
  rm -rf "$tmp"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# --- move-onto-epic-head -----------------------------------------------------------------------
ok_move=""
if ! out="$(g worktree add -q -b "$epic_branch" "$epic_wt" "$epic_head" 2>&1)"; then
  fail move-onto-epic-head "cannot add the epic worktree: $(last "$out")"
elif ! out="$(g worktree add -q --detach "$task_wt" "$epic_head" 2>&1)"; then
  fail move-onto-epic-head "cannot add the task worktree: $(last "$out")"
elif ! out="$(t reset -q --hard "$epic_head" 2>&1)" ||
  [ "$(t rev-parse HEAD 2>/dev/null)" != "$epic_head" ]; then
  fail move-onto-epic-head "git reset --hard $epic_head: $(last "$out")"
else
  ok_move=1
  pass move-onto-epic-head "${epic_head:0:8} in a detached task worktree"
fi

# --- red ---------------------------------------------------------------------------------------
red=""
if [ -z "$ok_move" ]; then
  fail red "skipped: no task worktree"
else
  mkdir -p "$task_wt/$tdir" &&
    printf '#!/usr/bin/env bash\n# PAD rehearsal: red until pad-rehearsal-green.txt exists.\ntest -f pad-rehearsal-green.txt\n' \
      >"$task_wt/$test_file"
  if out="$(t add -- "$test_file" 2>&1 && t commit -q -m "test(REHEARSAL): trivial red [red]" 2>&1)"; then
    red="$(t rev-parse HEAD)"
    pass red "${red:0:8} adds $test_file"
  else
    fail red "cannot commit $test_file: $(last "$out")"
  fi
fi

# --- verify-red --------------------------------------------------------------------------------
if [ -z "$red" ]; then
  fail verify-red "skipped: no red commit"
else
  out="$(cd "$main" && bash "$bin/verify-red.sh" "$red" -- bash "$test_file" 2>&1)"
  if [ $? -eq 0 ]; then pass verify-red "$(last "$out")"; else fail verify-red "$(last "$out")"; fi
fi

# --- green -------------------------------------------------------------------------------------
green=""
if [ -z "$red" ]; then
  fail green "skipped: no red commit"
else
  echo "green" >"$task_wt/pad-rehearsal-green.txt"
  if ! out="$(t add -- pad-rehearsal-green.txt 2>&1 && t commit -q -m "feat(REHEARSAL): trivial green" 2>&1)"; then
    fail green "cannot commit: $(last "$out")"
  elif ! (cd "$task_wt" && bash "$test_file") >/dev/null 2>&1; then
    fail green "$test_file still fails"
  else
    green="$(t rev-parse HEAD)"
    pass green "${green:0:8} passes $test_file"
  fi
fi

# --- task-submit -------------------------------------------------------------------------------
submitted=""
if [ -z "$green" ]; then
  fail task-submit "skipped: no green commit"
else
  out="$(cd "$task_wt" && bash "$bin/task-submit.sh" "$epic_head" "$red" "$green" --test-paths "$paths" 2>&1)"
  if [ $? -eq 0 ]; then submitted=1; pass task-submit "$(last "$out")"
  else fail task-submit "$(last "$out")"; fi
fi

# --- merge-task --------------------------------------------------------------------------------
if [ -z "$submitted" ]; then
  fail merge-task "skipped: task not submitted"
else
  out="$(cd "$main" && bash "$bin/merge-task.sh" --worktree "$epic_wt" --branch "$epic_branch" \
    --gate "bash $test_file" --lint "true" --test-paths "$paths" \
    REHEARSAL "$red" "$green" "rehearsal" 2>&1)"
  if [ $? -eq 0 ]; then pass merge-task "$(last "$out") on $epic_branch"
  else fail merge-task "$(last "$out")"; fi
fi

# --- preview-restart ---------------------------------------------------------------------------
if [ ! -d "$epic_wt" ]; then
  fail preview-restart "skipped: no epic worktree"
else
  # The preview reads the worktree's config; use the checkout's current one.
  if [ -f "$cfg" ]; then
    mkdir -p "$epic_wt/.claude/workflow" && cp "$cfg" "$epic_wt/.claude/workflow/config.md"
  fi
  surface="$(bash "$bin/preview.sh" list --worktree "$epic_wt" 2>/dev/null | head -n 1 | cut -f1)"
  if [ -z "$surface" ]; then
    pass preview-restart "skipped: no surface has a Preview start"
  elif bash "$bin/preview.sh" status --surface "$surface" --worktree "$epic_wt" 2>/dev/null |
    tail -n 1 | grep -q '^PREVIEW running '; then
    fail preview-restart "a $surface preview is already running; stop it and rehearse again"
  else
    previewing=1
    pidfile="$(cd "$main" && cd "$(git rev-parse --git-common-dir)" && pwd)/pad-preview/$surface.pid"
    out="$(bash "$bin/preview.sh" start --surface "$surface" --worktree "$epic_wt" 2>&1)"
    if [ $? -ne 0 ]; then
      fail preview-restart "start: $(last "$out")"
    else
      p1="$(cat "$pidfile" 2>/dev/null)"
      out="$(bash "$bin/preview.sh" restart --surface "$surface" --worktree "$epic_wt" 2>&1)"
      code=$?
      p2="$(cat "$pidfile" 2>/dev/null)"
      if [ "$code" -ne 0 ]; then fail preview-restart "restart: $(last "$out")"
      elif [ -z "$p2" ] || [ "$p1" = "$p2" ]; then fail preview-restart "restart kept pid $p1"
      else pass preview-restart "$surface restarted (pid $p1 -> $p2)"; fi
    fi
    bash "$bin/preview.sh" stop --surface "$surface" --worktree "$epic_wt" >/dev/null 2>&1
    previewing=""
  fi
fi

# --- ledger-write ------------------------------------------------------------------------------
if [ ! -d "$task_wt" ]; then
  fail ledger-write "skipped: no task worktree"
else
  ok=1
  for d in "$main/.work" "$main/.work/tickets" "$ticket_dir"; do
    [ -d "$d" ] && continue
    if mkdir "$d" 2>/dev/null; then made+=("$d"); else ok=""; break; fi
  done
  if [ -z "$ok" ] || [ -e "$ticket" ] ||
    ! printf -- '---\nkey: %s\nstatus: todo\n---\n\n## Goal\nPAD rehearsal ticket.\n' "$key" >"$ticket" 2>/dev/null; then
    fail ledger-write "cannot create a temporary ticket under $main/.work/tickets"
  else
    out="$(cd "$task_wt" && bash "$bin/ledger.sh" "$key" status doing "rehearsal" 2>&1)"
    if [ "$(last "$out")" = "LEDGER OK $key doing" ] && grep -q ': rehearsal$' "$ticket"; then
      pass ledger-write "$(last "$out") from a worktree"
    else
      fail ledger-write "$(last "$out")"
    fi
  fi
fi

finish
