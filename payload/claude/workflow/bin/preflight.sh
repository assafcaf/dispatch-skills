#!/usr/bin/env bash
# Prove a run's setup still holds before any agent starts.
#
#   preflight.sh [--config <path>]
#
# Output: one `PREFLIGHT FAIL <check>: <detail>` line per failure, then `PREFLIGHT OK` or
# `PREFLIGHT FAILED <n>`. Exit 0 or 1.
#
# Not implemented yet (E1-T25).
echo "preflight: not implemented" >&2
exit 2
