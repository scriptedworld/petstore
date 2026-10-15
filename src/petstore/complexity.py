"""Test decorators that hold code to a time or memory complexity.

A complexity claim is checked by running the same work at several sizes and
comparing how a deterministic measure grows, never by timing it:

    @time_complexity(Complexity.CONSTANT, sizes=(10, 100, 1_000))
    def test_get_is_constant(n: int, probe: Probe) -> None:
        cache = filled(n)                  # setup: not counted
        with probe.counting():
            cache.get(probe.key(0))        # the work: counted

    @memory_complexity(Complexity.CONSTANT, sizes=(1_000, 10_000, 100_000))
    def test_memory_stays_bounded(n: int, meter: Meter) -> None:
        cache = Cache(capacity=10)
        with meter.measuring():
            for i in range(n):
                cache.put(i, i)

Inside ``counting()`` a ``Probe`` counts two kinds of work, so neither hides:

    every bytecode instruction     catches loops in Python code, however they
    executed                       reach their data (via ``sys.monitoring``),
                                   including loops packed into one line such
                                   as a comprehension
    every hash and comparison on   catches work inside C builtins, where
    a key from ``probe.key()``     ``key in some_list`` compares n times in
                                   one line

``granularity="lines"`` counts lines instead: faster, but blind to a loop
that stays on one line, so a comprehension over n items reads as constant.
``probe.tick(n)`` counts anything else by hand. A ``Meter`` reads memory with
``tracemalloc`` inside ``measuring()``: what the block leaves allocated, or with
``measure="peak"`` the most it allocated at once, so auxiliary space can be held
to a bound as well as retained space.

A growth is an upper bound, like the O it stands for. Divided by the growth
function, the measure at every size must stay within ``tolerance`` times its
value at the smallest size. Sizes must span a factor large enough for a wrong
class to show: 10 for polynomial classes (linear work held to constant over
sizes 10 to 1,000 grows 100 times, far past the default tolerance of 2), 2 for
exponential and factorial ones, whose growth shows within a doubling and which
could not be run over a wider span anyway.

``Complexity`` names the usual classes, from constant to factorial; ``Growth``
makes any other, such as ``Growth("n^4", lambda n: n**4)``. Growth is compared
in log space, so a growth function may return an int too large for a float. A test that never enters its counting or
measuring block fails rather than passing on nothing. A decorated test takes no
arguments, so pytest runs it as it is.

Not thread-safe, and only meaningful single-threaded: ``sys.monitoring`` events
are process-wide, so a Probe also counts instructions that other threads run
while ``counting()`` is open. Run complexity tests with no other threads busy.
"""

from __future__ import annotations

import gc
import math
import sys
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from typing import TYPE_CHECKING, Literal, Protocol, Self

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from types import CodeType

__all__ = [
    "Complexity",
    "Growth",
    "GrowthClass",
    "Meter",
    "Probe",
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


def time_complexity(
    growth: GrowthClass,
    *,
    sizes: Sequence[int],
    tolerance: float = DEFAULT_TOLERANCE,
    granularity: Granularity = "instructions",
) -> Callable[[Callable[[int, Probe], None]], Callable[[], None]]:
    """Hold a test's counted work, run at each size with a fresh Probe counting at granularity, to growth."""
    _check_sizes(sizes, growth.min_span)

    def decorate(test: Callable[[int, Probe], None]) -> Callable[[], None]:
        def run() -> None:
            counts = []
            for n in sizes:
                probe = Probe(granularity)
                test(n, probe)
                _require_entered(test, "probe.counting()", entered=probe.entered)
                counts.append(probe.count)
            _assert_labelled(growth, sizes, counts, tolerance=tolerance, unit=_Unit("operations counted", 1))

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
