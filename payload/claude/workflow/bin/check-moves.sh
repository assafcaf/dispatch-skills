#!/usr/bin/env bash
# Prove every Git moves capability in config.md is allowed by the effective settings.
#
#   check-moves.sh [--config <config.md>] [--settings <file>]...
#
# Reads the `## Git moves` table (`| Capability | Command |`) of the config, and the
# `permissions.allow` / `permissions.deny` lists of each settings file. Defaults, relative to
# the working directory: `.claude/workflow/config.md`, then `~/.claude/settings.json`,
# `.claude/settings.json` and `.claude/settings.local.json` (a missing default settings file is
# skipped). Any --settings replaces the default list; a named file must exist.
#
# A capability passes when its command matches an allow rule in some layer and no deny rule in
# any layer. A command matching neither would prompt, so it fails. Only `Bash(...)` rules count:
#   Bash(cmd)      exact
#   Bash(cmd:*)    cmd, or cmd followed by a space and anything (a word boundary)
#   Bash(a * b)    `*` matches any text, spaces included; a trailing ` *` also matches without it
#   Bash           every command
# Placeholders in a command (`<sha>`, `<branch>`, `<path>`, any `<word>`) stand for an arbitrary
# value: a rule must cover any value, not one particular sha or branch.
#
# Output: one line per failure,
#   MOVES FAIL <capability>: <command> — add "Bash(<pattern>)" to permissions.allow
# or `MOVES OK` as the last line. Diagnostics go to stderr.
#
# Exit 0: every capability passes. Exit 1: a capability fails, or any error (missing config,
# no `## Git moves` section, unreadable or malformed settings JSON, bad usage).

set -uo pipefail

REQUIRED=(
  branch-from-epic-head move-onto-sha take-red rebase-red discard-changes set-aside-work
  try-merge abort-merge commit-merge revert-merge push-epic remove-worktree delete-merged-branch
)

die() { echo "check-moves: $*" >&2; exit 1; }
usage() { echo "usage: check-moves.sh [--config <config.md>] [--settings <file>]..." >&2; exit 1; }

config=".claude/workflow/config.md"
settings=()
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || usage; config="$2"; shift 2 ;;
    --settings) [ $# -ge 2 ] || usage; settings+=("$2"); shift 2 ;;
    *) usage ;;
  esac
done

if [ ${#settings[@]} -eq 0 ]; then
  for f in "${HOME:-}/.claude/settings.json" .claude/settings.json .claude/settings.local.json; do
    [ -n "${HOME:-}" ] || [ "$f" != "/.claude/settings.json" ] || continue
    [ -f "$f" ] && settings+=("$f")
  done
else
  for f in "${settings[@]}"; do
    [ -f "$f" ] || die "settings file not found: $f"
  done
fi

# --- settings: a strict JSON parser in portable awk (no jq, no python) -----------------------
# Prints `A <rule>` / `D <rule>` for each string in the top-level permissions.allow / .deny.
# Exits 1 on anything that is not valid JSON, so a broken file can't hide a deny rule.
JSON_AWK='
function fail(m) { if (bad == "") bad = m " at offset " p }
function skipws(  c) {
  while (p <= n) {
    c = substr(s, p, 1)
    if (c == " " || c == "\t" || c == "\n" || c == "\r") p++; else break
  }
}
function jstr(  r, c, e) {
  p++; r = ""
  while (p <= n) {
    c = substr(s, p, 1)
    if (c == "\"") { p++; return r }
    if (c == "\n") { fail("newline in string"); return "" }
    if (c == "\\") {
      e = substr(s, p + 1, 1)
      if (e == "\"" || e == "\\" || e == "/") r = r e
      else if (e == "n" || e == "t" || e == "r" || e == "b" || e == "f") r = r "\\" e
      else if (e == "u") {
        if (substr(s, p + 2, 4) !~ /^[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]$/) {
          fail("bad \\u escape"); return ""
        }
        r = r "\\u" substr(s, p + 2, 4); p += 4
      }
      else { fail("bad escape"); return "" }
      p += 2; continue
    }
    r = r c; p++
  }
  fail("unterminated string"); return ""
}
function value(path,  c, str) {
  skipws()
  if (p > n) { fail("unexpected end"); return }
  c = substr(s, p, 1)
  if (c == "{") obj(path)
  else if (c == "[") arr(path)
  else if (c == "\"") {
    str = jstr()
    if (bad == "" && path == ALLOW) print "A " str
    else if (bad == "" && path == DENY) print "D " str
  }
  else if (substr(s, p, 4) == "true" || substr(s, p, 4) == "null") p += 4
  else if (substr(s, p, 5) == "false") p += 5
  else if (match(substr(s, p), /^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?/)) p += RLENGTH
  else fail("unexpected character")
}
function obj(path,  key, c) {
  p++; skipws()
  if (substr(s, p, 1) == "}") { p++; return }
  while (1) {
    skipws()
    if (substr(s, p, 1) != "\"") { fail("expected a key"); return }
    key = jstr(); if (bad != "") return
    skipws()
    if (substr(s, p, 1) != ":") { fail("expected :"); return }
    p++
    value(path SUBSEP key); if (bad != "") return
    skipws()
    c = substr(s, p, 1)
    if (c == ",") { p++; continue }
    if (c == "}") { p++; return }
    fail("expected , or }"); return
  }
}
function arr(path,  c) {
  p++; skipws()
  if (substr(s, p, 1) == "]") { p++; return }
  while (1) {
    value(path "[]"); if (bad != "") return
    skipws()
    c = substr(s, p, 1)
    if (c == ",") { p++; continue }
    if (c == "]") { p++; return }
    fail("expected , or ]"); return
  }
}
{ s = s $0 "\n" }
END {
  ALLOW = SUBSEP "permissions" SUBSEP "allow[]"
  DENY = SUBSEP "permissions" SUBSEP "deny[]"
  if (substr(s, 1, 3) == "\357\273\277") s = substr(s, 4)
  n = length(s); p = 1; bad = ""
  skipws()
  if (p > n) fail("empty file")
  else { value(""); skipws(); if (bad == "" && p <= n) fail("trailing content") }
  if (bad != "") { print "invalid JSON: " bad > "/dev/stderr"; exit 1 }
}'

allow=()
deny=()
for f in ${settings[@]+"${settings[@]}"}; do
  out="$(awk "$JSON_AWK" "$f")" || die "cannot read settings $f"
  while IFS= read -r line; do
    case "$line" in
      "A "*) allow+=("${line#A }") ;;
      "D "*) deny+=("${line#D }") ;;
    esac
  done <<<"$out"
