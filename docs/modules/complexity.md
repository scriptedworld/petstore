# Complexity

Module: `petstore.complexity`, imported from the module itself and not from
`petstore`:

```python
from petstore.complexity import Clock, Complexity, Growth, Meter, Probe, memory_complexity, time_complexity
```

Public API: `time_complexity`, `memory_complexity`, `Clock`, `Complexity`,
`Growth`, `GrowthClass`, `Probe`, `Stopwatch`, `Meter`, `assert_growth`

## Purpose

Hold code to a time or memory bound in an ordinary test, so a requirement such
as "get is O(1) in the entries held" has a test that fails when the code grows
faster. The same operation runs at several sizes, and a measure taken at each
is compared against the bound. A test can only catch what its measure sees,
so most of this guide is about choosing the measure, the sizes and the input
that let a wrong algorithm show.

## What each measure sees

There are four measures. Counted work is what `time_complexity` holds by
default; timed work is what it adds with `clock=Clock()`; retained and peak
memory are `memory_complexity`'s.

| Work done by the operation | Counted | Timed | Peak memory |
|---|---|---|---|
| A Python loop, comprehension or recursion | yes | yes | if it allocates |
| A builtin that hashes or compares a probe key, such as `key in some_list` or `some_list.remove(key)` | yes | yes | no |
| A builtin that walks a container without touching the probe key, such as `list(d)`, `sum(d.values())`, `[None] * len(d)` or `deque(iter(d), maxlen=0)` | no | yes | only what it copies, such as `list(d)` |
| Moving memory inside a builtin, such as `some_list.pop(0)` or `insert(0, x)` | no | yes, at large enough sizes | no |
| A CPU cache step as a table outgrows a cache level | no | yes, as growth the tolerance has to absorb | no |

The counted pass uses a `Probe`. Inside `probe.counting()` it counts every
bytecode instruction run, through `sys.monitoring` on a tool id nobody else is
using, so coverage and debuggers keep working. It also counts every hash and
comparison made on a key from `probe.key()`, which is how `key in some_list`
shows as n comparisons although it is one instruction. A builtin that never
hashes or compares a probe key runs nothing the probe counts, however much it
does, so `list(d)` added to an O(1) operation passes a counted test.

For a given Python version with no other threads running, a count is the same
on every run and every machine. A different Python version can count a
different number of instructions for the same code.

The timed pass uses a `Stopwatch`, which times the same blocks with
`time.perf_counter_ns`. It sees everything the operation does, and it is
noisy.

`memory_complexity` reads `tracemalloc` inside `meter.measuring()`.
`measure="retained"`, the default, reads what the block leaves allocated after
a garbage collection. `measure="peak"` reads the most it held at any moment, so
a copy made and thrown away inside the block still shows.

## Time

```python
from petstore.complexity import Clock, Complexity, Probe, time_complexity

time_complexity(
    Complexity.CONSTANT,                  # any Complexity, or a Growth
    sizes=(100, 1_000, 10_000, 100_000),  # at least two, ascending, spanning the class's minimum
    tolerance=2.0,                        # how far the count may grow past the bound
    granularity="instructions",           # "lines" is faster and blind to one-line loops
    clock=Clock(repeats=50, tolerance=4.0),  # None, the default, runs no timed pass
)
```

The function you write takes `(n, probe)`; the decorator returns a function
that takes nothing, under the same name and docstring, which pytest runs as it
is.

The counted pass runs first: the test is called once per size with a fresh
`Probe`, and the counts are held to the bound within `tolerance`.

With a `Clock`, and only once the counts pass, the timed pass runs size by
size. A run's time is the sum of its `counting()` blocks, the fastest of
`clock.repeats` runs at each size is the reading, and the readings are held to
the bound within `clock.tolerance`. Garbage collection is off inside a timed
block and left as it was found afterwards, and `probe.key(value)` returns the
plain int, so neither adds to what is timed. `probe.tick()` does nothing on the
timed pass, which reads only the clock. `Clock(read=...)` takes any function
returning nanoseconds, which is how the module's own tests drive it with a
clock that moves only when told to.

### When to ask for the timed pass

A count cannot see work inside builtins that never touch the probe key, which
is most of what can go wrong in an operation on a container: a stray copy, a
sum, a drain, a list kept beside a dict. For an operation claimed O(1) on a
container, pass `clock=Clock()`.

It is off by default because a timing depends on the machine. Every reading
carries noise, a large enough cache step can look like growth, and a heavily
loaded machine slows every run of one size. The timed pass also runs the block
`clock.repeats` times per size, so it costs far more than counting.

### Repeating a block: `probe.runs()`

