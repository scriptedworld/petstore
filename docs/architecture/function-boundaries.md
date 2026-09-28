# IO boundaries are seams

Code that does IO takes the IO as an argument. Production passes nothing and
gets the real boundary; a test passes a `petstore.Stub`. Nothing is patched,
because the code declares the seam and the test uses it.

The same applies to anything that raises an exception that is hard to provoke
for real, such as a full disk.

## Terminology

- A **boundary function** is a small wrapper around IO, or around an operation
  whose failure is otherwise hard to provoke.
- A **seam** is a parameter through which a boundary function is passed.
- A **function policy** is an immutable, typed group of boundary functions that
  vary together.

## The default form: a seam with a default

```python
from collections.abc import Callable
from pathlib import Path

Reader = Callable[[Path], str]


def _read_text(path: Path) -> str:
    """Read text at the filesystem boundary."""
    return path.read_text()


def load_config(path: Path, *, reader: Reader = _read_text) -> Config:
    """Load config from path."""
    return decode_config(reader(path))
```

`_read_text` owns the IO and does nothing else. `load_config` owns the
decisions. The seam is keyword-only, so a caller cannot pass a reader by
accident, and callers in production never name it.

A test passes its own reader:

```python
def test_load_config_reads_the_requested_path() -> None:
    reader = Stub(_read_text).returns('{"enabled": true}')

    result = load_config(Path("config.yaml"), reader=reader)

    assert result.enabled
    assert reader.calls[0].args == (Path("config.yaml"),)
```

`Stub(_read_text)` takes the boundary function's signature and types, so it
rejects a call the real one would reject, and scripting a return value of the
wrong type is a type error.

## A failure the machine will not produce on demand

A full disk is the standard case. A test cannot fill a real filesystem safely,
so the write goes behind a seam and the test hands in one that fails:

```python
import errno
from enum import Enum

Writer = Callable[[Path, str], None]


class Saved(Enum):
    """Outcome of saving a report."""

    OK = "ok"
    DISK_FULL = "disk full"


def _write_text(path: Path, text: str) -> None:
    """Write text at the filesystem boundary."""
    path.write_text(text)


def save_report(path: Path, text: str, *, writer: Writer = _write_text) -> Saved:
    """Save a report, turning a full disk into an outcome."""
    try:
        writer(path, text)
    except OSError as error:
        if error.errno != errno.ENOSPC:
            raise
        return Saved.DISK_FULL
    return Saved.OK
```

```python
def test_a_full_disk_is_an_outcome_not_a_crash() -> None:
    writer = Stub(_write_text).raises(OSError(errno.ENOSPC, "No space left on device"))

    assert save_report(Path("report.txt"), "body", writer=writer) is Saved.DISK_FULL
    assert writer.call_count == 1


def test_any_other_write_failure_still_raises() -> None:
    writer = Stub(_write_text).raises(OSError(errno.EACCES, "Permission denied"))

    with pytest.raises(OSError, match="Permission denied"):
        save_report(Path("report.txt"), "body", writer=writer)
```

The stub does one thing: it raises the failure the test exists for. It does
not imitate a filesystem.

## Several seams: a composition factory

When an operation has several boundary functions that vary together, a
default on each parameter crowds its signature. Collect them in a function
policy, and let a factory bind the production one:

```python
from typing import NamedTuple


class FilePolicy(NamedTuple):
    """Filesystem boundary functions used by one operation."""

    read: Callable[[Path], str]
    write: Callable[[Path, str], None]
    exists: Callable[[Path], bool]


PRODUCTION = FilePolicy(read=_read_text, write=_write_text, exists=Path.exists)


def _publish(source: Path, target: Path, *, files: FilePolicy) -> bool:
    """Copy source to target unless target already exists."""
    if files.exists(target):
        return False
    files.write(target, files.read(source))
    return True


def make_publisher(files: FilePolicy = PRODUCTION) -> Callable[[Path, Path], bool]:
    """Bind a file policy and return the operational publisher."""

    def publish(source: Path, target: Path) -> bool:
        """Copy source to target unless target already exists."""
        return _publish(source, target, files=files)

    return publish


publish = make_publisher()
```

Tests call `_publish` with a policy built from stubs. Each factory also needs
one wiring test that calls the function it returns, since calling only the
factory leaves the closure's body uncovered.

A policy stays a small bag of related functions. It holds no state and no call
history, and it does no lookup. Name it for its domain, such as `FilePolicy`,
not `Dependencies`.

## When not to add a seam

An operation that can raise does not need a seam for that alone. Validation
errors and deterministic library failures are provoked through ordinary
inputs. Pure functions need none, and a private helper that only decomposes
logic is not a seam.

## Why this is not mocking

A mock or a patch replaces something the code under test did not offer to have
replaced, such as a module attribute or a method on a class. A stub passed
through a seam replaces only what the function's own signature says may be
passed. Patching a module's internals is still patching, and a seam is how to
avoid needing it.

## Adoption checklist

- Confirm the operation is IO, or a failure that is hard to provoke.
- Wrap the boundary in a small documented function.
- Take it as a keyword-only parameter whose default is that function.
- For several boundaries that vary together, use a function policy and a
  composition factory.
- Test through the seam with `petstore.Stub`, built from the boundary function.
