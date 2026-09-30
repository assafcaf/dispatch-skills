#!/usr/bin/env bash
# Prove a run's setup still holds before any agent starts.
#
#   preflight.sh [--config <path>]
#
# Run from the repo root (the epic worktree). The config defaults to .claude/workflow/config.md;
# settings are the layers check-moves.sh reads (~/.claude/settings.json, .claude/settings.json,
# .claude/settings.local.json). Each check is a function below, and each reports on its own:
#
#   moves                 check-moves.sh passes: every Git moves command is allowed
#   commands              every command a run executes unattended is allowed and not denied:
#                         the Commands gates (Setup, Run named tests, Full suite, Typecheck,
#                         Lint, Weakened tests), each surface's Automated check and Preview
#                         start, and `bash .claude/workflow/bin/<script> ...` for every script
#   knowledge-paths       knowledge-paths.sh passes
#   version               config.md's `PAD version:` equals the installed VERSION (beside bin/),
#                         and config.md has every `## ` section of this version's
#                         config.example.md
#   dependency-directory  the Commands `Dependency directory`, when named, exists
#   lockfile              the Commands `Lockfile`, when named, exists
#   models                each agent file's `model:` matches the Agents table, with the Tiers
#                         table's `standard` row for test-designer and code-writer
#   executable            every .claude/workflow/bin/*.sh is mode 100755 in the git index
#   gitignore             .gitignore covers .work/ and .claude/worktrees/
#   line-endings          core.autocrlf and .gitattributes agree: not autocrlf=true with
#                         `eol=lf`, nor autocrlf false/input with `eol=crlf`
#
# Output: one `PREFLIGHT FAIL <check>: <detail>` line per failure, then `PREFLIGHT OK` or
# `PREFLIGHT FAILED <n>`. Exit 0 when every check passes, 1 otherwise (a missing config or bad
# usage included).

set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
wf="$(dirname "$here")"
config=".claude/workflow/config.md"

fails=0
fail() { printf 'PREFLIGHT FAIL %s: %s\n' "$1" "$2"; fails=$((fails + 1)); }
finish() {
  if [ "$fails" -eq 0 ]; then echo "PREFLIGHT OK"; exit 0; fi
  echo "PREFLIGHT FAILED $fails"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --config)
      if [ $# -lt 2 ]; then fail usage "--config needs a path"; finish; fi
      config="$2"; shift 2 ;;
    *) fail usage "preflight.sh [--config <path>], got '$1'"; finish ;;
  esac
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
US=$'\037'

# The sections a config of this PAD version has, when the payload's config.example.md is not
# installed beside bin/. Keep in step with config.example.md's `## ` headings.
FALLBACK_SECTIONS=(
  "Tracker" "Agents" "Tracker updates during a run" "Paths" "Project knowledge" "Commands"
  "Git moves" "Serial resources" "Surfaces" "Review" "Execution"
)

# --- config tables ---------------------------------------------------------------------------

# table <heading line> <col,col,...>: the rows of the first table after that heading, one per
# line, the named columns' cells trimmed and joined by US. A missing column gives "".
table() {
  [ -f "$config" ] || return 0
  awk -F'|' -v want="$1" -v cols="$2" '
    function trim(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); return s }
    BEGIN { n = split(cols, C, ",") }
    { sub(/\r$/, "") }
    /^#+ / { line = $0; sub(/[ \t]+$/, "", line); insec = (!done && line == want); hdr = 0; next }
    insec && /^[ \t]*\|/ {
      if (!hdr) { for (i = 2; i < NF; i++) col[trim($i)] = i; hdr = 1; next }
      if ($0 ~ /^[ \t]*\|[ \t:]*-/) next
      out = ""
      for (i = 1; i <= n; i++) out = out (i > 1 ? "\037" : "") ((C[i] in col) ? trim($(col[C[i]])) : "")
      print out
      next
    }
    insec && hdr { insec = 0; done = 1 }
  ' "$config"
}

# value <cell>: the command or path a cell names: its first backtick span, or the cell itself.
# Empty for `none`, a dash or a bare <placeholder>.
value() {
  local v="$1"
  case "$v" in ''|none|none[!a-zA-Z]*|—*|-|'- '*) return 0 ;; esac
  if [[ "$v" == *'`'*'`'* ]]; then v="${v#*\`}"; v="${v%%\`*}"; fi
  case "$v" in '<'*'>') [[ "${v:1}" == *'<'* ]] || return 0 ;; esac
  printf '%s' "$v"
}

# gate <name>: the value of that row of the Commands table.
gate() {
  local g c
  while IFS="$US" read -r g c; do
    [ "$g" = "$1" ] && { value "$c"; return 0; }
  done <<<"$(table "## Commands" "Gate,Command")"
}

# --- checks ----------------------------------------------------------------------------------