A test that iterates `probe.runs()` makes each iteration one run. The loop
yields once on the counted pass and `clock.repeats` times on the timed pass,
so the test is called once per size on each pass and setup is paid twice per
size in all, which is what makes large sizes affordable. A test that does not
iterate it is called `clock.repeats` times per size on the timed pass, each
call one run, setup and all.

Use `probe.runs()` when the operation can repeat on the same object and leave
it in an equivalent state, and equivalent includes where the probed key sits.
An operation that moves its key, such as a cache `get` making the key most
recently used, would probe a different position on the second run, and since
the fastest run is the reading, one cheap run hides a slow algorithm. Take a
fresh key per run, as the worked example below does. Where repeating would
change what is measured, such as an insert into a container with room, leave
out `probe.runs()` and pay for setup per run, at sizes small enough to afford
it.

### What fails the test

A test that never enters its block fails rather than passing on nothing
measured: a counted call that never enters `probe.counting()`, or a
`memory_complexity` test that never enters `meter.measuring()`.

The timed pass refuses four more mistakes, each of which would mistime a run:

- a timed run that never enters `probe.counting()`, whose reading of zero
  would pass any bound
- in a call that iterates `probe.runs()`, a block before or after the loop,
  which belongs to no run
- leaving `probe.runs()` before it is exhausted: the call never gives a whole
  run, so it would be called again forever
- iterating `probe.runs()` twice in one call, which runs every block a second
  time on setup the first loop has already used

The counted pass has a single run per call, so it counts a block outside the
loop with the rest and refuses none of these; only a test given a `Clock` is
held to them.

Sizes that cannot tell one class from another raise `ValueError` when the
decorator is applied. `Clock` refuses `repeats` under 1, or a `tolerance` of 1
or less, with `petstore.ValidationError`, which is a `ValueError` too.

## Choosing the key

`probe.key()` takes an int and returns one equal to it. Choose the key a wrong
algorithm reaches last. A scan finds the first element at once, so probing the
first key of an insertion-ordered container lets a linear `in` pass as
constant. Probe a key midway through whatever order the structure keeps, or a
key it does not hold, which a scan has to walk all the way past. Write a
separate test per path: hit, miss, insert, replace, evict.

A container keyed by strings or tuples gets no counted view of the comparisons
made in C, so its tests rely on the timed pass for those. `probe.tick(n)` adds
`n` to the count by hand, for work the counted pass cannot otherwise reach.

## Sizes decide what can be seen

Sizes must be at least two, strictly ascending and positive, and must span a
factor large enough for a wrong class to show: 10 for constant, polynomial and
logarithmic classes and for a `Growth` by default, 2 for exponential and
factorial classes, whose growth shows within a doubling and which could not be
run over a wider span anyway. `Growth` takes `min_span` for a class of your
own.

That minimum separates constant from linear, and not constant from
logarithmic. log n grows 1.9 times from 10 to 100, inside the default
tolerance of 2. On the counted pass, separating them needs about 10 to 1,000,
where log n grows 2.9 times. On the timed pass, at a tolerance of 4, it needs
about 10 to 15,000, or 100 to 10^8, so in practice the timed pass cannot tell
constant from logarithmic.

Every reading also carries a fixed cost on top of the work: argument checks,
the call itself, a hash, and on the timed pass the clock, which costs tens of
nanoseconds per `counting()` block, so a run should have one block. A linear
term only shows once it outweighs that cost. As a first approximation, with
tolerance `t`, it is caught when

    per-element cost * largest size  >  (t - 1) * fixed cost

Cache steps bend this, so treat it as a guide to the order of magnitude. It is
why more repeats do not help: they shrink the noise, and the fixed cost is not
noise. In the worked example, a `put` that keeps its eviction queue in a list
and calls `pop(0)` grew 1.3 times from 10 to 3,000 entries, inside the timed
tolerance of 4, and 15.5 times from 100 to 100,000. This holds for the counted
pass as much as the timed one.

So pick sizes for what the test has to see:

- Push the largest size until a wrong class would clearly show. For an O(1)
  operation on a container, 100,000 entries is a good default. A test that
  runs too long is a reason to use `probe.runs()` before it is a reason to
  shrink the sizes.
- When the API caps its sizes, a bound tested only up to the cap says almost
  nothing. Test the algorithm past it through a declared seam, such as a test
  subclass that widens limits the class declares, as the worked example does.

## Bounds, not classifications

A growth is an upper bound, like the O it stands for, so code faster than its
claim passes: an O(1) operation passes a LINEAR test. A test never says which
class code is in, only that it is no worse than claimed. Divided by the growth
function, the measure at every size must stay within `tolerance` times its
value at the smallest size. Ratios are compared as logarithms, so a growth
function may return an int too large for a float, as `n!` does.

