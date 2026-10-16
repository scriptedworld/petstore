"""Test decorators that hold code to a time or memory complexity.

A complexity claim is checked by running the same work at several sizes and
comparing how a measure grows:

    @time_complexity(Complexity.CONSTANT, sizes=(100, 1_000, 10_000, 100_000), clock=Clock())
    def test_get_is_constant(n: int, probe: Probe) -> None:
        cache = filled(n)                            # setup, not measured: n entries
        for run, _ in enumerate(probe.runs()):
            key = probe.key(n // 4 + run % (n // 2))  # midway, where a scan arrives late
            with probe.counting():
                cache.get(key)                       # the work: measured

    @memory_complexity(Complexity.CONSTANT, sizes=(1_000, 10_000, 100_000))
    def test_memory_stays_bounded(n: int, meter: Meter) -> None:
        cache = Cache(capacity=10)                   # any container of fixed capacity
        with meter.measuring():
            for i in range(n):
                cache.put(i, i)

``time_complexity`` counts first. Inside ``counting()`` a ``Probe`` counts
every bytecode instruction run, through ``sys.monitoring``, and every hash and
comparison made on a key from ``probe.key()``, so ``key in some_list`` counts
n comparisons in one instruction. The count is the same on every run for a
given Python version with no other threads running. It cannot see a builtin
that walks a container without hashing or comparing a probe key: ``list(d)``,
``sum(d.values())`` and ``[None] * len(d)`` run no instruction it counts.

``clock=Clock()`` adds a timed pass, which sees that work. Once the counts
pass, the test runs again under a ``Stopwatch``, ``Clock.repeats`` runs per
size, and the fastest run at each size is held to the bound within
``Clock.tolerance``. It is off by default, because a timing depends on the
machine where a count does not. ``probe.runs()`` repeats a block on one setup:
it yields once when counted and ``Clock.repeats`` times when timed.

A ``Meter`` reads ``tracemalloc`` inside ``measuring()``: what the block leaves
allocated after a collection, or with ``measure="peak"`` the most it held at
once, so a copy thrown away inside the block still shows.

A growth is an upper bound, like the O it stands for. Divided by the growth
function, the measure at every size must stay within ``tolerance`` times its
value at the smallest size. Sizes must span a factor of 10 for polynomial
classes and 2 for exponential and factorial ones. ``Complexity`` names the
usual classes; ``Growth`` makes any other. A decorated test takes no arguments,
so pytest runs it as it is, and a test that measures nothing fails.

``docs/modules/complexity.md`` is the guide: what each measure sees, how to
choose sizes and keys, and how to show a test failing.

Not thread-safe, and only meaningful single-threaded: ``sys.monitoring`` events
are process-wide, so a Probe also counts what other threads run while
``counting()`` is open, and a timed block absorbs it.
"""

from __future__ import annotations

import gc
import math
import sys
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from typing import TYPE_CHECKING, Literal, Protocol, Self

from .validation import ValidationError, validate

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from types import CodeType

__all__ = [
    "Clock",
    "Complexity",
    "Growth",
    "GrowthClass",
    "Meter",
    "Probe",
    "Stopwatch",
    "assert_growth",
    "memory_complexity",
    "time_complexity",
]

MIN_SIZES = 2
POLYNOMIAL_SPAN = 10
"""Sizes for a polynomial class must span this factor, or the next class up cannot show."""
SUPERPOLYNOMIAL_SPAN = 2
"""Exponential and factorial growth shows within a doubling, and cannot be run over a wider one."""
LARGEST_SHOWN = 50.0
"""Factors with a natural log above this are written as a power of ten."""
DEFAULT_TOLERANCE = 2.0
MEMORY_NOISE = 4096
"""Bytes below which a memory reading is noise: allocator slack, frames, the interpreter's own bookkeeping."""


class GrowthClass(Protocol):
    """Anything with a label, as written inside O(...), a growth function of n, and the span its sizes need."""

    @property
    def label(self) -> str:
        """The class as written inside O(...)."""

    @property
    def function(self) -> Callable[[int], float]:
        """How the class grows with n; it may return an int too large for a float."""

    @property
    def min_span(self) -> int:
        """How many times the largest size must exceed the smallest for a faster class to show."""


@dataclass(frozen=True)
class Growth:
    """A complexity class not in Complexity: its label, its growth function and the span its sizes need."""

    label: str
    function: Callable[[int], float]
    min_span: int = POLYNOMIAL_SPAN


