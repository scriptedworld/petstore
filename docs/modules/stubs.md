# Scripted test doubles

Module: `petstore.stubs`

Public API: `petstore.Stub`, `petstore.StubExhaustedError`, `petstore.CallEvent`,
`petstore.stubs.make_signature`

## Purpose

This module builds callables whose successive outcomes are declared in advance
and whose invocations are recorded. A chain of links reads as the call sequence
it stands for, so a seam's expected behavior is visible at the point the double
is constructed rather than assembled from assertions later.

## Usage

```python
from petstore import Stub

fetch = Stub().returns(200).yields("a").yields("b").raises(TimeoutError)

fetch()  # 200
fetch()  # an iterator producing "a" then "b"
fetch()  # raises TimeoutError
```

`returns` and `raises` each describe one whole call. `yields` and `yields_from`
mirror the statements they are named after and accumulate into a single call's
iterator: `yields(a)` is `yield a`, and `yields_from(a)` is `yield from a`. A
run of them builds one generator, which the next `returns` or `raises` closes.

```python
stub = Stub().yields(1).yields_from([2, 3]).returns(None)

list(stub())  # [1, 2, 3]
stub()  # None
```

Calling a stub more times than its script describes raises
`StubExhaustedError` rather than silently repeating. The unscripted call is
still recorded, so the history can be inspected after the failure.

By default a link covers one call. When repetition is what a test wants, a
modifier says so explicitly by widening the most recent link. Each link takes at
most one modifier.

```python
Stub().returns("not ready").times(3).returns("ready")  # three calls, then one
Stub().returns("warming").over(seconds=30).returns("up")  # 30 seconds, then one
Stub().returns("ready").always()  # every call from here on
```

`times(n)` covers `n` consecutive calls. `always()` covers this and every later
call. `over(hours=..., minutes=..., seconds=...)` covers every call made within a
window that opens at the first call reaching the link. A timed final link whose
window has closed leaves the stub exhausted.

Timed links are measured by the stub's clock. Tests should supply their own, so
that time moves only when the test moves it:

```python
now = [0.0]
status = Stub(clock=lambda: now[0]).returns("warming").over(seconds=30).returns("up")

status()  # "warming"
now[0] = 30.0
status()  # "up"
```

A repeated generator link builds a fresh iterator on each call. Anything passed
to `yields_from` is iterated again each time, so pass a re-iterable such as a
list; a one-shot iterator is empty from the second call onwards. `always`
without a preceding link, and any link added after it, raise `ValueError`,
since that later link could never be reached.

Every invocation is captured as a `CallEvent` holding the positional arguments,
the keyword arguments and (when a signature was declared) the arguments bound
to their parameter names:

```python
save = Stub(parameters=["path"]).returns(None)
save("alpha")

save.calls[0].bound_arguments  # {"path": "alpha"}
save.call_count  # 1
```

A signature may be given as parameter names or copied from a real callable with
`Stub(some_function)`. The two sources are mutually exclusive. Without one, the
stub accepts any arguments and records no binding.

A stub built from a callable also takes its types. `Stub(read_text)` type-checks
wherever `read_text` would, and `Stub(read_text).returns(42)` is a type error
when `read_text` returns `str`. Pass the real boundary function whenever there
is one: the stub then rejects bad calls at runtime and bad scripts statically.
A stub built without a callable accepts any arguments and returns `Any`.

For a seam that does the same thing on every call,
[`generate`](../testing/stub.md) is the short form.

## Canonical requirements

[`stubs.requirements.yaml`](stubs.requirements.yaml) is the sole normative
source for this module's requirements. Requirement statements must not be
duplicated or edited in this Markdown file.

The YAML registry is append-only after requirements become active. IDs are
never deleted or reused; replaced behavior is retained with `status: retired`
and linked to its replacement through `superseded_by`.

| ID | Status | Title |
| --- | --- | --- |
| `PS-STUB-001` | Active | Scripted call sequence |
| `PS-STUB-002` | Active | Value and exception outcomes |
| `PS-STUB-003` | Active | Generator composition |
| `PS-STUB-004` | Active | Script exhaustion |
| `PS-STUB-005` | Active | Call recording |
| `PS-STUB-006` | Active | Declared signatures |
| `PS-STUB-007` | Active | Repeating link |
| `PS-STUB-008` | Retired | Counted link |
| `PS-STUB-009` | Retired | Timed link |
| `PS-STUB-010` | Active | Counted link |
| `PS-STUB-011` | Active | Timed link |
