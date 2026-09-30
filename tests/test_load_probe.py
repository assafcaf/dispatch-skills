"""E1-T27: load-probe.sh calibrates suite slots and parallelism under load (O43).

`load-probe.sh <N> -- <full suite cmd>` first runs the suite alone, then N copies at once. It
prints `RUN <i> exit <code> <seconds>s` per concurrent run (i = 1..N), then
`LOAD-ONLY FAILURES: <test ids | none>` (ids that failed under load and not alone, read from
pytest-style `FAILED <id> - <reason>` lines), then `SUGGEST slots=<n> parallelism=<n>` last.
The suite here is a fake script that fails `test_flaky` only when another copy runs beside it.
"""
from __future__ import annotations

import re

import pytest

from conftest import BASH

SCRIPT = "load-probe.sh"
RUN_LINE = re.compile(r"^RUN (?P<i>\d+) exit (?P<code>\d+) (?P<secs>[0-9]+(?:\.[0-9]+)?)s$")
SUGGEST = re.compile(r"^SUGGEST slots=(?P<slots>\d+) parallelism=(?P<par>\d+)$")

SUITE = """#!/usr/bin/env bash
d="$1"
mkdir -p "$d/active"
touch "$d/active/$$"
sleep 3
n=$(ls "$d/active" | wc -l)
echo "$n" >> "$d/peaks"
rc=0
if [ "$n" -gt 1 ]; then
  echo "FAILED tests/test_x.py::test_flaky - timed out"
  rc=1
fi
if [ "$2" = broken ]; then
  echo "FAILED tests/test_x.py::test_broken - assert 1 == 2"
  rc=1
fi
rm -f "$d/active/$$"
exit $rc
"""


@pytest.fixture
def probe(run_script, tmp_path):
    """probe(n, mode) -> (result, state dir). mode: `ok`, or `broken` (also always fails one)."""
    state = tmp_path / "suite-state"
    suite = tmp_path / "suite.sh"
    suite.write_text(SUITE, encoding="utf-8", newline="\n")

    def run(n, mode="ok"):
        cmd = [BASH, suite.as_posix(), state.as_posix(), mode]
        return run_script(SCRIPT, str(n), "--", *cmd, cwd=tmp_path), state

    return run


def out_lines(result):
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_o43_n_suites_run_at_once(probe):
    result, state = probe(3)
    assert (state / "peaks").is_file(), (result.stdout, result.stderr)
    peaks = [int(x) for x in (state / "peaks").read_text().split()]
    assert max(peaks) == 3, (peaks, result.stdout, result.stderr)


def test_o43_each_run_is_reported_with_its_exit_code_and_seconds(probe):
    result, _ = probe(3)
    runs = [m for m in (RUN_LINE.match(line) for line in out_lines(result)) if m]
    assert sorted(int(m.group("i")) for m in runs) == [1, 2, 3], result.stdout
    assert all(m.group("code") == "1" for m in runs), result.stdout
    assert all(float(m.group("secs")) >= 3 for m in runs), result.stdout


def test_o43_a_test_failing_only_under_load_is_named_as_load_only(probe):
    result, _ = probe(3)
    assert "LOAD-ONLY FAILURES: tests/test_x.py::test_flaky" in out_lines(result), result.stdout


def test_o43_a_test_failing_alone_too_is_not_a_load_only_failure(probe):
    result, _ = probe(3, "broken")
    load_only = [x for x in out_lines(result) if x.startswith("LOAD-ONLY FAILURES:")]
    assert load_only == ["LOAD-ONLY FAILURES: tests/test_x.py::test_flaky"], result.stdout


def test_o43_a_suite_that_passes_under_load_reports_none_and_suggests_all_n_slots(probe):
    result, _ = probe(1)
    out = out_lines(result)
    assert "LOAD-ONLY FAILURES: none" in out, result.stdout
    m = SUGGEST.match(out[-1]) if out else None
    assert m and int(m.group("slots")) == 1, result.stdout
    assert result.returncode == 0, (result.stdout, result.stderr)


def test_o43_setup_is_told_fewer_slots_than_n_when_load_breaks_tests(probe):
    result, _ = probe(3)
    out = out_lines(result)
    m = SUGGEST.match(out[-1]) if out else None
    assert m, result.stdout
    assert 1 <= int(m.group("slots")) < 3, result.stdout
    assert int(m.group("par")) >= 1, result.stdout


def test_o43_suggest_is_the_last_line_after_load_only_failures(probe):
    result, _ = probe(2)
    names = [
        next((k for k in ("RUN", "LOAD-ONLY", "SUGGEST") if x.startswith(k)), "?")
        for x in out_lines(result)
    ]
    assert names and names[-1] == "SUGGEST", result.stdout
    assert names[-2:-1] == ["LOAD-ONLY"], result.stdout
    assert "RUN" in names, result.stdout
    assert names.index("LOAD-ONLY") > max(i for i, n in enumerate(names) if n == "RUN"), result.stdout


@pytest.mark.parametrize("args", [(), ("0",), ("abc",)])
def test_o43_a_missing_or_non_numeric_n_is_refused_without_a_suggestion(run_script, tmp_path, args):
    result = run_script(SCRIPT, *args, "--", "true", cwd=tmp_path)
    assert result.returncode not in (0, 1), (result.returncode, result.stderr)
    assert "SUGGEST" not in result.stdout, result.stdout


VITEST_SUITE = r"""#!/usr/bin/env bash
d="$1"
mkdir -p "$d/active"
touch "$d/active/$$"
sleep 3
n=$(ls "$d/active" | wc -l)
rc=0
printf ' \033[32m✓\033[39m src/ok.test.ts (2 tests) 12ms\n'
if [ "$n" -gt 1 ]; then
  printf ' \033[31m❯\033[39m src/dial.test.ts (3 tests | 1 failed) 40ms\n'
  printf '\033[41m\033[1m FAIL \033[22m\033[49m src/dial.test.ts\033[2m > \033[22mdial\033[2m > \033[22mturns under load\n'
  rc=1
fi
rm -f "$d/active/$$"
exit $rc
"""


def test_o43_vitest_fail_lines_are_read_as_load_only_failures(run_script, tmp_path):
    """vitest prints ` FAIL  <file> > <suite> > <test>` (in colour) rather than pytest's FAILED."""
    suite = tmp_path / "vitest-suite.sh"
    suite.write_text(VITEST_SUITE, encoding="utf-8", newline="\n")
    state = tmp_path / "vitest-state"
    result = run_script(SCRIPT, "2", "--", BASH, suite.as_posix(), state.as_posix(), cwd=tmp_path)
    out = out_lines(result)
    assert "LOAD-ONLY FAILURES: src/dial.test.ts > dial > turns under load" in out, result.stdout
    m = SUGGEST.match(out[-1]) if out else None
    assert m and int(m.group("slots")) == 1, result.stdout
