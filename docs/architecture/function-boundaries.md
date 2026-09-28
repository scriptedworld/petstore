# Functional boundary composition

Status: project standard

This pattern keeps a function's public operational signature free of testing
and infrastructure concerns while making genuine boundaries directly testable.
It is the default pattern for PetStore and future projects derived from its
template.

## Terminology

- A **boundary function** is a small wrapper around I/O or another operation
  whose required exception behavior is otherwise difficult or unreliable to
  induce.
- A **strategy** is one replaceable boundary function.
- A **function policy** is an immutable, typed, cohesive collection of related
  strategies. It contains functions, not mutable services or test state.
- An **implementation function** contains the behavior and accepts its
  strategies or policy explicitly.
- A **composition factory** binds production strategies and returns a function
  having the clean operational signature.

## Required shape

Use an explicit implementation and factory for a function that needs a
boundary:

```python
from collections.abc import Callable
from pathlib import Path


Reader = Callable[[Path], str]


def _read_text(path: Path) -> str:
    """Read text at the filesystem boundary."""
    return path.read_text()


def _load_config(path: Path, *, reader: Reader) -> Config:
    """Implement config loading with an explicit boundary strategy."""
    return decode_config(reader(path))


def make_config_loader(*, reader: Reader = _read_text) -> Callable[[Path], Config]:
    """Bind a reader and return the operational config loader."""

    def load_config(path: Path) -> Config:
        """Load config from path."""
        return _load_config(path, reader=reader)

    return load_config


load_config = make_config_loader()
```

The layers have separate responsibilities:

1. `_read_text` owns the I/O boundary.
2. `_load_config` owns validation, decisions, and result construction.
3. `make_config_loader` owns dependency composition.
4. The returned `load_config` owns only argument and result forwarding.

The implementation's boundary parameters must be keyword-only and must not
have production defaults. Production defaults belong to the composition
factory. The returned closure must have an explicit operational signature; a
generic `*args, **kwargs` binder is not part of this pattern.

## Strategies and policies

Use a strategy directly when only one boundary varies. Do not create a policy
solely to wrap one function.

When multiple boundary functions form one cohesive capability and normally
vary together, collect them in a function policy:

```python
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple


class FilePolicy(NamedTuple):
    """Immutable filesystem boundary functions used by one operation."""

    read: Callable[[Path], str]
    write: Callable[[Path, str], None]
    exists: Callable[[Path], bool]
```

A policy must remain a small bag of related functions. It must not become a
project-wide service container, perform runtime lookup, own mutable state, or
contain call history. Prefer a domain-specific name such as `FilePolicy` or
`PublishPolicy` over a generic name such as `Dependencies`.

## When not to introduce a boundary

Do not add a strategy or policy merely because an operation can raise. Normal
validation errors and deterministic library failures should be induced through
ordinary inputs. A non-I/O operation qualifies only when producing the required
failure directly would be difficult, unreliable, unsafe, or prohibitively
expensive.

Pure functions and directly testable iterator behavior do not need this
composition structure. In particular, private helper functions used to
decompose logic are not seams unless the consumer can replace them.

## Testing standard

Behavioral tests call the implementation function and pass a `petstore.Stub`
for each strategy:

```python
def test_load_config_reads_the_requested_path() -> None:
    reader = Stub(_read_text).returns('{"enabled": true}')

    result = _load_config(Path("config.yaml"), reader=reader)

    assert result.enabled
    assert reader.calls[0].args == (Path("config.yaml"),)
```

### A failure the machine will not produce on demand

A full disk is the standard case. A test cannot fill a real filesystem safely,
so the write goes behind a strategy and the test hands in one that fails:

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


def _save_report(path: Path, text: str, *, writer: Writer) -> Saved:
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

    assert _save_report(Path("report.txt"), "body", writer=writer) is Saved.DISK_FULL
    assert writer.call_count == 1


def test_any_other_write_failure_still_raises() -> None:
    writer = Stub(_write_text).raises(OSError(errno.EACCES, "Permission denied"))

    with pytest.raises(OSError, match="Permission denied"):
        _save_report(Path("report.txt"), "body", writer=writer)
```

Nothing is patched. `_save_report` declares that it takes a writer, and the
test passes one, exactly as its composition factory passes `_write_text` in
production.

Validation, positive, negative, edge, property, and invariant cases belong to
the implementation tests. They carry the requirement IDs and functionality of
the public behavior even though they invoke its internal implementation.

Each composition factory also needs a focused wiring test that invokes the
returned function and proves that arguments, results, and bound strategies are
forwarded correctly. Do not duplicate the implementation's behavioral test
matrix at the closure layer.

Coverage tools count a closure body defined under `src/`. Calling only the
factory covers creation of the closure, not execution of its body. The wiring
test must therefore invoke the returned function at least once. Boundary
wrappers containing production code require their own appropriately scoped
integration tests.

Tests use `petstore.Stub` for deterministic return, raise, or yield behavior,
passing the boundary function so the stub rejects calls the real one would.
Build a new stub for each independent history. A stub is an argument the code
declares, so nothing at runtime is patched and nothing needs resetting.

## Adoption checklist

- Confirm that the replaceable operation is genuine I/O or a difficult failure
  boundary.
- Wrap the production boundary in a small documented function.
- Put decisions in a private implementation with explicit keyword-only
  strategies or one cohesive function policy.
- Bind production behavior in an operation-specific composition factory.
- Export the default composed callable with a clean operational signature.
- Test behavior through the implementation and wiring through the factory.
- Record requirement IDs and test classifications on both kinds of tests.
- Use `petstore.Stub` rather than mocks or runtime patching.
