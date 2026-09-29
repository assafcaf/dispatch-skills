#!/usr/bin/env bash
# Lint for this repo: every shell script parses, every Python file compiles.
# Exit 0 clean, 1 on the first file that fails. shellcheck is not assumed to be installed.
set -u
cd "$(dirname "$0")/.." || exit 1

status=0
checked=0
# A plain for loop: process substitution (< <(...)) is unavailable in some Git Bash builds.
for f in $(git ls-files '*.sh'); do
  bash -n "$f" || { echo "lint: bash -n failed: $f"; status=1; }
  checked=$((checked + 1))
done
[ "$checked" -gt 0 ] || { echo "lint: no shell scripts found"; status=1; }

python -m compileall -q dispatch_skills tests >/dev/null || { echo "lint: python compile failed"; status=1; }

[ "$status" -eq 0 ] && echo "lint: ok ($checked shell scripts)"
exit "$status"
