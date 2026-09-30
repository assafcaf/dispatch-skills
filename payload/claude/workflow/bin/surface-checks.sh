#!/usr/bin/env bash
# surface-checks.sh [--config <path>]
# Runs each non-empty `Automated check` cell of the config's `## Surfaces` table in the current
# directory. Prints `SURFACES FAIL <surface>` per failure; last line `SURFACES OK` only if none.
# Exit 0 (all green or no Surfaces) or 1.
set -u
config=".claude/workflow/config.md"
if [ "${1:-}" = "--config" ]; then config="${2:?--config needs a path}"; fi

trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }
unquote() { local s; s="$(trim "$1")"; case "$s" in \`*\`) s="${s#\`}"; s="${s%\`}";; esac; printf '%s' "$s"; }

fail=0
if [ -f "$config" ]; then
  in=0; col=-1
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      "## Surfaces"*) in=1; continue;;
      "## "*) in=0;;
    esac
    [ "$in" = 1 ] || continue
    case "$line" in "|"*) ;; *) continue;; esac
    IFS='|' read -r -a cells <<< "$line"
    if [ "$col" -lt 0 ]; then
      for i in "${!cells[@]}"; do
        [ "$(trim "${cells[$i]}")" = "Automated check" ] && col=$i
      done
      continue
    fi
    case "$(trim "${cells[1]:-}")" in -*|:*) continue;; esac
    check="$(unquote "${cells[$col]:-}")"
    [ -n "$check" ] || continue
    name="$(unquote "${cells[1]:-}")"
    if ! bash -c "$check" >&2 </dev/null; then
      echo "SURFACES FAIL $name"
      fail=1
    fi
  done < "$config"
fi
[ "$fail" = 0 ] && echo "SURFACES OK"
exit "$fail"