The fastest run at each size is a best case. Work done now and then, such as a
dict resizing as it grows, lands in some runs and not others, and taking the
fastest throws those runs away, so the timed pass holds neither an amortised
nor a worst-case bound: it holds the cheap path. The counted pass reads one
call per size, which includes an occasional cost only if that call happens to
pay it. Where a requirement means amortised or worst case, say so in it, and
test the expensive path on its own, with setup that forces it on every run.

`Complexity` names the usual classes, slowest growing first: `CONSTANT`,
`LOGARITHMIC`, `SQUARE_ROOT`, `LINEAR`, `LINEARITHMIC`, `QUADRATIC`, `CUBIC`,
`EXPONENTIAL` and `FACTORIAL`. `Growth` makes any other:

```python
QUARTIC = Growth("n^4", lambda n: n**4)
```

Anything with a `label`, a growth `function` of n and a `min_span` serves as a
class; `GrowthClass` is that protocol.

`assert_growth(growth, sizes, measured, tolerance=2.0, floor=1)` is the check
on its own, for a measure taken some other way. Readings below `floor` are
raised to it, since below it they are noise and a reading of zero would make
every ratio zero or infinite. The decorators call it with a floor of 1 for
counts and nanoseconds, and `noise` for bytes.

## Memory

With `filled(n)` from the worked example below, a cache holding n entries:

```python
from petstore.complexity import Complexity, Meter, memory_complexity


@memory_complexity(Complexity.CONSTANT, sizes=(100, 1_000, 10_000, 100_000), measure="peak")
def test_get_needs_no_memory_that_grows(n: int, meter: Meter) -> None:
    cache = filled(n)
    with meter.measuring():
        cache.get(n // 2)
```

`memory_complexity` calls the test once per size with a fresh `Meter`; memory
readings do not need repeats. Build everything the bound is not about outside
`meter.measuring()`. Objects made before the block do not count; objects made
inside it do, including keys and values built in a loop there. Use
`measure="retained"` for what an operation keeps and `measure="peak"` for what
it needs on the way, which is what catches a hidden copy.

Readings under `noise` bytes, 4,096 by default, are raised to `noise`. For a
CONSTANT bound that floor is what lets a correct operation pass, since its
readings are allocator slack. For a class that should grow, start the sizes
where the smallest reading clears the floor: a smallest reading raised to it
loosens the tolerance at every other size. `tracemalloc` sees only what
Python's allocators hand out, so memory a C extension takes from `malloc`
directly does not show.

## Show the test failing

When writing a complexity test, break the operation and confirm the test goes
red, then restore it. A mutant a test survives is either a gap in the test or a
limit of the measure, and the table under "What each measure sees" says which.

Try these on a container operation claimed O(1). Each was run against the
worked example's cache, with its complexity tests on the timed pass, and was
caught by the measure shown:

| Mutant | Caught by |
|---|---|
| `key in list(entries)` in place of `key in entries` | counted, peak memory |
| a recency list kept beside the dict, updated with `remove(key)` and evicted with `pop(0)` | counted, and timed on the evicting put |
| `list(entries)` added | timed, peak memory |
| `sum(entries.values())` added | timed |
| `[None] * len(entries)` added | timed, peak memory |
| `deque(iter(entries), maxlen=0)` added | timed |
| an eviction queue in a list, with `pop(0)` | timed, at 100,000 entries |
| a recency list updated with `insert(0, key)` | timed |

## Writing the requirement

Say what n is, which operation, and the bound: "get shall do O(1) work in the
number of entries held, whether it finds the key or not". A requirement that
leaves n unnamed cannot be tested, because nobody knows what to grow. Where the
API caps n, the requirement is about the algorithm, and the test says so by
testing past the cap.

## Reading a failure

A failure names the class expected, the sizes, the readings and how far they
grew past the tolerance, then the measure in brackets: `operations counted`,
`nanoseconds, fastest of 50 runs`, `bytes retained` or `bytes peak`. The five
mistakes above each fail with their own message. A `ValueError` from bad sizes
shows as an error when the test module is collected, since the decorator raises
it as it is applied.

A counted failure reproduces for a given Python version with no other threads
running. A timed failure on code that passes the counted pass has one of four
causes: work inside a builtin, a CPU cache step large enough to pass the
tolerance, an amortised cost such as a resize that every run repeats because
the test rebuilds its object per run, or a machine loaded hard enough to slow
every run of one size. The first three reproduce; rerun it before trusting it.

## Worked example: an LRU cache

This is a cache of int values by int key with O(1) `get` and `put`, kept in an
`OrderedDict` that is both the index and the eviction queue. It is the cache
the figures and the mutant table above were measured on. Its public class caps
capacity at 3,000 entries, too few for a cheap linear term to show, so its
complexity tests use a subclass that widens the limits the class declares:

