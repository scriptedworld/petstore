# PetStore

PetStore is a UV-managed collection of small Python tools for development work.

The canonical development, quality, commit, traceability, and troubleshooting
instructions are in [`docs/tooling-and-runbook.md`](docs/tooling-and-runbook.md).
The standard pattern for testable I/O and difficult exception boundaries is in
[`docs/architecture/function-boundaries.md`](docs/architecture/function-boundaries.md).

## Setup

```console
uv sync
uv run poe hooks
uv run poe quality
```

### Dev Container

The repository includes a reproducible development container using Python 3.14
on Debian Bookworm and UV 0.12.6. Opening the repository in a Dev
Container synchronizes the locked environment and installs the configured Git
hooks when Git metadata is available.

The container persists UV's download cache in a named volume and configures the
Python, Ruff, Mypy, and Pytest editor integrations. After creation, run:

```console
uv run poe quality
```

## Lazy zip

Module documentation and its identified requirements are maintained in
[`docs/modules/iteration.md`](docs/modules/iteration.md), with the canonical
requirement registry in
[`docs/modules/iteration.requirements.yaml`](docs/modules/iteration.requirements.yaml).

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

Module documentation and its identified requirements are maintained in
[`docs/modules/validation.md`](docs/modules/validation.md), with the canonical
requirement registry in
[`docs/modules/validation.requirements.yaml`](docs/modules/validation.requirements.yaml).

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

## Scripted test doubles

Module documentation and its identified requirements are maintained in
[`docs/modules/stubs.md`](docs/modules/stubs.md), with the canonical requirement
registry in
[`docs/modules/stubs.requirements.yaml`](docs/modules/stubs.requirements.yaml).

`petstore.Stub` builds a callable whose successive outcomes are declared in
advance and whose invocations are recorded:

```python
from petstore import Stub

fetch = Stub().returns(200).yields("a").yields("b").raises(TimeoutError)

fetch()  # 200
fetch()  # an iterator producing "a" then "b"
fetch()  # raises TimeoutError
```

`returns` and `raises` each describe one whole call. `yields` and `yields_from`
mirror the statements they are named after and accumulate into a single call's
iterator, which the next `returns` or `raises` closes. Calling past the end of
the script raises `StubExhaustedError` rather than silently repeating, and the
unscripted call is still recorded. When repetition is wanted, a modifier widens
the most recent link: `times(n)` for a counted run, `over(seconds=30)` for a time
window measured by an injectable clock, or `always()` for every later call.

Declaring a signature, either as parameter names or copied from a real callable,
makes the stub reject calls the real function would reject and records arguments
bound to their parameter names through `calls[n].bound_arguments`.

## Path locks

Module documentation and its identified requirements are maintained in
[`docs/modules/locking.md`](docs/modules/locking.md), with the canonical
requirement registry in
[`docs/modules/locking.requirements.yaml`](docs/modules/locking.requirements.yaml).

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

## Quality gates

Install the development tools and run the standard project gate through UV:

```console
uv sync
uv run poe quality
```

`quality` runs formatting checks, Ruff, Mypy, Pylint, Complexipy, Interrogate,
Vulture, Bandit, mechanical requirement traceability, and Pytest in sequence.
Use `uv run poe fix` to format code and apply safe Ruff fixes. Every individual
gate is also available as a Poe task; run `uv run poe --help` to list them.

## Commits

Install both the quality and commit-message hooks after cloning:

```console
uv run poe hooks
```

Create commits through Commitizen:

```console
uv run poe commit
```

Every commit message must follow Conventional Commits. The `pre-commit` hook
delegates the complete source check to `poe quality`, keeping the quality-gate
definition in one place. The `commit-msg` hook delegates validation to the Poe
`commit-check` task and rejects non-conforming messages. Run all file-oriented
hooks manually with `uv run poe hooks-run`.

Pytest enforces 100% line and branch coverage and prints coverage for every
source file. Pylint permits no findings and does not calculate an averaged
score. Interrogate requires 100% documentation coverage. Ruff and Pylint limit
nesting to three blocks; Ruff and Complexipy enforce a per-function complexity
ceiling of 15. Source lines may be up to 150 characters. Complexity, typing,
lint, and dead-code gates inspect both `src/` and `tests/`. Interrogate and
Bandit inspect production code under `src/` only.

Project-wide engineering constraints and any human-approved exceptions are
recorded in [`SUPPRESSIONS.md`](SUPPRESSIONS.md). Safety-tool suppressions
require explicit human approval and an expiry date. Approved mocks and patches
would be recorded in [`MOCKS.md`](MOCKS.md); its current approved ledger is
empty.
