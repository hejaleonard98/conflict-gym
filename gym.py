"""The conflict gym: a merge conflict whenever you ask for one, in four shapes.

    uv run gym.py reset       build the gym, or knock it down and build it again
    uv run gym.py next        set up the next round; the shapes come round in order
    uv run gym.py next 3      set up a round of shape 3
    uv run gym.py check       look at how you resolved this round and say what is still wrong

`reset` makes a small git repository in drill/ holding a workout log. `next` puts two commits on
top of it, one on `main` and one on a branch beside it, that disagree. You are on `main`, and
merging the branch in conflicts, the same way every time.

The four shapes:

    1  one line, changed two ways               git merge their-wording
    2  two additions at the end of one file     git merge add-cooldown
    3  a file deleted on one side, edited on    git merge drop-notes
       the other
    4  a conflict in a file that also has       git merge tidy-up
       clean changes elsewhere

Rounds stack up: every merge you commit stays in drill/, so `git log --oneline` there shows each
round you have finished. drill/ is yours to wreck. `reset` builds it again from nothing.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DRILL = ROOT / "drill"
STATE = DRILL / ".git" / "gym.json"
PROGRAM = "workout_log.py"
MARKERS = ("<<<<<<<", "=======", ">>>>>>>")

LOG = """\
def load(path: str) -> list[dict]:
    return []


def save(path: str, records: list[dict]) -> None:
    pass


def add(records: list[dict], record: dict) -> list[dict]:
    records.append(record)
    return records


def summary(records: list[dict]) -> str:
    count = len(records)
    return f"{count} sets"


if __name__ == "__main__":
    sets = add([], {"exercise": "squat", "reps": 5})
    sets = add(sets, {"exercise": "press", "reps": 8})
    print(summary(sets))
"""

OURS_LINE = '    return f"You logged {count} sets"'
THEIRS_LINE = '    return f"{count} sets done"'
BASE_LINE = '    return f"{count} sets"'

LOAD_NOTE = '    """Read the records from path. Nothing is saved yet, so there are none."""'
SAVE_NOTE = '    """Write the records to path. Not written yet."""'
ADD_NOTE = '    """Put one record at the end of the list and give the list back."""'

ROUTINE = '''\
def warmup() -> str:
    return "five minutes on the bike"
'''

REST = '''

def rest() -> str:
    return "ninety seconds between sets"
'''

COOLDOWN = '''

def cooldown() -> str:
    return "five minutes of stretching"
'''

NOTES = """\
# Notes

- squats hurt the left knee below ninety degrees
"""

NOTES_EDITED = NOTES + "- the knee was fine at eighty degrees\n"


def after(text: str, line: str, new: str) -> str:
    """text with the line new put in straight after line."""
    return text.replace(line + "\n", line + "\n" + new + "\n", 1)


def with_line(text: str, line: str) -> str:
    """The workout log with its summary line swapped for another one."""
    return text.replace(BASE_LINE, line, 1)


# One entry per shape: what the round starts from, what `main` does, what the branch does.
# A file set to None is deleted on that side.
SHAPES: dict[int, dict] = {
    1: {
        "name": "one line, changed two ways",
        "branch": "their-wording",
        "base": {PROGRAM: LOG},
        "ours": ("Say You logged in the summary line", {PROGRAM: with_line(LOG, OURS_LINE)}),
        "theirs": ("Say done in the summary line", {PROGRAM: with_line(LOG, THEIRS_LINE)}),
    },
    2: {
        "name": "two additions at the end of one file",
        "branch": "add-cooldown",
        "base": {PROGRAM: LOG, "routine.py": ROUTINE},
        "ours": ("Add a rest between sets", {"routine.py": ROUTINE + REST}),
        "theirs": ("Add a cooldown", {"routine.py": ROUTINE + COOLDOWN}),
    },
    3: {
        "name": "a file deleted on one side, edited on the other",
        "branch": "drop-notes",
        "base": {PROGRAM: LOG, "notes.md": NOTES},
        "ours": ("Note that the knee was fine", {"notes.md": NOTES_EDITED}),
        "theirs": ("Drop the notes, they belong in the log", {"notes.md": None}),
    },
    4: {
        "name": "a conflict in a file that also has clean changes elsewhere",
        "branch": "tidy-up",
        "base": {PROGRAM: LOG},
        "ours": (
            "Say what load does, and You logged in the summary",
            {PROGRAM: with_line(after(LOG, "def load(path: str) -> list[dict]:", LOAD_NOTE), OURS_LINE)},
        ),
        "theirs": (
            "Say what save and add do, and done in the summary",
            {
                PROGRAM: with_line(
                    after(
                        after(LOG, "def save(path: str, records: list[dict]) -> None:", SAVE_NOTE),
                        "def add(records: list[dict], record: dict) -> list[dict]:",
                        ADD_NOTE,
                    ),
                    THEIRS_LINE,
                )
            },
        ),
    },
}

DRILL_README = """\
# The drill