class Complexity(Enum):
    """The usual complexity classes, slowest growing first."""

    CONSTANT = ("1", lambda _: 1)
    LOGARITHMIC = ("log n", lambda n: math.log2(n + 1))
    SQUARE_ROOT = ("sqrt n", math.sqrt)
    LINEAR = ("n", lambda n: n)
    LINEARITHMIC = ("n log n", lambda n: n * math.log2(n + 1))
    QUADRATIC = ("n^2", lambda n: n**2)
    CUBIC = ("n^3", lambda n: n**3)
    EXPONENTIAL = ("2^n", lambda n: 2**n, SUPERPOLYNOMIAL_SPAN)
    FACTORIAL = ("n!", math.factorial, SUPERPOLYNOMIAL_SPAN)

    def __init__(self, label: str, function: Callable[[int], float], min_span: int = POLYNOMIAL_SPAN) -> None:
        """Hold the label, growth function and size span each member is defined with."""
        self.label = label
        self.function = function
        self.min_span = min_span


def _check_sizes(sizes: Sequence[int], min_span: int) -> None:
    """Refuse sizes that could not tell one growth from another."""
    shown = tuple(sizes)
    if len(sizes) < MIN_SIZES:
        message = f"need at least {MIN_SIZES} sizes, not {shown}"
    elif any(low >= high for low, high in pairwise(sizes)):
        message = f"sizes must be strictly ascending, not {shown}"
    elif sizes[0] < 1:
        message = f"sizes must be positive, not {shown}"
    elif sizes[-1] < min_span * sizes[0]:
        message = f"sizes must span at least a factor of {min_span}, not {sizes[0]} to {sizes[-1]}"
    else:
        return
    raise ValueError(message)


def _times(log_factor: float) -> str:
    """Write a factor given as its natural log, without overflowing a float."""
    if log_factor < LARGEST_SHOWN:
        return f"{math.exp(log_factor):.1f}x"
    return f"about 10^{log_factor / math.log(10):.0f}x"


def assert_growth(
    growth: GrowthClass,
    sizes: Sequence[int],
    measured: Sequence[float],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    floor: float = 1,
) -> None:
    """Fail unless measured, taken at sizes, grows no faster than growth allows.

    Readings below floor are raised to it: below it they are noise, and a
    reading of zero would make every ratio zero or infinite. Ratios are
    compared as logs, so a growth such as n! may exceed any float.
    """
    _check_sizes(sizes, growth.min_span)
    log_ratios = [math.log(max(value, floor)) - math.log(growth.function(n)) for n, value in zip(sizes, measured, strict=True)]
    worst = max(log_ratios) - log_ratios[0]
    if worst > math.log(tolerance):
        message = (
            f"expected O({growth.label}), but at sizes {tuple(sizes)} measured {tuple(measured)}: "
            f"measure over {growth.label} grew {_times(worst)}, more than the {tolerance}x allowed"
        )
        raise AssertionError(message)


@dataclass(frozen=True)
class _Unit:
    """What a decorator measures, as named in its failures, and its noise floor."""

    name: str
    floor: float


def _assert_labelled(growth: GrowthClass, sizes: Sequence[int], measured: Sequence[float], *, tolerance: float, unit: _Unit) -> None:
    """Run assert_growth, naming what was measured in any failure."""
    try:
        assert_growth(growth, sizes, measured, tolerance=tolerance, floor=unit.floor)
    except AssertionError as failure:
        message = f"{failure} ({unit.name})"
        raise AssertionError(message) from None


class _ProbeKey(int):
    """An int that tells its probe about every hash and comparison made on it."""

    _probe: Probe

    def __new__(cls, value: int, probe: Probe) -> Self:
        key = super().__new__(cls, value)
        key._probe = probe
        return key

    def __hash__(self) -> int:
        self._probe.tick()
        return super().__hash__()

    def __eq__(self, other: object) -> bool:
        self._probe.tick()
        return super().__eq__(other)

    def __ne__(self, other: object) -> bool:
        self._probe.tick()
        return super().__ne__(other)

    def __lt__(self, other: int) -> bool:
        self._probe.tick()
        return super().__lt__(other)

    def __le__(self, other: int) -> bool:
        self._probe.tick()
        return super().__le__(other)

    def __gt__(self, other: int) -> bool:
        self._probe.tick()
        return super().__gt__(other)

    def __ge__(self, other: int) -> bool:
        self._probe.tick()
        return super().__ge__(other)


