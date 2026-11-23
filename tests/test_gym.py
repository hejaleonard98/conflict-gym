"""Tests for the gym itself: it builds, each shape conflicts the way it says, and check is right.

They run gym.py in a folder of their own, so nothing here touches the gym you are drilling in.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
GYM = ROOT / "gym.py"
LOG = "workout_log.py"


def gym(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run gym.py in a copy of the project, in a folder of its own."""
    return subprocess.run(
        [sys.executable, "gym.py", *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=60,
    )


def git(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one git command in the drill repository."""
    return subprocess.run(
        ["git", "-C", str(directory / "drill"), *arguments],
        capture_output=True,
        text=True,
        timeout=60,
    )


def text(directory: Path, name: str) -> str:
    """One file of the drill, as it is now."""
    return (directory / "drill" / name).read_text()


def settle(directory: Path, name: str, wanted: str) -> None:
    """Resolve one file by writing what it should say, and stage it."""
    (directory / "drill" / name).write_text(wanted)
    git(directory, "add", name)


def a_built_gym(tmp_path: Path) -> Path:
    """A copy of gym.py in a folder of its own, with the gym built."""
    shutil.copy(GYM, tmp_path / "gym.py")
    result = gym(tmp_path, "reset")
    assert result.returncode == 0, "gym.py reset failed:\n" + result.stderr.strip()
    return tmp_path


def a_round(tmp_path: Path, shape: str) -> tuple[Path, subprocess.CompletedProcess[str]]:
    """A built gym with a round of one shape set up and its merge started."""
    directory = a_built_gym(tmp_path)
    result = gym(directory, "next", shape)
    assert result.returncode == 0, f"gym.py next {shape} failed:\n{result.stdout}{result.stderr}"
    branch = result.stdout.split("git merge ")[-1].strip()
    return directory, git(directory, "merge", branch)


def resolve_one_line(directory: Path) -> None:
    """Shape 1 settled by keeping main's wording, and committed."""
    settle(directory, LOG, text(directory, LOG).replace(
        '<<<<<<< HEAD\n    return f"You logged {count} sets"\n=======\n'
        '    return f"{count} sets done"\n>>>>>>> their-wording\n',
        '    return f"You logged {count} sets"\n',
    ))
    git(directory, "commit", "-q", "--no-edit")


def test_reset_builds_main_with_one_commit(tmp_path: Path) -> None:
    """The gym starts on main, clean, with the workout log and nothing to merge."""
    directory = a_built_gym(tmp_path)
    assert (directory / "drill" / LOG).exists(), f"reset left no {LOG} in drill/."
    on = git(directory, "branch", "--show-current").stdout.strip()
    assert on == "main", f"reset left the gym on {on!r}; the drill starts on main."
    log = git(directory, "log", "--oneline").stdout.splitlines()
    assert len(log) == 1, f"reset left {len(log)} commits; a fresh gym has one."


def test_shape_1_is_one_line_changed_two_ways(tmp_path: Path) -> None:
    """One conflict, on the summary line, and the program does not run until it is settled."""
    directory, merge = a_round(tmp_path, "1")
    assert merge.returncode != 0, "the shape 1 merge went through without a conflict."
    assert text(directory, LOG).count("<<<<<<<") == 1, "shape 1 is one conflict."
    run = subprocess.run([sys.executable, LOG], cwd=directory / "drill", capture_output=True)
    assert run.returncode != 0, "the program ran with marker lines still in it."


def test_shape_2_keeps_both_additions(tmp_path: Path) -> None:
    """Two functions added in the same place: keeping both is clear, keeping one is not."""
    directory, merge = a_round(tmp_path, "2")
    assert merge.returncode != 0, "the shape 2 merge went through without a conflict."
    conflicted = text(directory, "routine.py")
    assert "def rest()" in conflicted and "def cooldown()" in conflicted
    one_side = conflicted.split("=======")[0].replace("<<<<<<< HEAD\n", "")
    settle(directory, "routine.py", one_side)
    git(directory, "commit", "-q", "--no-edit")
    result = gym(directory, "check")
    assert result.returncode != 0, "check accepted a routine.py with no cooldown in it."
    assert "cooldown" in result.stdout, "check did not say which function went missing."


def test_shape_3_has_no_markers_and_either_answer_is_clear(tmp_path: Path) -> None:
    """modify/delete leaves the file whole; git add and git rm both settle it."""
    for settle_with in ["add", "rm"]:
        (tmp_path / settle_with).mkdir()
        directory, merge = a_round(tmp_path / settle_with, "3")
        assert "CONFLICT (modify/delete)" in merge.stdout, merge.stdout
        assert "<<<<<<<" not in text(directory, "notes.md"), "shape 3 put markers in notes.md."
        git(directory, settle_with, "notes.md")
        git(directory, "commit", "-q", "--no-edit")
        result = gym(directory, "check")
        assert result.returncode == 0, f"check refused git {settle_with}:\n{result.stdout}"


def test_shape_4_conflicts_once_and_merges_the_rest(tmp_path: Path) -> None:
    """Only the summary line conflicts; the three docstrings arrive already merged."""
    directory, merge = a_round(tmp_path, "4")
    assert merge.returncode != 0, "the shape 4 merge went through without a conflict."
    conflicted = text(directory, LOG)
    assert conflicted.count("<<<<<<<") == 1, "shape 4 is one conflict among clean changes."
    for docstring in ["Read the records", "Write the records", "Put one record"]:
        assert docstring in conflicted, f"the clean change {docstring!r} was not merged."


def test_shape_4_catches_a_file_retyped_from_one_side(tmp_path: Path) -> None:
    """Retyping the whole file from main's version undoes what git merged correctly."""
    directory, _ = a_round(tmp_path, "4")
    ours = git(directory, "show", "main:" + LOG).stdout
    settle(directory, LOG, ours)
    git(directory, "commit", "-q", "--no-edit")
    result = gym(directory, "check")
    assert result.returncode != 0, "check accepted a file that lost the branch's clean changes."
    assert "Write the records" in result.stdout, result.stdout


def test_check_says_no_while_the_merge_is_open(tmp_path: Path) -> None:
    """Half way through a merge, check does not say the round is clear."""
    directory, _ = a_round(tmp_path, "1")
    result = gym(directory, "check")
    assert result.returncode != 0, "check said the round was clear in the middle of a merge."
    assert "marker lines" in result.stdout, "check did not mention the marker lines:\n" + result.stdout


def test_check_says_yes_after_the_resolution(tmp_path: Path) -> None:
    """Settled, the markers gone, the merge committed: the round is clear."""
    directory, _ = a_round(tmp_path, "1")
    resolve_one_line(directory)
    result = gym(directory, "check")
    assert result.returncode == 0, "check did not accept a right resolution:\n" + result.stdout


def test_next_refuses_while_a_merge_is_open(tmp_path: Path) -> None:
    """A new round is not stacked on top of one that is half done."""
    directory, _ = a_round(tmp_path, "1")
    result = gym(directory, "next")
    assert result.returncode != 0, "next set up a round in the middle of a merge."


def test_rounds_stack_up_and_the_shapes_come_round_in_order(tmp_path: Path) -> None:
    """Three rounds finished leave three merge commits, and next goes 1, 2, 3."""
    directory = a_built_gym(tmp_path)
    for shape, branch in [("1", "their-wording"), ("2", "add-cooldown"), ("3", "drop-notes")]:
        result = gym(directory, "next")
        assert f"shape {shape}" in result.stdout, result.stdout
        git(directory, "merge", branch)
        if shape == "1":
            resolve_one_line(directory)
            continue
        if shape == "2":
            settle(directory, "routine.py", "\n".join(
                line for line in text(directory, "routine.py").splitlines()
                if not line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
            ) + "\n")
        if shape == "3":
            git(directory, "add", "notes.md")
        git(directory, "commit", "-q", "--no-edit")
        check = gym(directory, "check")
        assert check.returncode == 0, f"round {shape} was not clear:\n{check.stdout}"
    merges = git(directory, "rev-list", "--merges", "--count", "HEAD").stdout.strip()
    assert merges == "3", f"drill/ holds {merges} merge commits after three rounds."


def test_the_conflict_is_the_same_every_time(tmp_path: Path) -> None:
    """Build, merge, wreck it, build again: the same file comes out."""
    directory, _ = a_round(tmp_path, "1")
    first = text(directory, LOG)
    (directory / "drill" / LOG).write_text("whatever I felt like")
    gym(directory, "reset")
    gym(directory, "next", "1")
    git(directory, "merge", "their-wording")
    assert text(directory, LOG) == first, "the second time round the gym made another conflict."


def test_reset_works_in_the_middle_of_a_broken_merge(tmp_path: Path) -> None:
    """You can always start again, even with a merge open and the file in pieces."""
    directory, _ = a_round(tmp_path, "4")
    result = gym(directory, "reset")
    assert result.returncode == 0, "gym.py reset failed mid-merge:\n" + result.stderr.strip()
    assert not (directory / "drill" / ".git" / "MERGE_HEAD").exists(), "reset left the merge open."
    assert "<<<<<<<" not in text(directory, LOG), "reset left the marker lines in the file."