A workout log, and a round of conflict set up on top of it. You are on `main`. The round you are
in, and the merge that starts it, is the last thing `uv run gym.py next` printed.

Before you touch anything, say which branch you are standing on and which one is arriving.

1. `git merge <the branch it named>`
2. Settle every file git names, by editing it. `git diff --check` prints nothing when no marker
   line is left.
3. `git add` each settled file (or `git rm` one you want gone), then `git commit --no-edit`.
4. `uv run workout_log.py`

When you think it is done, from the folder above this one:

```
uv run gym.py check
```

The next round is `uv run gym.py next`. Starting again from nothing is `uv run gym.py reset`.
"""


def git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run one git command inside drill/."""
    return subprocess.run(
        ["git", "-C", str(DRILL), *arguments],
        capture_output=True,
        text=True,
        check=check,
    )


def put(files: dict[str, str | None]) -> None:
    """Write each file into drill/, or delete it where the text is None."""
    for name, text in files.items():
        path = DRILL / name
        if text is None:
            if path.exists():
                git("rm", "-q", name)
        else:
            path.write_text(text)
            git("add", name)


def commit(message: str) -> None:
    """Commit whatever is staged in drill/, if anything is."""
    if git("diff", "--cached", "--quiet", check=False).returncode != 0:
        git("commit", "-q", "-m", message)


def read_state() -> dict:
    """The round the gym is in, as next left it."""
    if not STATE.exists():
        return {"rounds": 0}
    return json.loads(STATE.read_text())


def reset() -> None:
    """Knock the gym down and build it again, with no round set up yet."""
    if DRILL.exists():
        shutil.rmtree(DRILL)
    DRILL.mkdir()
    git("init", "-q", "-b", "main")
    git("config", "user.name", "The Gym")
    git("config", "user.email", "gym@example.com")
    git("config", "commit.gpgsign", "false")
    put({PROGRAM: LOG, "README.md": DRILL_README})
    commit("Add the four functions")
    print("the gym is built, on main, with nothing to merge yet.")
    print("Set up the first round with:")
    print()
    print("    uv run gym.py next")


def next_round(asked: str | None) -> int:
    """Put the two disagreeing commits of the next round in place. 0 when it worked."""
    if not DRILL.exists():
        print("the gym is not built. Run: uv run gym.py reset")
        return 1
    if (DRILL / ".git" / "MERGE_HEAD").exists():
        print("a merge is still open in drill/. Finish it, or from drill/: git merge --abort")
        return 1
    if git("status", "--porcelain").stdout.strip():
        print("drill/ has changes that are not committed. Commit them, or run: uv run gym.py reset")
        return 1
    if git("branch", "--show-current").stdout.strip() != "main":
        print("the gym works on main. From drill/: git switch main")
        return 1

    state = read_state()
    if asked is None:
        shape = state["rounds"] % len(SHAPES) + 1
    elif asked.isdigit() and int(asked) in SHAPES:
        shape = int(asked)
    else:
        print(f"there is no shape {asked!r}. The shapes are 1 to {len(SHAPES)}.")
        return 2
    round_ = SHAPES[shape]
    branch = round_["branch"]

    put(round_["base"])
    commit(f"Set up round {state['rounds'] + 1}")
    git("branch", "-f", branch)
    message, files = round_["ours"]
    put(files)
    commit(message)
    git("checkout", "-q", branch)
    message, files = round_["theirs"]
    put(files)
    commit(message)
    tip = git("rev-parse", "HEAD").stdout.strip()
    git("checkout", "-q", "main")

    state = {"rounds": state["rounds"] + 1, "shape": shape, "branch": branch, "tip": tip}
    STATE.write_text(json.dumps(state))
    print(f"round {state['rounds']}, shape {shape}: {round_['name']}.")
    print()
    print("    cd drill")
    print(f"    git merge {branch}")
    return 0