check_moves() {
  local out rc line any=0
  out="$(bash "$here/check-moves.sh" --config "$config" 2>"$tmp/moves.err")"; rc=$?
  while IFS= read -r line; do
    case "$line" in "MOVES FAIL "*) fail moves "${line#MOVES FAIL }"; any=1 ;; esac
  done <<<"$out"
  if [ "$rc" -ne 0 ] && [ "$any" -eq 0 ]; then
    fail moves "check-moves.sh exited $rc: $(head -n 1 "$tmp/moves.err")"
  fi
}

check_commands() {
  local labels=() cmds=() g c n s a p name seg i out rc line any=0
  for g in "Setup in a fresh worktree" "Run named tests" "Full suite" "Typecheck" "Lint" \
    "Weakened tests"; do
    c="$(gate "$g")"
    [ -n "$c" ] && { labels+=("$g"); cmds+=("$c"); }
  done
  while IFS="$US" read -r n a p; do
    [ -n "$n" ] || continue
    name="$(value "$n")"
    c="$(value "$a")"; [ -n "$c" ] && { labels+=("$name Automated check"); cmds+=("$c"); }
    c="$(value "$p")"; [ -n "$c" ] && { labels+=("$name Preview start"); cmds+=("$c"); }
  done <<<"$(table "## Surfaces" "Surface,Automated check,Preview start")"
  for s in "$here"/*.sh; do
    [ -f "$s" ] || continue
    labels+=("workflow script"); cmds+=("bash .claude/workflow/bin/${s##*/} <args>")
  done

  # Each command, split where the shell would run separate commands, goes through
  # check-moves.sh's matcher as a row of a Git moves table of its own.
  {
    printf '## Git moves\n\n| Capability | Command |\n|---|---|\n'
    for i in "${!cmds[@]}"; do
      printf '%s\n' "${cmds[$i]}" | sed 's/{{\([^}]*\)}}/<\1>/g; s/{\([^}]*\)}/<\1>/g' \
        | awk '{ gsub(/\|\||&&|;|\|/, "\n"); print }' \
        | while IFS= read -r seg; do
            seg="${seg#"${seg%%[![:space:]]*}"}"; seg="${seg%"${seg##*[![:space:]]}"}"
            [ -n "$seg" ] && printf '| cmd-%d | %s |\n' "$i" "$seg"
          done
    done
  } >"$tmp/commands.md"
  out="$(bash "$here/check-moves.sh" --config "$tmp/commands.md" 2>"$tmp/commands.err")"; rc=$?
  while IFS= read -r line; do
    [[ "$line" =~ ^MOVES\ FAIL\ cmd-([0-9]+):\ (.*)$ ]] || continue
    fail commands "${labels[${BASH_REMATCH[1]}]}: ${BASH_REMATCH[2]}"
    any=1
  done <<<"$out"
  if [ "$rc" -ne 0 ] && [ "$any" -eq 0 ] && [ -s "$tmp/commands.err" ]; then
    fail commands "cannot check the settings: $(head -n 1 "$tmp/commands.err")"
  fi
}

check_knowledge_paths() {
  local out rc line any=0
  out="$(bash "$here/knowledge-paths.sh" 2>&1)"; rc=$?
  [ "$rc" -eq 0 ] && return 0
  while IFS= read -r line; do
    case "$line" in
      "knowledge-paths: "*) fail knowledge-paths "${line#knowledge-paths: }"; any=1 ;;
    esac
  done <<<"$out"
  [ "$any" -eq 1 ] || fail knowledge-paths "knowledge-paths.sh exited $rc: $(head -n 1 <<<"$out")"
}