done

# --- rule matching ---------------------------------------------------------------------------

# glob_match <string> <glob>: `*` matches any text; every other character is literal.
glob_match() {
  local s="$1" g="$2" pat="" c i
  for ((i = 0; i < ${#g}; i++)); do
    c="${g:i:1}"
    if [ "$c" = "*" ]; then pat+="*"; else pat+="\\$c"; fi
  done
  # shellcheck disable=SC2053  # pat is a pattern on purpose; literals are escaped above
  [[ "$s" == $pat ]]
}

# rule_matches <rule> <command>
rule_matches() {
  local rule="$1" cmd="$2" body pre
  [ "$rule" = "Bash" ] && return 0
  case "$rule" in
    "Bash("*")") ;;
    *) return 1 ;;
  esac
  body="${rule#Bash(}"
  body="${body%)}"
  if [[ "$body" == *":*" ]]; then
    pre="${body%:\*}"
    glob_match "$cmd" "$pre" || glob_match "$cmd" "$pre *"
  elif [[ "$body" == *"*"* ]]; then
    glob_match "$cmd" "$body" && return 0
    [[ "$body" == *" *" ]] && glob_match "$cmd" "${body% \*}"
  else
    [ "$cmd" = "$body" ]
  fi
}

any_match() { # any_match <command> <rule>...
  local cmd="$1" r
  shift
  for r in "$@"; do rule_matches "$r" "$cmd" && return 0; done
  return 1
}

# A placeholder becomes a value no rule names literally, so only a rule covering any value
# matches it.
PLACEHOLDER_VALUE="pad0placeholder9value"
instantiate() {
  local c="$1"
  while [[ "$c" =~ \<[^\<\>[:space:]]+\> ]]; do
    c="${c/"${BASH_REMATCH[0]}"/$PLACEHOLDER_VALUE}"
  done
  printf '%s' "$c"
}

# The rule to suggest: the words before the first placeholder, then ` *`; the command itself
# when it has none.
suggest() {
  local cmd="$1" w pre=""
  for w in $cmd; do
    case "$w" in
      *"<"*">"*) printf '%s *' "$pre"; return ;;
    esac
    pre="${pre:+$pre }$w"
  done
  printf '%s' "$cmd"
}

# --- config ----------------------------------------------------------------------------------

[ -f "$config" ] || die "config not found: $config"

trim() { # strip spaces and backticks at both ends
  local v="$1"
  v="${v#"${v%%[![:space:]\`]*}"}"
  v="${v%"${v##*[![:space:]\`]}"}"
  printf '%s' "$v"
}

caps=()
cmds=()
found=0
in_section=0
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  if [[ "$line" =~ ^##[[:space:]] ]]; then
    [ "$in_section" -eq 1 ] && break
    if [[ "$line" =~ ^##[[:space:]]+Git\ moves[[:space:]]*$ ]]; then
      in_section=1
      found=1
    fi
    continue
  fi
  [ "$in_section" -eq 1 ] || continue
  [[ "$line" =~ ^[[:space:]]*\| ]] || continue
  inner="$(trim "$line")"
  inner="${inner#|}"
  inner="${inner%|}"
  IFS='|' read -r -a cells <<<"$inner"
  [ ${#cells[@]} -eq 2 ] || continue
  cap="$(trim "${cells[0]}")"
  cmd="$(trim "${cells[1]}")"
  [ -n "$cap" ] || continue
  [ "$cap" = "Capability" ] && continue
  [[ "$cap" =~ ^:?-+:?$ ]] && continue
  caps+=("$cap")
  cmds+=("$cmd")
done <"$config"

[ "$found" -eq 1 ] || die "no '## Git moves' section in $config"
[ ${#caps[@]} -gt 0 ] || die "the '## Git moves' table in $config has no rows"

# --- check -----------------------------------------------------------------------------------

failed=0
for i in "${!caps[@]}"; do
  cap="${caps[$i]}"
  cmd="${cmds[$i]}"
  concrete="$(instantiate "$cmd")"
  if any_match "$concrete" ${allow[@]+"${allow[@]}"} \
    && ! any_match "$concrete" ${deny[@]+"${deny[@]}"}; then
    continue
  fi
  printf 'MOVES FAIL %s: %s — add "Bash(%s)" to permissions.allow\n' "$cap" "$cmd" "$(suggest "$cmd")"
  failed=1
done

for req in "${REQUIRED[@]}"; do
  present=0
  for cap in "${caps[@]}"; do
    [ "$cap" = "$req" ] && { present=1; break; }
  done
  if [ "$present" -eq 0 ]; then
    printf 'MOVES FAIL %s: missing from the Git moves table in %s\n' "$req" "$config"
    failed=1
  fi
done

[ "$failed" -eq 0 ] || exit 1
echo "MOVES OK"
