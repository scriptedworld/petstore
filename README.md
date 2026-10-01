# PetStore

Small Python tools for development work: `Validated` attributes checked on
assignment, `Stub` for testing code through its IO seams, a cross-process path
lock, and a zip with four termination policies. Python 3.10 or later, typed.

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

Rules run in declaration order and the first to reject a value determines the
failure. The rule supplies only what is wrong; the descriptor supplies which
attribute it was, defaulting to the attribute name and overridable with
`label=`. Validation applies to later assignment exactly as to construction,
and works on frozen dataclasses, which reject ordinary attribute assignment.

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