def _free_monitoring_tool() -> int:
    """Return a sys.monitoring tool id no one is using, such as coverage or a debugger."""
    for tool in range(6):
        if sys.monitoring.get_tool(tool) is None:
            return tool
    message = "every sys.monitoring tool id is in use"
    raise RuntimeError(message)


Granularity = Literal["lines", "instructions"]


class Probe:
    """Counts the work done inside counting(): Python instructions (or lines) run, operations on its keys, and ticks."""

    def __init__(self, granularity: Granularity = "instructions") -> None:
        """Start at zero, not counting, counting Python work at granularity."""
        self.granularity = granularity
        self.count = 0
        self.entered = False
        self._counting = False

    def key(self, value: int) -> int:
        """Return an int equal to value that counts each hash and comparison made on it."""
        return _ProbeKey(value, self)

    def tick(self, n: int = 1) -> None:
        """Count n units of work, if counting."""
        if self._counting:
            self.count += n

    def runs(self) -> Iterator[None]:
        """Yield once: a count does not vary from run to run, so one run is the reading."""
        yield

    def _step(self, code: CodeType, where: int) -> None:
        del code, where
        self.tick()

    @contextmanager
    def counting(self) -> Iterator[None]:
        """Count work done inside the block; setup outside it is free."""
        monitoring = sys.monitoring
        event = monitoring.events.LINE if self.granularity == "lines" else monitoring.events.INSTRUCTION
        tool = _free_monitoring_tool()
        monitoring.use_tool_id(tool, "complexity probe")
        monitoring.register_callback(tool, event, self._step)
        self.entered = self._counting = True
        monitoring.set_events(tool, event)
        try:
            yield
        finally:
            monitoring.set_events(tool, monitoring.events.NO_EVENTS)
            self._counting = False
            monitoring.register_callback(tool, event, None)
            monitoring.free_tool_id(tool)


def _at_least_one(value: int) -> None:
    if value < 1:
        message = f"must be at least 1, not {value!r}"
        raise ValidationError(message)


def _above_one(value: float) -> None:
    if not value > 1:
        message = f"must be more than 1, not {value!r}"
        raise ValidationError(message)


@dataclass(frozen=True)
class Clock:
    """How the timed pass runs: timed runs per size, the growth it allows, and the clock it reads in nanoseconds."""

    repeats: int = 50
    tolerance: float = 4.0
    read: Callable[[], int] = time.perf_counter_ns

    def __post_init__(self) -> None:
        """Refuse settings that cannot give a reading."""
        validate(self.repeats, _at_least_one, label="repeats")
        validate(self.tolerance, _above_one, label="tolerance")


def _outside_runs() -> None:
    message = "probe.counting() outside probe.runs() belongs to no run; put every block inside the loop"
    raise AssertionError(message)


class Stopwatch(Probe):
    """A Probe whose runs are timed rather than counted, and whose keys are plain ints.

    Until the test iterates runs(), the whole call is one run. tick() does
    nothing here: a timed run reads only the clock.
    """

    def __init__(self, clock: Clock) -> None:
        """Start one run, timed by clock.read."""
        super().__init__()
        self._clock = clock
        self._times: list[int] = []
        self._run = 0
        self._run_entered = False
        self._iterated = False
        self._exhausted = False
        self._open = True

    def key(self, value: int) -> int:
        """Return value itself, so the probe adds no work to what is timed."""
        return value

    def runs(self) -> Iterator[None]:
        """Yield Clock.repeats times, each iteration one run; a block outside the loop fails the test."""
        if self._iterated:
            message = "probe.runs() iterated more than once in one call; iterate it once"
            raise AssertionError(message)
        if self._run_entered:
            _outside_runs()
        self._iterated = True
        self._open = False
        for _ in range(self._clock.repeats):
            self._run, self._run_entered, self._open = 0, False, True
            try:
                yield
            finally:
                self._open = False
            self._close_run()
        self._exhausted = True

    def times(self) -> list[int]:
        """Return the time of every run, closing the whole-call run if runs() was never iterated."""
        if not self._iterated:
            self._close_run()
        elif not self._exhausted:
            # Calling the test again would leave early again, forever.
            message = "the test left probe.runs() before it was exhausted; iterate it in full"
            raise AssertionError(message)
        return self._times

    def _close_run(self) -> None:
        if not self._run_entered:
            message = "a timed run never entered probe.counting(), so it measured nothing"
            raise AssertionError(message)
        self._times.append(self._run)

    @contextmanager
    def counting(self) -> Iterator[None]:
        """Time the block into the current run with garbage collection off, then leave collection as it was found."""
        if not self._open:
            _outside_runs()
        self.entered = self._run_entered = True
        collecting = gc.isenabled()
        gc.disable()
        read = self._clock.read
        try:
            start = read()
            yield
            self._run += read() - start
        finally:
            if collecting:
                gc.enable()