def problems() -> list[str]:
    """Everything still wrong with this round, in the order it matters."""
    if not DRILL.exists():
        return ["the gym is not built. Run: uv run gym.py reset"]
    state = read_state()
    if "shape" not in state:
        return ["no round is set up yet. Run: uv run gym.py next"]
    branch = state["branch"]

    found = []
    if (DRILL / ".git" / "MERGE_HEAD").exists():
        unmerged = git("diff", "--name-only", "--diff-filter=U").stdout.split()
        waiting = f" Still waiting to be settled: {', '.join(unmerged)}." if unmerged else ""
        found.append(
            "the merge has not been committed." + waiting + " Settle each file, `git add` it "
            "(or `git rm` it), then: git commit --no-edit"
        )

    tracked = git("ls-files").stdout.split()
    for name in sorted(set(tracked)):
        path = DRILL / name
        if not path.exists():
            continue
        lines = path.read_text().splitlines()
        numbers = [str(n) for n, line in enumerate(lines, start=1) if line.startswith(MARKERS)]
        if numbers:
            found.append(
                f"{name} still has marker lines in it, on line {', '.join(numbers)}. Those lines "
                "are git showing you the two versions; none of them belongs in the finished file."
            )
    if any("marker lines" in problem for problem in found):
        return found  # nothing else can be judged until the markers are gone

    dirty = git("status", "--porcelain").stdout.strip()
    if dirty and not found:
        found.append("drill/ has changes that are not committed:\n" + dirty)

    parents = git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()
    if not found and (len(parents) != 3 or parents[2] != state["tip"]):
        found.append(f"this round's merge has not happened yet. From drill/: git merge {branch}")
    if found:
        return found

    for name in tracked:
        if name.endswith(".py"):
            run = subprocess.run(
                [sys.executable, name], cwd=DRILL, capture_output=True, text=True, timeout=30
            )
            if run.returncode != 0:
                last = run.stderr.strip().splitlines()[-1:] or ["no output"]
                found.append(f"{name} does not run: {last[0]}")

    text = (DRILL / PROGRAM).read_text() if (DRILL / PROGRAM).exists() else ""
    if state["shape"] == 2:
        routine = (DRILL / "routine.py").read_text()
        for wanted in ["def rest()", "def cooldown()"]:
            if wanted not in routine:
                found.append(
                    f"routine.py has no {wanted}. Both sides added a function and both were "
                    "wanted; nobody disagreed about anything."
                )
    if state["shape"] == 4:
        for wanted, side in [(LOAD_NOTE, "main"), (SAVE_NOTE, branch), (ADD_NOTE, branch)]:
            if wanted not in text.splitlines():
                found.append(
                    f"{PROGRAM} lost a line git had already merged cleanly, from {side}: "
                    f"{wanted.strip()!r}. Only the marked lines were yours to edit."
                )
    return found


def check() -> int:
    """Say what is still wrong with this round, or that nothing is. 0 when it is clear."""
    found = problems()
    if not found:
        state = read_state()
        merges = git("rev-list", "--merges", "--count", "HEAD").stdout.strip()
        print(f"round {state['rounds']} is clear: settled, merged and committed.")
        if state["shape"] == 3:
            kept = (DRILL / "notes.md").exists()
            print("notes.md was kept." if kept else "notes.md was let go.")
        print(f"drill/ holds {merges} merge commit{'' if merges == '1' else 's'} so far.")
        print("Next round: uv run gym.py next")
        return 0
    for problem in found:
        print(f"- {problem}")
    return 1


def main() -> int:
    """reset, next or check, whichever was asked for."""
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "reset":
        reset()
        return 0
    if command == "next":
        return next_round(sys.argv[2] if len(sys.argv) > 2 else None)
    if command == "check":
        return check()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
