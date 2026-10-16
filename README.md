# PetStore

Small Python tools for development work: `Validated` attributes checked on
assignment and `validate` for plain values such as arguments, `Stub` for
testing code through its IO seams, a cross-process path lock, a zip with four
termination policies, one place to start other programs from, counters and
measures with exact summaries and quantiles, and test decorators that hold
code to a time or memory complexity. Python 3.14 or later, typed.

## Install

petstore is not on PyPI. Install it from GitHub:

```console
uv add git+https://github.com/scriptedworld/petstore
```

or, with pip, `pip install git+https://github.com/scriptedworld/petstore`.

## Lazy zip

The module guide is [`docs/modules/iteration.md`](docs/modules/iteration.md).

`petstore.zip_iter` combines iterables lazily and supports four termination
policies:

```python
from petstore import ZipMode, zip_iter

list(zip_iter([1, 2], ["a"], mode=ZipMode.SHORTEST))
# [(1, "a")]

list(zip_iter([1, 2], ["a"], mode="first", fillvalues=(0, "missing")))
# [(1, "a"), (2, "missing")]

list(zip_iter([1], ["a", "b"], mode="longest", fillvalues=(0, "missing")))
# [(1, "a"), (0, "b")]

sequence = iter(["first", "second"])
list(zip_iter([1, 2], [], mode="first", fillvalues=(None, lambda: next(sequence))))
# [(1, "first"), (2, "second")]
```

The modes are:

- `shortest`: standard Python `zip` behavior.
- `strict`: standard Python `zip(..., strict=True)` behavior.
- `first`: Ruby-like behavior; the first iterable determines the result length,
  shorter remaining iterables use their position's fill value, and their excess
  values are ignored.
- `longest`: continue until every iterable is exhausted, padding shorter inputs.

For `first` and `longest`, `fillvalues` contains one value per input. When it is
omitted, every missing position uses `None`. A zero-argument callable creates a
fresh value each time its input position is missing.

All input iterables are converted to iterators only when iteration begins. The
result is single-pass and does not cache input values.

## Validated attributes

The module guide is [`docs/modules/validation.md`](docs/modules/validation.md).

`petstore.Validated` checks a value at the moment it is assigned, so a
constructed object is a valid one. A rule is an ordinary function: value in,
raise on problem, return nothing.

```python
from dataclasses import dataclass

from petstore import Validated, ValidationError


def positive(value: int) -> None:
    if value <= 0:
        message = "must be positive"
        raise ValidationError(message)


SIZE = Validated(positive)


@dataclass(frozen=True)
class Batch:
    size: Validated[int] = SIZE


Batch(4).size  # 4
Batch(0)  # ValidationError: size must be positive
```

Rules run in declaration order and stop at the first failure: the first rule to
reject a value is the one reported, and the rules after it are not run, so a
value with two problems reports the first. The rule supplies only what is wrong; the descriptor supplies which
attribute it was, defaulting to the attribute name and overridable with
`label=`. Validation applies to later assignment exactly as to construction,
and works on frozen dataclasses, which reject ordinary attribute assignment.

`petstore.validate` is what runs the rules, and `Validated` calls it on every
assignment. Called directly, it checks a plain value, such as a function
argument, and returns it unchanged, so the check sits on the assignment. The
label is required and keyword-only:

```python
from petstore import validate


def reserve(count: int) -> int:
    count = validate(count, positive, label="count")
    return count


reserve(4)  # 4
reserve(0)  # ValidationError: count must be positive
```

## Testing IO through a seam

Code that does IO takes the IO as an argument, defaulting to the real thing:

```python
import errno
from collections.abc import Callable
from pathlib import Path

Writer = Callable[[Path, str], None]


def _write_text(path: Path, text: str) -> None:
    path.write_text(text)


def save_report(path: Path, text: str, *, writer: Writer = _write_text) -> bool:
    """Save a report; False when the disk is full."""
    try:
        writer(path, text)
    except OSError as error:
        if error.errno != errno.ENOSPC:
            raise
        return False
    return True
```

Production calls `save_report(path, text)`. A test provokes a full disk, which
no real filesystem will do on demand, by passing a `petstore.Stub` through the
seam:

```python
from petstore import Stub


def test_a_full_disk_is_reported_not_raised() -> None:
    writer = Stub(_write_text).raises(OSError(errno.ENOSPC, "No space left on device"))

    assert save_report(Path("report.txt"), "body", writer=writer) is False
    assert writer.call_count == 1
```

Nothing is patched: the function declares the seam and the test uses it.
`Stub(_write_text)` takes that function's signature and types, so it rejects a
call the real one would. A stub scripts successive outcomes (`returns`,
`raises`, `yields`) and records every call.

[`docs/architecture/function-boundaries.md`](docs/architecture/function-boundaries.md)
is the pattern, including several seams bound by a factory, and
[`docs/modules/stubs.md`](docs/modules/stubs.md) is the guide to `Stub`.

## Path locks

The module guide is [`docs/modules/locking.md`](docs/modules/locking.md).

`petstore.locked` holds an exclusive lock named for a path, honored across
processes:

```python
from petstore import locked

with locked("/srv/app/socket"):
    ...

with locked("/srv/app/socket", timeout=5):
    ...  # raises LockTimeoutError if still held after five seconds
```

