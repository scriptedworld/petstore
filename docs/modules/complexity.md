# Complexity

Module: `petstore.complexity`, imported from the module itself and not from
`petstore`:

```python
from petstore.complexity import Complexity, Meter, Probe, memory_complexity, time_complexity
```

Public API: `time_complexity`, `memory_complexity`, `Complexity`, `Growth`,
`GrowthClass`, `Probe`, `Meter`, `assert_growth`

## Purpose

Hold code to a time or memory complexity in an ordinary test. The same work is
run at several sizes and a deterministic measure is compared across them:
instructions counted for time, bytes allocated for memory. Nothing is timed,
so the result is the same on every machine and every run.

## Time

```python
@time_complexity(Complexity.CONSTANT, sizes=(10, 100, 1_000))
def test_get_is_constant(n: int, probe: Probe) -> None:
    cache = filled(n)  # setup: not counted
    with probe.counting():
        cache.get(probe.key(0))  # the work: counted
```

The decorated test takes `(n, probe)` and is called once per size. Inside
`probe.counting()` the `Probe` counts two kinds of work, so neither hides:

- **Every bytecode instruction executed**, through `sys.monitoring` on a tool
  id no one else is using, so coverage and debuggers keep working. This
  catches loops in Python code however they reach their data, including a loop
  packed into one line such as a comprehension.
- **Every hash and comparison on a key from `probe.key()`.** This catches work
  inside C builtins, where `key in some_list` compares n times in a single
  instruction.

`granularity="lines"` counts lines instead. It is faster, but blind to a loop
that stays on one line, so a comprehension over n items reads as constant.
`probe.tick(n)` counts anything else by hand.

## Memory

```python
@memory_complexity(Complexity.CONSTANT, sizes=(1_000, 10_000, 100_000))
def test_memory_stays_bounded(n: int, meter: Meter) -> None:
    cache = Cache(capacity=10)
    with meter.measuring():
        for i in range(n):
            cache.put(i, i)
```

The decorated test takes `(n, meter)`. A `Meter` reads `tracemalloc` inside
`meter.measuring()`. `measure="retained"`, the default, holds what the block
leaves allocated; `measure="peak"` holds the most it allocated at any moment,
so auxiliary space can be bounded as well as retained space. Readings under
`noise` bytes, 4096 by default, count as noise.

## Growth classes

`Complexity` names the usual classes, slowest growing first: `CONSTANT`,
`LOGARITHMIC`, `SQUARE_ROOT`, `LINEAR`, `LINEARITHMIC`, `QUADRATIC`, `CUBIC`,
`EXPONENTIAL` and `FACTORIAL`. `Growth` makes any other:

```python
QUARTIC = Growth("n^4", lambda n: n**4)
```

A growth is an upper bound, like the O it stands for. The measure at each size
is divided by the growth function, and every result must stay within
`tolerance` times the one at the smallest size; the default tolerance is 2.
Ratios are compared as logarithms, so a growth function may return an integer
too large for a float, as `n!` does.

## Sizes

Sizes must be at least two, strictly ascending and positive, and must span a
factor large enough for a wrong class to show:

- **10 for polynomial classes.** Linear work held to constant over sizes 10 to
  1,000 grows 100 times, far past the tolerance.
- **2 for exponential and factorial classes,** whose growth shows within a
  doubling, and which could not be run over a wider span anyway.

`Growth` takes `min_span` for a class of your own; it defaults to 10.
Sizes that cannot tell one class from another raise `ValueError` when the
decorator is applied.

## Failing safely

A decorated test takes no arguments, so pytest runs it as it is. A test that
never enters its `counting()` or `measuring()` block fails, rather than passing
having measured nothing. A failure names the class expected, the sizes, what was
measured, and how far the measure grew past the tolerance.

`assert_growth(growth, sizes, measured)` is the check on its own, for a measure
taken some other way.

## Threads

Not thread-safe, and only meaningful single-threaded: `sys.monitoring` events
are process-wide, so a Probe also counts instructions that other threads run
while `counting()` is open. Run complexity tests with no other threads busy.

## Requirements

[`docs/REQUIREMENTS/complexity/`](../REQUIREMENTS/complexity/) holds this
module's requirements, `FR-8.x`, one file each. Tests cite them with a
`# COVERS <ids> | <kind>` comment directly above the test.
