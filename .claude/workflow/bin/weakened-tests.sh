#!/usr/bin/env bash
# Fail if a commit range weakens the test suite: adds a skip, xfail or TODO, or removes a test
# function without re-adding one of the same name (a moved or re-decorated test is fine).
#
#   weakened-tests.sh <base> <head>
#
# Patterns default to pytest; override for another stack:
#   WEAK_ADDED   ERE matched against added lines   (default: skip/xfail markers, pytest.skip(, TODO)
#   TEST_DEF     sed ERE capturing a test name in \2 (default: python `def test_*`)
#
# Exit 0: nothing weakened. Exit 1: offending lines printed. Exit 64: usage.

set -uo pipefail

if [ $# -ne 2 ]; then
  echo "usage: weakened-tests.sh <base> <head>" >&2
  exit 64
fi
base="$1"
head="$2"
added_re="${WEAK_ADDED:-(pytest\.mark\.(skip|xfail)|pytest\.skip\(|TODO)}"
def_re="${TEST_DEF:-[[:space:]]*(async )?def (test_[A-Za-z0-9_]+)}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git diff -U0 "$base" "$head" >"$tmp/diff" || exit 64
rc=0

grep -E '^\+' "$tmp/diff" | grep -vE '^\+\+\+ ' | grep -E "$added_re" >"$tmp/added" || true
if [ -s "$tmp/added" ]; then
  echo "weakened-tests: added skip/xfail/TODO:"
  sed 's/^/  /' "$tmp/added"
  rc=1
fi

sed -nE "s/^-${def_re}.*/\\2/p" "$tmp/diff" | sort -u >"$tmp/removed"
sed -nE "s/^\\+${def_re}.*/\\2/p" "$tmp/diff" | sort -u >"$tmp/readded"
comm -23 "$tmp/removed" "$tmp/readded" >"$tmp/gone"
if [ -s "$tmp/gone" ]; then
  echo "weakened-tests: removed tests:"
  sed 's/^/  /' "$tmp/gone"
  rc=1
fi

[ "$rc" -eq 0 ] && echo "weakened-tests: ok (${base:0:8}..${head:0:8})"
exit "$rc"
