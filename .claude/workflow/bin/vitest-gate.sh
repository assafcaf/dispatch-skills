#!/usr/bin/env bash
# Run vitest and map its result onto pytest's exit codes, so verify-red.sh can tell a genuine
# test failure (red) from a suite that never ran (not red). vitest exits 1 for both cases;
# the whole red gate depends on telling them apart.
#
# A worked example for /setup-workflow's stack step: a project on vitest can use this as-is;
# a project on another runner that doesn't split "failed" from "didn't run" across exit codes
# (jest, go test, cargo test, …) should copy this file and adapt the two `grep` patterns below
# to that runner's own wording for "no tests found" and "failed to load a file".
#
#   vitest-gate.sh [<vitest args...>]
#   vitest-gate.sh src/domain/prefill.test.ts src/domain/dial.test.ts
#
# Exit 0: tests ran, all passed.
# Exit 1: tests ran, at least one failed and nothing failed to load  -> a real red.
# Exit 2: no test files matched, a suite failed to import, or vitest itself errored.
#
# Set VITEST to override the runner (used by this repo's own tests of this script).

set -uo pipefail

runner="${VITEST:-npx vitest}"

out="$($runner run --reporter=verbose "$@" 2>&1)"
code=$?

printf '%s\n' "$out"
echo "---"

# vitest colours its summary even when its output is a pipe (on Windows tinyrainbow forces
# colour unless NO_COLOR is set), and the escape codes land between the anchors the patterns
# below match -- "\e[2m      Tests \e[22m \e[1m\e[31m17 failed". Match on a stripped copy so
# the verdict is the same everywhere; the caller still sees the original, colours and all.
esc=$(printf '\033')
plain="$(printf '%s' "$out" | sed -E "s/${esc}\[[0-9;?]*[a-zA-Z]//g")"

if printf '%s' "$plain" | grep -qE 'No test files found'; then
  echo "vitest-gate: no test files matched (exit 2)"
  exit 2
fi

if printf '%s' "$plain" | grep -qE 'Failed to load|Unhandled Error|Cannot find module|Tests[[:space:]]+no tests'; then
  echo "vitest-gate: a suite failed to load, so no assertion ran (exit 2)"
  exit 2
fi

if printf '%s' "$plain" | grep -qE '^[[:space:]]*Tests[[:space:]]+.*[0-9]+ failed'; then
  echo "vitest-gate: tests ran and failed (exit 1)"
  exit 1
fi

if [ "$code" -eq 0 ]; then
  echo "vitest-gate: tests ran and passed (exit 0)"
  exit 0
fi

echo "vitest-gate: vitest exited $code without a test-failure summary (exit 2)"
exit 2
