"""O26: verify-red.sh links the configured dependency directory when the lockfile is unchanged.

Runs the real script in a fixture repo. The test command it runs reports what the throwaway
worktree looked like (was setup run, was the dependency directory visible) on stdout, then
exits 1, so the script's own exit code is 0 (red as expected) and its output carries the facts.
"""
from __future__ import annotations

from pathlib import Path

from conftest import git

PROBE = (
    'echo "MARKER=$(cat deps/marker.txt 2>/dev/null)"; '
    'echo "SETUP=$(test -e setup-ran && echo yes || echo no)"; '
    "exit 1"
)


def commit_file(repo: Path, name: str, text: str, msg: str) -> str:
    (repo / name).write_text(text, encoding="utf-8")
    git("add", name, cwd=repo)
    git("commit", "-q", "-m", msg, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def prepare(repo: Path) -> Path:
    """main gets a lockfile; the invoking checkout gets an untracked dependency directory."""
    commit_file(repo, "lock.txt", "v1\n", "add lockfile")
    deps = repo / "deps"
    deps.mkdir()
    (deps / "marker.txt").write_text("installed\n", encoding="utf-8")
    return deps


def red_commit_on_branch(repo: Path, lock_text: str | None) -> str:
    """A commit on a side branch that adds a test file, and rewrites the lockfile if asked."""
    git("checkout", "-q", "-b", "task", cwd=repo)
    if lock_text is not None:
        (repo / "lock.txt").write_text(lock_text, encoding="utf-8")
        git("add", "lock.txt", cwd=repo)
    sha = commit_file(repo, "test_x.txt", "t\n", "test: red")
    git("checkout", "-q", "main", cwd=repo)
    return sha


def verify(run_script, repo, sha, *extra):
    return run_script(
        "verify-red.sh",
        "--setup", "touch setup-ran",
        *extra,
        sha, "--", "bash", "-c", PROBE,
        cwd=repo,
    )


def test_o26_unchanged_lockfile_links_deps_and_skips_setup(repo, run_script):
    prepare(repo)
    sha = red_commit_on_branch(repo, None)
    r = verify(run_script, repo, sha, "--deps", "deps", "--lockfile", "lock.txt")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MARKER=installed" in r.stdout
    assert "SETUP=no" in r.stdout


def test_o26_changed_lockfile_runs_setup_and_does_not_link_deps(repo, run_script):
    prepare(repo)
    sha = red_commit_on_branch(repo, "v2\n")
    r = verify(run_script, repo, sha, "--deps", "deps", "--lockfile", "lock.txt")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SETUP=yes" in r.stdout
    assert "MARKER=\n" in r.stdout or r.stdout.rstrip().endswith("MARKER=") or "MARKER=installed" not in r.stdout


def test_o26_base_option_overrides_merge_base_when_comparing_lockfiles(repo, run_script):
    prepare(repo)
    git("checkout", "-q", "-b", "task", cwd=repo)
    (repo / "lock.txt").write_text("v2\n", encoding="utf-8")
    git("add", "lock.txt", cwd=repo)
    base = commit_file(repo, "a.txt", "a\n", "bump lockfile")
    sha = commit_file(repo, "test_x.txt", "t\n", "test: red")
    git("checkout", "-q", "main", cwd=repo)
    # against the merge-base (main, lock v1) the lockfile changed; against --base it did not
    changed = verify(run_script, repo, sha, "--deps", "deps", "--lockfile", "lock.txt")
    assert "SETUP=yes" in changed.stdout, changed.stdout + changed.stderr
    same = verify(run_script, repo, sha, "--deps", "deps", "--lockfile", "lock.txt", "--base", base)
    assert same.returncode == 0, same.stdout + same.stderr
    assert "SETUP=no" in same.stdout
    assert "MARKER=installed" in same.stdout


def test_o26_linked_deps_survive_the_throwaway_worktree_cleanup(repo, run_script):
    deps = prepare(repo)
    sha = red_commit_on_branch(repo, None)
    r = verify(run_script, repo, sha, "--deps", "deps", "--lockfile", "lock.txt")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (deps / "marker.txt").read_text(encoding="utf-8") == "installed\n"


def test_o26_deps_without_lockfile_is_a_usage_error(repo, run_script):
    prepare(repo)
    sha = red_commit_on_branch(repo, None)
    r = verify(run_script, repo, sha, "--deps", "deps")
    assert r.returncode == 64, r.stdout + r.stderr
    assert "lockfile" in r.stderr.lower()
