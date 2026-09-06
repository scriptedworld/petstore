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

## Canonical requirements

[`iteration.requirements.yaml`](iteration.requirements.yaml) is the sole
normative source for this module's requirements. Requirement statements must
not be duplicated or edited in this Markdown file.

The YAML registry is append-only after requirements become active. IDs are
never deleted or reused; replaced behavior is retained with `status: retired`
and linked to its replacement through `superseded_by`.

| ID | Status | Title |
| --- | --- | --- |
| `PS-ITER-001` | Active | Deferred iteration |
| `PS-ITER-002` | Active | Shortest-input mode |
| `PS-ITER-003` | Active | Strict mode with equal inputs |
| `PS-ITER-004` | Active | Strict mode mismatch |
| `PS-ITER-005` | Retired | First-input mode |
| `PS-ITER-006` | Retired | Longest-input mode |
| `PS-ITER-007` | Active | Empty invocation |
| `PS-ITER-008` | Retired | Mode selection |
| `PS-ITER-009` | Active | First-input mode with per-input fills |
| `PS-ITER-010` | Active | Longest-input mode with per-input fills |
| `PS-ITER-011` | Retired | Fill-value configuration |
| `PS-ITER-012` | Retired | Dynamic fill factories |
| `PS-ITER-013` | Active | Mode selection without unnecessary seams |
| `PS-ITER-014` | Active | Directly validated fill-value configuration |
| `PS-ITER-015` | Retired | Directly tested wrapped fill factories |
| `PS-ITER-016` | Active | Callable fill values |

This table is an informational index. If it disagrees with the YAML registry,
the YAML registry is authoritative and the table must be corrected.

## Test traceability

Tests declare traceability with the registered pytest marker:

```python
@pytest.mark.requirement(
    "PS-ITER-002",
    functionality="zip_iter.shortest",
    test_type="positive",
)
```

The marker's positional values are requirement IDs. `functionality` identifies
the exercised public behavior. `test_type` classifies the test as `positive`,
`negative`, `edge`, `property`, `invariant`, or `regression`.

The requirement-coverage gate will validate markers against the canonical YAML
registry, reject retired or unknown IDs, enforce required test classifications,
and ensure every active requirement is covered.