The lock is an advisory `flock` on a private lock file named for the resolved
path, so the path itself need not exist and is never touched. Lock files live
under `$XDG_RUNTIME_DIR`; use `make_locked(lock_dir=...)` where no runtime
directory exists. POSIX only.

## Starting other programs

The module guide is [`docs/modules/proc.md`](docs/modules/proc.md).

`petstore.proc` starts programs from a list of arguments, never through a
shell, so each element reaches the program as one argument:

```python
from petstore.proc import capture

finished = capture(["git", "rev-parse", "HEAD"], check=True)
finished.stdout  # the commit, with a newline
```

`through` hands the child given streams, `wait` lets it use this process's,
and `become` replaces this process with it. bandit's findings on starting a
program are registered once, in petstore, so code starting its programs here
needs no pragma of its own.

## Metrics

The module guide is [`docs/modules/metrics.md`](docs/modules/metrics.md).

`petstore.metrics` counts how often things happen and records values. Import
it as a module; its `Counter` is not exported from `petstore`, where it would
shadow `collections.Counter`:

```python
from petstore.metrics import All, StatsRecorder

recorder = StatsRecorder()
hits = recorder.counter("hits")
load = recorder.measure("page_load", keep=All(), under=(5.0,))

hits()
load(2.4)

d = recorder.snapshot().distribution("page_load")
d.mean, d.stdev, d.quantile(0.95), d.under(5.0)
```

Every measure keeps an exact running summary in constant memory. Quantiles
need `keep=All()`, a recent window needs `keep=Last(n)` and is read through
`.sample`, and a share under a threshold declared in `under=` costs nothing
kept. A question a measure cannot answer raises `StatsError` saying what it
would need. Not thread-safe: give each thread its own recorder, or guard calls
with a lock.

## Complexity tests

The module guide is [`docs/modules/complexity.md`](docs/modules/complexity.md).

`petstore.complexity` holds code to a time or memory complexity in an ordinary
test, by running the same work at several sizes and comparing how a measure
grows:

```python
from petstore.complexity import Clock, Complexity, Probe, time_complexity


@time_complexity(Complexity.CONSTANT, sizes=(100, 1_000, 10_000, 100_000), clock=Clock())
def test_get_is_constant(n: int, probe: Probe) -> None:
    cache = filled(n)  # setup, not measured: your container holding keys 0 to n - 1
    for run, _ in enumerate(probe.runs()):
        key = probe.key(n // 4 + run % (n // 2))  # midway, where a scan arrives late
        with probe.counting():
            cache.get(key)  # the work: measured
```

A `Probe` counts every bytecode instruction run inside `counting()`, and every
hash and comparison on a key from `probe.key()`. That count is the same on
every run, and it cannot see a builtin that never hashes or compares the probe
key: `list(d)` or `sum(d.values())` added to an O(1) operation passes it.
`clock=Clock()` adds a timed pass that does see them, the fastest of 50 runs
per size held to the bound; it is off by default, because a timing depends on
the machine. Probe a key midway through the structure's order, or a missing
one: a scan finds the first key at once.

`memory_complexity` reads `tracemalloc`, for retained or peak bytes.
`Complexity` runs from `CONSTANT` to `FACTORIAL`, and `Growth` makes any other
class. A test that measures nothing fails rather than passing. Not thread-safe:
`sys.monitoring` is process-wide, so run these with no other threads busy. The
guide covers which sizes a test needs, what each measure misses, and how to
show a test failing.

## Developing petstore

```console
uv sync
uv run just checks
```

`checks` is the whole gate: toolbox's Python jig (formatting, lint, strict
typing, complexity, docstrings, dead code, bandit, and the suite under
per-file coverage), wording, requirement traceability and a secrets scan. It
needs a [toolbox](https://github.com/scriptedworld/toolbox) checkout beside
this tree, [bolt](https://github.com/scriptedworld/bolt), and the checkers on
`PATH`; the runbook lists them. `uv run just --list` shows every recipe.

[`docs/tooling-and-runbook.md`](docs/tooling-and-runbook.md) covers the Dev
Container, the recipes, the commit hooks and troubleshooting.

## Releasing

Every change ends with a release, and consumers pin the release tag, never a
commit hash:

```toml
[tool.uv.sources]
petstore = { git = "https://github.com/scriptedworld/petstore", tag = "v0.5.0" }
```

A hash in a consumer's `pyproject.toml` reads as a possible secret to
detect-secrets, and a tag says what the pin means.

```console
just release                      # the increment the commits call for
just release --increment PATCH    # or name it
```

The version is written once, in `pyproject.toml`; `petstore.__version__` reads
it back from the installed package. `release` refuses unless it is on `main`
with nothing uncommitted, then runs the full gate and commitizen's `cz bump`.
That works out the increment from the conventional commits since the last tag
(`fix` a patch; `feat`, and before 1.0 a breaking change, a minor), sets the
version, relocks `uv.lock`, adds the release to `CHANGELOG.md`, commits, and
creates the annotated tag. `release` then pushes the commit and the tag with
`git push --follow-tags` and prints `git ls-remote --tags` for the new tag as
the proof it landed.

Tags are `vMAJOR.MINOR.PATCH`. Before 1.0, a minor release may break things. A
pushed tag is never moved or deleted; a mistake is fixed by the next patch
release. `tests/test_release.py` fails if `petstore.__version__`,
`pyproject.toml` and the tags drift apart.
