#!/usr/bin/env bash
# Run N copies of the full suite at once and report what load changes.
#
#   load-probe.sh <N> -- <full suite cmd>
#
# Runs the suite once alone, then N copies at once. Prints `RUN <i> exit <code> <seconds>s` for
# each concurrent copy (i = 1..N), `LOAD-ONLY FAILURES: <ids | none>` (test ids that failed under
# load and not alone, read from pytest-style `FAILED <id> - ...` lines), then last
# `SUGGEST slots=<n> parallelism=<n>`. Exit 0 when load changed nothing, 1 when it broke a test,
# 64 on bad usage (no SUGGEST line).

set -uo pipefail

n="${1:-}"
if ! [[ "$n" =~ ^[0-9]+$ ]] || [ "$((10#$n))" -lt 1 ] || [ "${2:-}" != "--" ] || [ $# -lt 3 ]; then
  echo "usage: load-probe.sh <N> -- <full suite cmd>" >&2
  exit 64
fi
n=$((10#$n))
shift 2

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

now() { if [ -n "${EPOCHREALTIME:-}" ]; then echo "${EPOCHREALTIME/,/.}"; else date +%s; fi; }

failed_ids() { sed -n 's/^FAILED \([^ ]*\).*/\1/p' "$@" | tr -d '\r' | sort -u; }

"$@" >"$tmp/alone.out" 2>&1 </dev/null

for ((i = 1; i <= n; i++)); do
  (
    start="$(now)"
    "$@" >"$tmp/run$i.out" 2>&1 </dev/null
    rc=$?
    end="$(now)"
    awk -v s="$start" -v e="$end" -v rc="$rc" -v i="$i" \
      'BEGIN { printf "RUN %d exit %d %.1fs\n", i, rc, e - s }' >"$tmp/run$i.res"
  ) &
done
wait

for ((i = 1; i <= n; i++)); do cat "$tmp/run$i.res"; done

failed_ids "$tmp/alone.out" >"$tmp/alone.ids"
for ((i = 1; i <= n; i++)); do
  failed_ids "$tmp/run$i.out"
done | sort -u | while IFS= read -r id; do
  grep -Fxq -- "$id" "$tmp/alone.ids" || echo "$id"
done >"$tmp/load.ids"
load_only="$(paste -sd' ' "$tmp/load.ids")"

if [ -z "$load_only" ]; then
  echo "LOAD-ONLY FAILURES: none"
  echo "SUGGEST slots=$n parallelism=$n"
  exit 0
fi
slots=$((n - 1)); [ "$slots" -ge 1 ] || slots=1
echo "LOAD-ONLY FAILURES: $load_only"
echo "SUGGEST slots=$slots parallelism=$slots"
exit 1