```python
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

from petstore import Rule, Validated, ValidationError, validate
from petstore.complexity import Clock, Complexity, Probe, time_complexity

MISSING = -1
SIZES = (100, 1_000, 10_000, 100_000)
WIDE = 10_000_000


def int_in_range(low: int, high: int) -> Callable[[object], None]:
    """Return a rule refusing anything but an int from low to high."""

    def rule(value: object) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            message = f"must be an int from {low} to {high}, not {value!r}"
            raise ValidationError(message)

    return rule


@dataclass(frozen=True, eq=False)
class LRUCache:
    """Holds up to capacity entries, evicting the least recently used to make room."""

    capacity: Validated[int] = Validated(int_in_range(1, 3_000))
    key_rule: ClassVar[Rule[object]] = int_in_range(0, 10_000)
    value_rule: ClassVar[Rule[object]] = int_in_range(0, 100_000)
    _entries: OrderedDict[int, int] = field(default_factory=OrderedDict, init=False, repr=False)

    def get(self, key: int) -> int:
        """Return the value held under key, making it most recently used, or MISSING."""
        validate(key, type(self).key_rule, label="key")
        if key not in self._entries:
            return MISSING
        self._entries.move_to_end(key)
        return self._entries[key]

    def put(self, key: int, value: int) -> None:
        """Hold value under key as the most recently used entry, evicting the least recently used if full."""
        validate(key, type(self).key_rule, label="key")
        validate(value, type(self).value_rule, label="value")
        if key in self._entries:
            self._entries.move_to_end(key)
        elif len(self._entries) == self.capacity:
            self._entries.popitem(last=False)
        self._entries[key] = value


@dataclass(frozen=True, eq=False)
class Unbounded(LRUCache):
    """The cache with limits wide enough to measure its algorithm at scale."""

    capacity: Validated[int] = Validated(int_in_range(1, WIDE))
    key_rule: ClassVar[Rule[object]] = int_in_range(0, WIDE)
    value_rule: ClassVar[Rule[object]] = int_in_range(0, WIDE)


def filled(n: int) -> LRUCache:
    """Return a full Unbounded cache holding keys 0 to n - 1, key 0 least recently used."""
    cache = Unbounded(n)
    for key in range(n):
        cache.put(key, key)
    return cache


@time_complexity(Complexity.CONSTANT, sizes=SIZES, clock=Clock())
def test_get_of_a_held_key_does_not_grow_with_size(n: int, probe: Probe) -> None:
    """A hit on a key midway through the recency order costs the same at any size."""
    cache = filled(n)  # setup, once per size, never measured
    for run, _ in enumerate(probe.runs()):
        key = probe.key(n // 4 + run % (n // 2))
        with probe.counting():
            cache.get(key)  # the one operation the requirement names
```

A `get` moves its key to the most recent end, so the runs cycle through the
middle half of the keys, n / 4 to 3n / 4. The keys below n / 4 and from 3n / 4
up are never touched, so none of them is ever more recent than a touched key,
and the key each run touches has at least n / 4 keys on either side of it in
the recency order, for any number of runs. A scan from either end walks past
n / 4 keys to reach it. Counting up
from `n // 2` instead runs off the end of the keys once the runs outnumber
n / 2, and the later runs quietly measure misses.

A `put` that evicts can repeat if each run inserts a key the cache does not
hold, so it stays full. An insert into a cache with room cannot, since it
leaves the cache full, so that test rebuilds the cache per run and stops at
10,000 entries to stay affordable.

The class reads its rules through `type(self)`: a plain function stored on a
class becomes a bound method when read through `self`, and the rule would
receive the cache as its value. The public class keeps its limits, and its own
tests still hold them.

## Limits

Complexity tests measure the whole process, so they only mean something with no
other threads working: `sys.monitoring` events are process-wide, so a `Probe`
also counts what other threads run while `counting()` is open, and a busy
thread slows the timed runs. A garbage collection inside a counted block runs
finalizers whose instructions are counted too.

The timed pass assumes no per-line tracer is active, since a tracer adds a
fixed cost to every reading and hides growth behind it. coverage measures
through `sys.monitoring` by default from Python 3.14, which
[`docs/DECISIONS/python-3.14-is-the-floor.md`](../DECISIONS/python-3.14-is-the-floor.md)
records as the reason for petstore's floor. coverage still uses a
`sys.settrace` tracer when its `timid` or `core` setting asks for one, and
falls back to one for dynamic contexts or a `concurrency` setting such as
`gevent`; where one is active, show a timed test failing with the suite run
outside coverage.

## Requirements

[`docs/REQUIREMENTS/complexity/`](../REQUIREMENTS/complexity/) holds this
module's requirements, `FR-8.x`, one file each. Tests cite them with a
`# COVERS <ids> | <kind>` comment directly above the test.
