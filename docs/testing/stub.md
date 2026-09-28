# One-behavior stubs

`petstore.generate` is the short form of [`petstore.Stub`](../modules/stubs.md)
for a seam that does the same thing on every call. It builds a stub whose
script is one repeating link, so it carries the same call history and the same
typing. It is passed through a seam the code declares, so it does not patch or
replace a runtime object and is not a mock.

Reach for `Stub` directly when successive calls need to differ, such as a
write that fails twice and then succeeds.

Generated stubs are intended for the implementation layer described by the
[`functional boundary-composition standard`](../architecture/function-boundaries.md)
or as entries in a test function policy.

The canonical requirements are in
[`stub.requirements.yaml`](stub.requirements.yaml).

## Configured behavior

Choose exactly one behavior when generating a function:

```python
returning = generate(returns="value")
raising = generate(raises=RuntimeError("unavailable"))
yielding = generate(yields=["first", "second"])
```

`raises` accepts an exception instance or a zero-argument exception type.
`yields` snapshots its iterable when `generate` is called. Each invocation of
the resulting function returns a fresh iterator over that snapshot.

Pass the result directly to a seam:

```python
read = generate(returns="contents")

assert consumer(read=read) == "contents"
assert read.call_count == 1
assert read.calls[0].args == ()
assert dict(read.calls[0].kwargs) == {}
```

Every valid invocation is recorded before its return, raise, or yield behavior
occurs. `calls` is an immutable tuple of `CallEvent` records; each record
contains positional `args`, read-only `kwargs`, and optional read-only
`bound_arguments`. Generate a new stub whenever a test needs empty call
history.

## Optional call signatures

A generated stub accepts arbitrary arguments by default. A test can instead
declare ordered positional-or-keyword parameter names:

```python
operation = generate(returns="result", parameters=["left", "right"])
operation(1, right=2)

assert dict(operation.calls[0].bound_arguments) == {"left": 1, "right": 2}
```

Or it can copy the complete signature of an existing callable:

```python
def contract(identifier: int, *, enabled: bool = False) -> str:
    raise NotImplementedError


operation = generate(returns="result", signature_from=contract)
```

`signature_from` inspects the callable without invoking it and preserves
positional-only, keyword-only, variadic, and defaulted parameters. Invalid
calls raise `TypeError` and do not enter call history. `parameters` and
`signature_from` are mutually exclusive.
