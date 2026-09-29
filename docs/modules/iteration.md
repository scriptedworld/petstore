# Iterable combination

Module: `petstore.iteration`

Public API: `petstore.zip_iter`, `petstore.ZipMode`

## Purpose

This module combines any number of iterables without materializing them. Its
termination policy is explicit, allowing callers to select Python-compatible,
strict, Ruby-like, or longest-input behavior.

## Usage

```python
from petstore import ZipMode, zip_iter

shortest = zip_iter([1, 2], ["a"], mode=ZipMode.SHORTEST)
assert list(shortest) == [(1, "a")]

per_input_fills = zip_iter(
    [1],
    ["a", "b"],
    mode=ZipMode.LONGEST,
    fillvalues=(0, "missing"),
)
assert list(per_input_fills) == [(1, "a"), (0, "b")]

sequence = iter(["first", "second"])
dynamic_fills = zip_iter(
    [1, 2],
    [],
    mode=ZipMode.FIRST,
    fillvalues=(None, lambda: next(sequence)),
)
assert list(dynamic_fills) == [(1, "first"), (2, "second")]
```

A zero-argument callable fill is invoked separately and lazily for each missing
position. All other fill entries are used as static values.

## Requirements

[`docs/REQUIREMENTS/iteration/`](../REQUIREMENTS/iteration/) holds this
module's requirements, `FR-1.x`, one file each. Tests cite them with a
`# COVERS <ids> | <kind>` comment directly above the test.
