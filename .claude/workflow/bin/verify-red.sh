#!/usr/bin/env bash
# Prove a task's tests were red: check out <commit> in a throwaway worktree, run the test
# command there, and pass only if it exits with an expected red code.
#
#   verify-red.sh [--setup '<cmd>'] [--expect 1[,<code>...]] <commit> -- <test command...>
#   verify-red.sh --setup 'uv sync -q' abc1234 -- uv run pytest -q tests/test_x.py::test_y
#
# Exit 0: red as expected. Exit 1: not red (passed, or failed the wrong way). Exit 64: usage.
# The last 40 lines of the test output are printed either way, so the caller can quote them.

set -uo pipefail

setup=""
expect="1"
while [ $# -gt 0 ]; do
  case "$1" in
    --setup) setup="$2"; shift 2 ;;
    --expect) expect="$2"; shift 2 ;;
    --) shift; break ;;
    -*) echo "verify-red: unknown option $1" >&2; exit 64 ;;
    *) commit="$1"; shift ;;
  esac
done
if [ -z "${commit:-}" ] || [ $# -eq 0 ]; then
  echo "usage: verify-red.sh [--setup '<cmd>'] [--expect 1[,<code>...]] <commit> -- <test command...>" >&2
  exit 64
fi

sha="$(git rev-parse --verify --quiet "${commit}^{commit}")" || {
  echo "verify-red: no such commit: $commit" >&2
  exit 64
}

dir="$(mktemp -d)/red-${sha:0:8}"
cleanup() { git worktree remove --force "$dir" >/dev/null 2>&1 || true; }
trap cleanup EXIT

git worktree add --detach --quiet "$dir" "$sha" || {
  echo "verify-red: could not create a worktree at $sha" >&2
  exit 64
}

out="$dir/.verify-red.log"
(
  cd "$dir" || exit 97
  if [ -n "$setup" ]; then
    bash -c "$setup" || exit 98
  fi
  "$@"
) >"$out" 2>&1
code=$?

tail -n 40 "$out"
echo "---"
case "$code" in
  97|98) echo "verify-red: setup failed at ${sha:0:8} (exit $code)"; exit 1 ;;
esac
if [[ ",$expect," == *",$code,"* ]]; then
  echo "RED OK: exit $code at ${sha:0:8}"
  exit 0
fi
echo "NOT RED: exit $code at ${sha:0:8}, expected one of: $expect"
exit 1