# vercmp <a> <b>: prints -1, 0 or 1 comparing dotted numeric versions.
vercmp() {
  local IFS=. i x y
  local -a a b
  read -r -a a <<<"$1"; read -r -a b <<<"$2"
  for ((i = 0; i < ${#a[@]} || i < ${#b[@]}; i++)); do
    x=$((10#${a[i]:-0})); y=$((10#${b[i]:-0}))
    if [ "$x" -lt "$y" ]; then echo -1; return; fi
    if [ "$x" -gt "$y" ]; then echo 1; return; fi
  done
  echo 0
}

check_version() {
  local installed recorded want=() have s missing="" add="" cmp
  installed="$(tr -d '[:space:]' <"$wf/VERSION" 2>/dev/null)"
  if [ -z "$installed" ]; then fail version "no PAD version at $wf/VERSION"; return; fi
  recorded="$(sed -n 's/^PAD version:[[:space:]]*//p' "$config" | head -n 1 | tr -d '\r')"
  recorded="${recorded%"${recorded##*[![:space:]]}"}"

  if [ -f "$wf/config.example.md" ]; then
    while IFS= read -r s; do [ -n "$s" ] && want+=("$s"); done <<<"$(
      sed -n 's/^## //p' "$wf/config.example.md" | tr -d '\r' | sed 's/[[:space:]]*$//')"
  else
    want=("${FALLBACK_SECTIONS[@]}")
  fi
  have="$(sed -n 's/^## //p' "$config" | tr -d '\r' | sed 's/[[:space:]]*$//')"
  for s in "${want[@]}"; do
    grep -Fxq -- "$s" <<<"$have" || missing="${missing:+$missing, }## $s"
  done
  [ -n "$missing" ] && add="; sections to add: $missing"

  if ! [[ "$recorded" =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
    fail version "$config records no PAD version (installed is $installed): run /setup-workflow upgrade$add"
    return
  fi
  cmp="$(vercmp "$recorded" "$installed")"
  if [ "$cmp" = -1 ]; then
    fail version "$config records PAD version $recorded, older than the installed $installed: run /setup-workflow upgrade$add"
  elif [ "$cmp" = 1 ]; then
    fail version "$config records PAD version $recorded, newer than the installed $installed: reinstall PAD$add"
  elif [ -n "$missing" ]; then
    fail version "$config lacks sections of PAD $installed: $missing; run /setup-workflow upgrade to add them"
  fi
}

check_dependency_directory() {
  local d
  d="$(gate "Dependency directory")"
  [ -z "$d" ] || [ -d "$d" ] || fail dependency-directory \
    "$d (Commands, Dependency directory) does not exist: run setup in the repo root"
}

check_lockfile() {
  local f
  f="$(gate "Lockfile")"
  [ -z "$f" ] || [ -f "$f" ] || fail lockfile "$f (Commands, Lockfile) does not exist"
}

check_models() {
  local agents=() models=() a m t td cw i file got
  set_model() { # set_model <agent> <model>
    local j
    [[ "$2" =~ ^[A-Za-z0-9._-]+$ ]] || return 0
    for j in "${!agents[@]}"; do
      [ "${agents[$j]}" = "$1" ] && { models[$j]="$2"; return 0; }
    done
    agents+=("$1"); models+=("$2")
  }
  while IFS="$US" read -r a m; do
    a="$(value "$a")"; [ -n "$a" ] && set_model "$a" "$(value "$m")"
  done <<<"$(table "## Agents" "Agent,Model")"
  while IFS="$US" read -r t td cw; do
    [ "$(value "$t")" = standard ] || continue
    set_model test-designer "$(value "$td")"
    set_model code-writer "$(value "$cw")"
  done <<<"$(table "### Tiers" "Tier,Test-designer,Code-writer")"

  for i in "${!agents[@]}"; do
    a="${agents[$i]}"; m="${models[$i]}"
    file=".claude/agents/$a.md"
    if [ ! -f "$file" ]; then
      fail models "$a: no $file for the Agents table's row"
      continue
    fi
    got="$(awk '
      { sub(/\r$/, "") }
      NR == 1 { if ($0 != "---") exit; next }
      /^---[ \t]*$/ { exit }
      /^model:/ { sub(/^model:[ \t]*/, ""); gsub(/["\047 \t]/, ""); print; exit }
    ' "$file")"
    [ "$got" = "$m" ] || fail models "$a: $file has model ${got:-<none>}, the config says $m"
  done
}

check_executable() {
  local line mode path
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    fail executable "not a git repository: cannot read script modes"; return; }
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    mode="${line%% *}"; path="${line#*$'\t'}"
    [ "$mode" = 100755 ] || fail executable \
      "$path is mode $mode in git, not 100755: run git update-index --chmod=+x $path"
  done <<<"$(git ls-files -s -- '.claude/workflow/bin/*.sh')"
}

check_gitignore() {
  local p
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    fail gitignore "not a git repository: cannot check .gitignore"; return; }
  for p in .work/ .claude/worktrees/; do
    git check-ignore -q --no-index -- "${p}pad-preflight-probe" 2>/dev/null \
      || git check-ignore -q --no-index -- "$p" 2>/dev/null \
      || fail gitignore "$p is not ignored: add '$p' to .gitignore"
  done
}

check_line_endings() {
  local auto eol=""
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  [ -f .gitattributes ] || return 0
  auto="$(git config --get core.autocrlf 2>/dev/null | tr -d '\r' | tr 'A-Z' 'a-z')"
  grep -Eq 'eol=lf([[:space:]]|$)' .gitattributes && eol=lf
  grep -Eq 'eol=crlf([[:space:]]|$)' .gitattributes && eol=crlf
  if [ "$auto" = true ] && [ "$eol" = lf ]; then
    fail line-endings "core.autocrlf=true converts to CRLF but .gitattributes forces eol=lf: set core.autocrlf to input or false, or change .gitattributes"
  elif [ "$auto" != true ] && [ "$eol" = crlf ]; then
    fail line-endings "core.autocrlf=${auto:-unset} but .gitattributes forces eol=crlf: set core.autocrlf=true, or change .gitattributes"
  fi
}

# --- run -------------------------------------------------------------------------------------

if [ -f "$config" ]; then
  check_moves
  check_commands
else
  fail config "no config at $config"
fi
check_knowledge_paths
if [ -f "$config" ]; then
  check_version
  check_dependency_directory
  check_lockfile
  check_models
fi
check_executable
check_gitignore
check_line_endings
finish
