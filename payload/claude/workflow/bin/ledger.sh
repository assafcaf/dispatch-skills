#!/usr/bin/env bash
# Update a local ticket in the main checkout's ledger, from any worktree or subdirectory.
#
#   ledger.sh <KEY> status <todo|doing|review|done> "<comment>"
#   ledger.sh <KEY> comment "<text>"
#
# The ticket is <main checkout>/.work/tickets/<EPIC>/<KEY>.md, or .../<EPIC>/epic.md when KEY is
# an epic key (E<n>). `status` rewrites the frontmatter `status:` line; both forms append
# `- <yyyy-mm-dd>: <comment>` under `## Log`, creating the heading when missing.
#
# Last stdout line: `LEDGER OK <KEY> <status>`. Exit 1 with `LEDGER FAIL <KEY>: <why>` on
# stdout. Exit 64: usage.

set -uo pipefail

usage() {
  echo 'usage: ledger.sh <KEY> status <todo|doing|review|done> "<comment>" | ledger.sh <KEY> comment "<text>"' >&2
  exit 64
}
fail() { echo "LEDGER FAIL $key: $1"; exit 1; }

[ $# -ge 3 ] || usage
key="$1"; verb="$2"
[ -n "$key" ] || usage
case "$verb" in
  status) [ $# -eq 4 ] || usage; to="$3"; text="$4" ;;
  comment) [ $# -eq 3 ] || usage; to=""; text="$3" ;;
  *) usage ;;
esac

if [ "$verb" = status ]; then
  case "$to" in todo|doing|review|done) ;; *) fail "invalid status '$to' (todo|doing|review|done)" ;; esac
fi

top="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not a git repository"
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || fail "cannot find the main checkout"

epic="${key%%-T*}"
if [ "$epic" = "$key" ]; then file="$main/.work/tickets/$epic/epic.md"
else file="$main/.work/tickets/$epic/$key.md"; fi
[ -f "$file" ] || fail "no ticket at $file"

tmp="$file.tmp.$$"
trap 'rm -f "$tmp"' EXIT
line="- $(date +%Y-%m-%d): $text"

# Rewrite the first frontmatter `status:` line (status verb only), keep everything else.
awk -v to="$to" '
  BEGIN { fm = 0; done = 0 }
  { sub(/\r$/, "") }
  NR == 1 && $0 == "---" { fm = 1; print; next }
  fm == 1 && $0 == "---" { fm = 2 }
  fm == 1 && !done && to != "" && /^status:/ { print "status: " to; done = 1; next }
  { print }
' "$file" >"$tmp" || fail "cannot read $file"

# Make sure the file ends in a newline, then find or create the Log heading.
[ -z "$(tail -c1 "$tmp")" ] || printf '\n' >>"$tmp"
if ! grep -q '^## Log[[:space:]]*$' "$tmp"; then
  printf '\n## Log\n' >>"$tmp"
fi
printf '%s\n' "$line" >>"$tmp"

cat "$tmp" >"$file" || fail "cannot write $file"

cur="$(awk 'NR>1 && /^---$/ {exit} /^status:/ {sub(/^status:[ \t]*/, ""); sub(/[ \t#].*$/, ""); print; exit}' "$file")"
echo "LEDGER OK $key $cur"
