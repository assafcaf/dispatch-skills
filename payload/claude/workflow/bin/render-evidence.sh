#!/usr/bin/env bash
# Write a merged task's evidence file, log its run line and print its PR-table row.
#
#   render-evidence.sh --run <id> --key <KEY> --red <sha> --merge <sha> --outcomes "<O ids>"
#       --red-result "<cmd -> result>" --green-result "<cmd -> result>"
#       [--files-outside "<paths>"] [--rulings "<text>"]
#
# Writes <main checkout>/.work/runs/<id>/<KEY>.md, appends "<KEY>: done (red <sha7>, merge
# <sha7>)" through run-log.sh, then prints that line and the PR row "| <KEY> | <O ids> |
# <merge sha7> |" (last). Values are written literally.
#
# Exit 0: done. Exit 1: not in a git repository or a write failed. Exit 64: usage; nothing written.

set -uo pipefail

usage() { echo "usage: render-evidence.sh --run <id> --key <KEY> --red <sha> --merge <sha> --outcomes <ids> --red-result <text> --green-result <text> [--files-outside <paths>] [--rulings <text>]" >&2; exit 64; }

run= key= red= merge= outcomes= red_result= green_result= files_outside= rulings=
seen=" "
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || usage
  case "$1" in
    --run) run="$2" ;;
    --key) key="$2" ;;
    --red) red="$2" ;;
    --merge) merge="$2" ;;
    --outcomes) outcomes="$2" ;;
    --red-result) red_result="$2" ;;
    --green-result) green_result="$2" ;;
    --files-outside) files_outside="$2" ;;
    --rulings) rulings="$2" ;;
    *) usage ;;
  esac
  seen="$seen$1 "
  shift 2
done
for f in run key red merge outcomes red-result green-result; do
  case "$seen" in *" --$f "*) ;; *) usage ;; esac
done
for v in "$run" "$key" "$red" "$merge" "$outcomes" "$red_result" "$green_result"; do
  [ -n "$v" ] || usage
done

top="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "render-evidence: not a git repository" >&2; exit 1; }
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || {
  echo "render-evidence: cannot find the main checkout" >&2; exit 1; }

dir="$main/.work/runs/$run"
mkdir -p "$dir" || { echo "render-evidence: cannot create $dir" >&2; exit 1; }

{
  printf '# %s\n\n' "$key"
  printf -- '- Outcomes: %s\n' "$outcomes"
  printf -- '- Red commit: %s\n' "$red"
  printf -- '- Merge commit: %s\n' "$merge"
  printf -- '- Red gate: %s\n' "$red_result"
  printf -- '- Green gate: %s\n' "$green_result"
  [ -z "$files_outside" ] || printf -- '- Files outside the ticket: %s\n' "$files_outside"
  [ -z "$rulings" ] || printf -- '- Rulings: %s\n' "$rulings"
} >"$dir/$key.md" || { echo "render-evidence: cannot write $dir/$key.md" >&2; exit 1; }

line="$key: done (red ${red:0:7}, merge ${merge:0:7})"
bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$bin/run-log.sh" "$run" "$line" || exit 1
printf '%s\n' "$line"
printf '| %s | %s | %s |\n' "$key" "$outcomes" "${merge:0:7}"
