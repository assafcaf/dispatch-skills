#!/usr/bin/env bash
# Lint for this repo: every shell script parses, every Python file compiles.
# Exit 0 clean, 1 on the first file that fails. shellcheck is not assumed to be installed.
set -u
cd "$(dirname "$0")/.." || exit 1

status=0
while IFS= read -r f; do
  bash -n "$f" || { echo "lint: bash -n failed: $f"; status=1; }
done < <(git ls-files '*.sh')

python -m compileall -q dispatch_skills tests >/dev/null || { echo "lint: python compile failed"; status=1; }

[ "$status" -eq 0 ] && echo "lint: ok"
exit "$status"