class Meter:
    """Reads the memory used inside measuring(): what it leaves allocated, and the most it held at once."""

    def __init__(self) -> None:
        """Start with nothing read."""
        self.retained = 0
        self.peak = 0
        self.entered = False

    @contextmanager
    def measuring(self) -> Iterator[None]:
        """Measure memory allocated inside the block; setup outside it is free."""
        self.entered = True
        gc.collect()
        started = not tracemalloc.is_tracing()
        if started:
            tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            before = tracemalloc.get_traced_memory()[0]
            yield
            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            self.retained, self.peak = current - before, peak - before
        finally:
            if started:
                tracemalloc.stop()


def _named_like[F: Callable[..., object]](run: F, test: Callable[..., object]) -> F:
    """Give run the test's name and docstring, without the signature pytest would read as fixtures."""
    run.__name__ = test.__name__
    run.__qualname__ = test.__qualname__
    run.__doc__ = test.__doc__
    run.__module__ = test.__module__
    return run


def _require_entered(test: Callable[..., object], block: str, *, entered: bool) -> None:
    """Refuse a test whose block never ran, rather than passing it on nothing measured."""
    if not entered:
        message = f"{test.__name__} never entered {block}, so it measured nothing"
        raise AssertionError(message)


def _counts(test: Callable[[int, Probe], None], sizes: Sequence[int], granularity: Granularity) -> list[int]:
    """Run test once per size under a fresh counting Probe and return the counts."""
    counts = []
    for n in sizes:
        probe = Probe(granularity)
        test(n, probe)
        _require_entered(test, "probe.counting()", entered=probe.entered)
        counts.append(probe.count)
    return counts


def _fastest(test: Callable[[int, Probe], None], n: int, clock: Clock) -> int:
    """Run test at size n under fresh Stopwatches until clock.repeats runs are timed, and return the fastest."""
    times: list[int] = []
    while len(times) < clock.repeats:
        watch = Stopwatch(clock)
        test(n, watch)
        times.extend(watch.times())
    return min(times)


def time_complexity(
    growth: GrowthClass,
    *,
    sizes: Sequence[int],
    tolerance: float = DEFAULT_TOLERANCE,
    granularity: Granularity = "instructions",
    clock: Clock | None = None,
) -> Callable[[Callable[[int, Probe], None]], Callable[[], None]]:
    """Hold a test's counted work to growth within tolerance, then, given a clock, its fastest timed run within clock.tolerance."""
    _check_sizes(sizes, growth.min_span)

    def decorate(test: Callable[[int, Probe], None]) -> Callable[[], None]:
        def run() -> None:
            counted = _Unit("operations counted", 1)
            _assert_labelled(growth, sizes, _counts(test, sizes, granularity), tolerance=tolerance, unit=counted)
            if clock is None:
                return
            timed = _Unit(f"nanoseconds, fastest of {clock.repeats} runs", 1)
            _assert_labelled(growth, sizes, [_fastest(test, n, clock) for n in sizes], tolerance=clock.tolerance, unit=timed)

        return _named_like(run, test)

    return decorate


def memory_complexity(
    growth: GrowthClass,
    *,
    sizes: Sequence[int],
    tolerance: float = DEFAULT_TOLERANCE,
    measure: Literal["retained", "peak"] = "retained",
    noise: int = MEMORY_NOISE,
) -> Callable[[Callable[[int, Meter], None]], Callable[[], None]]:
    """Hold the memory a test uses inside meter.measuring(), run at each size, to growth.

    "retained" reads what the block leaves allocated, "peak" the most it
    allocated at any moment. Readings under noise bytes count as noise.
    """
    _check_sizes(sizes, growth.min_span)

    def decorate(test: Callable[[int, Meter], None]) -> Callable[[], None]:
        def run() -> None:
            used = []
            for n in sizes:
                meter = Meter()
                test(n, meter)
                _require_entered(test, "meter.measuring()", entered=meter.entered)
                used.append(meter.retained if measure == "retained" else meter.peak)
            _assert_labelled(growth, sizes, used, tolerance=tolerance, unit=_Unit(f"bytes {measure}", noise))

        return _named_like(run, test)

    return decorate
