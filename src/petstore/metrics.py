"""Open-ended metrics, and a recorder holding them by name.

A metric is an object that records and reports: a ``Counter`` counts how often
something happens, a ``Measure`` records values. Each is callable, so the code
being measured holds the metric and calls it. A ``StatsRecorder`` holds
metrics by name, so one snapshot or reset reaches all of them, and holds any
other kind of ``Metric`` added to it:

    recorder = StatsRecorder()
    hits = recorder.counter("hits")
    load = recorder.measure("page_load", keep=All(), under=(1.0, 5.0))

    hits()          # one more
    hits(3)         # three more
    load(2.4)       # one observation

    d = recorder.snapshot().measures["page_load"]
    d.mean, d.stdev            # running, exact, O(1) memory
    d.quantile(0.85)           # p85, from the kept values
    d.under(5.0)               # u5: the share of loads under 5.0

What a measure answers depends on what it keeps, chosen when it is made:

    nothing kept       count, total, min, max, mean and stdev, always exact
    under=(...)        u[x] for each declared x, exact over all time in O(1)
                       memory, with no observation kept
    keep=All()         any p[x] or u[x] chosen afterwards, exact; memory grows
                       with every observation
    keep=Last(n)       any p[x] or u[x] over the most recent n, on the
                       snapshot's ``sample``

Everything a ``Distribution`` answers directly is exact over every observation
since the last reset. Statistics over a recent window are only reached through
``Distribution.sample``, so a p95 cannot silently change from all-time to
recent when a window fills.

Quantiles interpolate linearly between the two nearest ranks, numpy's default
and ``statistics.quantiles(method="inclusive")``, so ``quantile(0)`` is the
minimum and ``quantile(1)`` the maximum.

A metric works on its own as well, without a recorder.

Not thread-safe. Recording is a read-modify-write on a metric's state, so two
threads recording at once can lose an update. Give each thread its own
recorder, or guard calls with a lock of your own.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from bisect import bisect_left, bisect_right
from collections import deque
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

__all__ = [
    "All",
    "Counter",
    "Distribution",
    "Last",
    "Measure",
    "Metric",
    "Sample",
    "StatsError",
    "StatsRecorder",
    "StatsSnapshot",
]


class StatsError(ValueError):
    """Raised for a question a measure cannot answer, or a name used two ways."""


class Metric[S](ABC):
    """Something that records, reports what it has recorded as a snapshot of type S, and resets."""

    @abstractmethod
    def snapshot(self) -> S:
        """Return what has been recorded, unaffected by later recording."""

    @abstractmethod
    def reset(self) -> None:
        """Forget everything recorded, in place, so whoever holds the metric keeps recording into it."""


class Counter(Metric[int]):
    """Counts how often something happens: each call adds n, one by default."""

    def __init__(self) -> None:
        """Start at zero."""
        self._value = 0

    def __call__(self, n: int = 1) -> None:
        """Add n, refusing to go down."""
        if n < 0:
            message = f"a count only goes up, not by {n}"
            raise StatsError(message)
        self._value += n

    def snapshot(self) -> int:
        """Return the count."""
        return self._value

    def reset(self) -> None:
        """Return to zero."""
        self._value = 0


@dataclass(frozen=True)
class All:
    """Keep every observation: exact answers to any question, memory growing with use."""


@dataclass(frozen=True)
class Last:
    """Keep only the most recent size observations."""

    size: int

    def __post_init__(self) -> None:
        """Refuse a window that could hold nothing."""
        if self.size < 1:
            message = f"a window must hold at least 1 observation, not {self.size}"
            raise StatsError(message)


def _share(count: int, total: int) -> float:
    """Return count as a share of total, refusing an empty total."""
    if not total:
        message = "no observations"
        raise StatsError(message)
    return count / total


@dataclass(frozen=True)
class Sample:
    """Kept observations, sorted, with the questions any set of values can answer."""

    values: tuple[float, ...]

    def quantile(self, q: float) -> float:
        """Return the value a share q of the observations fall at or below, interpolating linearly."""
        if not 0 <= q <= 1:
            message = f"a quantile must be from 0 to 1, not {q}"
            raise StatsError(message)
        if not self.values:
            message = "no observations"
            raise StatsError(message)
        position = q * (len(self.values) - 1)
        low = math.floor(position)
        high = min(low + 1, len(self.values) - 1)
        return self.values[low] + (self.values[high] - self.values[low]) * (position - low)

    def quantiles(self, *qs: float) -> tuple[float, ...]:
        """Return quantile(q) for each q, in the order given."""
        return tuple(self.quantile(q) for q in qs)

    def under(self, x: float, *, inclusive: bool = False) -> float:
        """Return the share of observations below x, or at or below it when inclusive."""
        below = bisect_right(self.values, x) if inclusive else bisect_left(self.values, x)
        return _share(below, len(self.values))


@dataclass(frozen=True)
class Distribution:
    """A snapshot of one measure. Everything it answers directly covers every observation.

    min, max, mean and stdev are None before the first observation. stdev is
    the population standard deviation of what was observed.
    """

    count: int
    total: float
    min: float | None
    max: float | None
    mean: float | None
    stdev: float | None
    sample: Sample | None
    """The kept observations: every one under keep=All(), the recent ones under keep=Last(n)."""
    complete: bool
    """Whether sample holds every observation, so it can answer for all of them."""
    thresholds: Mapping[float, tuple[int, int]]
    """For each declared x, the counts of observations below it and at or below it."""

    def quantile(self, q: float) -> float:
        """Return p[q] over every observation; needs keep=All()."""
        return self._all_values("quantile").quantile(q)

    def quantiles(self, *qs: float) -> tuple[float, ...]:
        """Return quantile(q) for each q, in the order given; needs keep=All()."""
        return self._all_values("quantiles").quantiles(*qs)

    def under(self, x: float, *, inclusive: bool = False) -> float:
        """Return u[x], the share of every observation below x; needs x declared or keep=All()."""
        if x in self.thresholds:
            below, at_or_below = self.thresholds[x]
            return _share(at_or_below if inclusive else below, self.count)
        if self.complete and self.sample is not None:
            return self.sample.under(x, inclusive=inclusive)
        declared = ", ".join(map(str, self.thresholds)) or "none"
        message = f"u[{x}] needs {x} declared in under=(...) or keep=All(); declared: {declared}"
        raise StatsError(message)

    def _all_values(self, question: str) -> Sample:
        """Return the sample if it holds every observation, refusing otherwise."""
        if self.complete and self.sample is not None:
            return self.sample
        if self.sample is None:
            message = f"{question} needs kept observations: measure with keep=All()"
        else:
            message = f"{question} over every observation needs keep=All(); this keeps a window, so ask .sample"
        raise StatsError(message)


@dataclass(frozen=True)
class StatsSnapshot:
    """Every metric's snapshot by name, as they stood when the snapshot was taken.

    metrics holds whatever each metric reports, whatever its kind; count and
    distribution read one back typed, and counts and measures view them all.
    """

    metrics: Mapping[str, object]

    def count(self, name: str) -> int:
        """Return the counter under name."""
        return self._typed(name, int, "counter")

    def distribution(self, name: str) -> Distribution:
        """Return the measure under name."""
        return self._typed(name, Distribution, "measure")

    @property
    def counts(self) -> Mapping[str, int]:
        """Every counter by name."""
        return MappingProxyType({name: value for name, value in self.metrics.items() if isinstance(value, int)})

    @property
    def measures(self) -> Mapping[str, Distribution]:
        """Every measure by name."""
        return MappingProxyType({name: value for name, value in self.metrics.items() if isinstance(value, Distribution)})

    def _typed[T](self, name: str, kind: type[T], label: str) -> T:
        value = self.metrics[name]
        if not isinstance(value, kind):
            message = f"{name!r} is not a {label}"
            raise StatsError(message)
        return value


class Measure(Metric[Distribution]):
    """Records values: a running summary always, plus whatever keep and under ask for."""

    def __init__(self, *, keep: All | Last | None = None, under: Iterable[float] = ()) -> None:
        """Keep the observations keep asks for, and count observations under each x in under."""
        self._keep = keep
        self._under = tuple(sorted(set(under)))
        self.reset()

    @property
    def keep(self) -> All | Last | None:
        """What this measure keeps, fixed when it is made."""
        return self._keep

    @property
    def under(self) -> tuple[float, ...]:
        """The thresholds this measure counts under, sorted, fixed when it is made."""
        return self._under

    def reset(self) -> None:
        """Forget every observation."""
        self._count = 0
        self._total = 0.0
        self._low: float | None = None
        self._high: float | None = None
        # Welford's running mean and sum of squared deviations: exact, stable, O(1).
        self._mean = 0.0
        self._squares = 0.0
        # Observations are counted at the first threshold they fall under, one
        # slot per threshold plus one for above them all; a snapshot sums them.
        self._starts_below = [0] * (len(self.under) + 1)
        self._starts_at_or_below = [0] * (len(self.under) + 1)
        self._kept: list[float] | deque[float] | None = None
        if isinstance(self.keep, All):
            self._kept = []
        elif isinstance(self.keep, Last):
            self._kept = deque(maxlen=self.keep.size)

    def __call__(self, x: float) -> None:
        """Record one observation."""
        self._count += 1
        self._total += x
        self._low = x if self._low is None else min(self._low, x)
        self._high = x if self._high is None else max(self._high, x)
        delta = x - self._mean
        self._mean += delta / self._count
        self._squares += delta * (x - self._mean)
        self._starts_below[bisect_right(self.under, x)] += 1
        self._starts_at_or_below[bisect_left(self.under, x)] += 1
        if self._kept is not None:
            self._kept.append(x)

    def snapshot(self) -> Distribution:
        """Return the distribution of every observation so far."""
        empty = self._count == 0
        return Distribution(
            count=self._count,
            total=self._total,
            min=self._low,
            max=self._high,
            mean=None if empty else self._mean,
            stdev=None if empty else math.sqrt(self._squares / self._count),
            sample=None if self._kept is None else Sample(tuple(sorted(self._kept))),
            complete=isinstance(self.keep, All),
            thresholds=MappingProxyType(self._threshold_counts()),
        )

    def _threshold_counts(self) -> dict[float, tuple[int, int]]:
        counts: dict[float, tuple[int, int]] = {}
        below = at_or_below = 0
        # Not strict: the last slot, observations above every threshold, has no threshold to report.
        for x, starting_below, starting_at_or_below in zip(self.under, self._starts_below, self._starts_at_or_below, strict=False):
            below += starting_below
            at_or_below += starting_at_or_below
            counts[x] = (below, at_or_below)
        return counts


class StatsRecorder:
    """Metrics held by name, so one snapshot or reset reaches every one of them."""

    def __init__(self) -> None:
        """Start holding no metrics."""
        self._metrics: dict[str, Metric[Any]] = {}

    def add[M: Metric[Any]](self, name: str, metric: M) -> M:
        """Hold metric under name and return it; any kind of Metric will do.

        Adding the metric already held under name returns it again; adding a
        different one under a name already taken is refused.
        """
        existing = self._metrics.get(name)
        if existing is None:
            self._metrics[name] = metric
        elif existing is not metric:
            message = f"{name!r} is already a {type(existing).__name__.lower()}"
            raise StatsError(message)
        return metric

    def counter(self, name: str) -> Counter:
        """Return the Counter under name, adding one if there is none."""
        existing = self._metrics.get(name)
        if existing is None:
            return self.add(name, Counter())
        return self._held(name, existing, Counter)

    def measure(self, name: str, *, keep: All | Last | None = None, under: Sequence[float] = ()) -> Measure:
        """Return the Measure under name, adding one configured with keep and under if there is none.

        Asking again with the same keep and under returns the same measure;
        asking with different ones is refused.
        """
        existing = self._metrics.get(name)
        if existing is None:
            return self.add(name, Measure(keep=keep, under=under))
        measure = self._held(name, existing, Measure)
        if (measure.keep, measure.under) != (keep, tuple(sorted(set(under)))):
            message = f"{name!r} is already a measure with keep={measure.keep}, under={measure.under}"
            raise StatsError(message)
        return measure

    def snapshot(self) -> StatsSnapshot:
        """Return every metric's snapshot, unaffected by later recording."""
        return StatsSnapshot(metrics=MappingProxyType({name: metric.snapshot() for name, metric in self._metrics.items()}))

    def reset(self) -> None:
        """Reset every metric in place, so metrics already handed out keep recording into this recorder."""
        for metric in self._metrics.values():
            metric.reset()

    @staticmethod
    def _held[M: Metric[Any]](name: str, existing: Metric[Any], kind: type[M]) -> M:
        if not isinstance(existing, kind):
            message = f"{name!r} is already a {type(existing).__name__.lower()}"
            raise StatsError(message)
        return existing
