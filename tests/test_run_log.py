"""O6: from any worktree, run-log.sh appends to the main checkout's run log, never rewrites it."""
from pathlib import Path

RUN = "E1-20260929"


def progress(main: Path, run: str = RUN) -> Path:
    return main / ".work" / "runs" / run / "progress.md"


def test_o6_line_from_main_checkout_lands_in_new_progress_file(repo, run_script):
    result = run_script("run-log.sh", RUN, "wave 1 started", cwd=repo)

    assert result.returncode == 0, result.stderr
    assert progress(repo).read_bytes() == b"wave 1 started\n"


def test_o6_line_from_linked_worktree_lands_in_main_checkout(repo, worktree, run_script):
    wt = worktree(repo, "E1-T2")

    result = run_script("run-log.sh", RUN, "E1-T2 red proven", cwd=wt)

    assert result.returncode == 0, result.stderr
    assert progress(repo).read_bytes() == b"E1-T2 red proven\n"
    assert not (wt / ".work").exists()


def test_o6_line_from_worktree_subdirectory_lands_in_main_checkout(repo, worktree, run_script):
    wt = worktree(repo, "E1-T3")
    sub = wt / "deep" / "er"
    sub.mkdir(parents=True)

    result = run_script("run-log.sh", RUN, "from a subdirectory", cwd=sub)

    assert result.returncode == 0, result.stderr
    assert progress(repo).read_bytes() == b"from a subdirectory\n"
    assert not (wt / ".work").exists()
    assert not (sub / ".work").exists()


def test_o6_line_from_main_checkout_subdirectory_lands_at_its_root(repo, run_script):
    sub = repo / "docs" / "decisions"
    sub.mkdir(parents=True)

    result = run_script("run-log.sh", RUN, "from main subdir", cwd=sub)

    assert result.returncode == 0, result.stderr
    assert progress(repo).read_bytes() == b"from main subdir\n"
    assert not (sub / ".work").exists()


def test_o6_existing_log_content_is_kept_and_line_appended(repo, worktree, run_script):
    log = progress(repo)
    log.parent.mkdir(parents=True)
    log.write_bytes(b"# Run E1-20260929\n\nplanner: 3 tasks\n")
    wt = worktree(repo, "E1-T4")

    result = run_script("run-log.sh", RUN, "E1-T4 doing", cwd=wt)

    assert result.returncode == 0, result.stderr
    assert log.read_bytes() == b"# Run E1-20260929\n\nplanner: 3 tasks\nE1-T4 doing\n"


def test_o6_lines_from_several_worktrees_accumulate_in_call_order(repo, worktree, run_script):
    a = worktree(repo, "E1-T5")
    b = worktree(repo, "E1-T6")

    for cwd, line in [(a, "one"), (b, "two"), (repo, "three"), (a, "four")]:
        result = run_script("run-log.sh", RUN, line, cwd=cwd)
        assert result.returncode == 0, result.stderr

    assert progress(repo).read_bytes() == b"one\ntwo\nthree\nfour\n"


def test_o6_separate_run_ids_write_separate_logs(repo, run_script):
    assert run_script("run-log.sh", "run-a", "for a", cwd=repo).returncode == 0
    assert run_script("run-log.sh", "run-b", "for b", cwd=repo).returncode == 0

    assert progress(repo, "run-a").read_bytes() == b"for a\n"
    assert progress(repo, "run-b").read_bytes() == b"for b\n"


def test_o6_line_is_written_literally_without_expansion(repo, run_script):
    line = "-e wave 2: E1-T7 -> done, 50% $HOME `whoami` \\t %s"

    result = run_script("run-log.sh", RUN, line, cwd=repo)

    assert result.returncode == 0, result.stderr
    assert progress(repo).read_text(encoding="utf-8") == line + "\n"


def test_o6_no_arguments_is_usage_error_and_writes_nothing(repo, run_script):
    result = run_script("run-log.sh", cwd=repo)

    assert result.returncode == 64
    assert not (repo / ".work").exists()


def test_o6_run_id_without_line_is_usage_error_and_writes_nothing(repo, run_script):
    result = run_script("run-log.sh", RUN, cwd=repo)

    assert result.returncode == 64
    assert not (repo / ".work").exists()


def test_o6_empty_run_id_is_usage_error_and_writes_nothing(repo, run_script):
    result = run_script("run-log.sh", "", "orphan line", cwd=repo)

    assert result.returncode == 64
    assert not (repo / ".work").exists()
