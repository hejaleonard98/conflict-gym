# The conflict gym

A merge conflict whenever you ask for one, in four shapes. `gym.py` builds a small git repository
in `drill/` holding a workout log, and sets up one round of conflict on top of it at a time.

## Build the gym

```
uv sync
uv run gym.py reset
```

## A round

```
uv run gym.py next
```

It says which shape the round is and which branch to merge. From `drill/`, merge it, settle every
file git names by editing it, `git add` (or `git rm`), and `git commit --no-edit`. Then, from here:

```
uv run gym.py check
```

The shapes come round in order: one line changed two ways, two additions at the end of one file, a
file deleted on one side and edited on the other, and a conflict in a file that also has clean
changes elsewhere. `uv run gym.py next 3` asks for one shape by its number.

Every merge you commit stays in `drill/`. `reset` knocks it down and builds it again from nothing.

`drill/` is not part of this repository: it is its own git repository, and `.gitignore` leaves it
out. What you hand in lives here, next to `gym.py`.

## Run the tests

```
uv run pytest
```

The tests are about `gym.py`, not about your resolutions.
