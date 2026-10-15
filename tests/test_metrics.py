"""Tests for petstore.metrics."""

import statistics
from typing import Any

import pytest

from petstore.metrics import All, Counter, Distribution, Last, Measure, Metric, StatsError, StatsRecorder

# Spread out, repeated and unordered: 200 values from 0 to 100.
SPREAD = [float((i * 37) % 101) for i in range(200)]


def observed(values: list[float], *, keep: All | Last | None = None, under: tuple[float, ...] = ()) -> Distribution:
    """Return the distribution of a fresh measure after recording values."""
    recorder = StatsRecorder()
    record = recorder.measure("m", keep=keep, under=under)
    for value in values:
        record(value)
    return recorder.snapshot().measures["m"]


# COVERS FR-7.1 | positive
def test_counter_adds_one_or_n() -> None:
    """Each call adds one, or n when given."""
    recorder = StatsRecorder()
    hits = recorder.counter("hits")
    hits()
    hits(3)
    assert recorder.snapshot().counts == {"hits": 4}


# COVERS FR-7.1 | positive
def test_counter_asked_for_again_shares_its_count() -> None:
    """Asking twice for one name returns the same counter."""
    recorder = StatsRecorder()
    first, second = recorder.counter("calls"), recorder.counter("calls")
    first()
    second()
    assert (first is second, recorder.snapshot().counts) == (True, {"calls": 2})


# COVERS FR-7.1 | negative
def test_counter_refuses_to_go_down() -> None:
    """A negative step is refused and leaves the count alone."""
    recorder = StatsRecorder()
    count = recorder.counter("c")
    with pytest.raises(StatsError, match="only goes up"):
        count(-1)
    assert recorder.snapshot().counts == {"c": 0}


# COVERS FR-7.2 | positive
def test_running_summary_is_exact() -> None:
    """Count, total, min, max, mean and population stdev, here with a mean of 5 and stdev of 2."""
    d = observed([2, 4, 4, 4, 5, 5, 7, 9])
    assert (d.count, d.total, d.min, d.max, d.mean, d.stdev) == (8, 40, 2, 9, 5, 2)


# COVERS FR-7.2 | property
def test_running_summary_matches_statistics_module() -> None:
    """On many values, mean and stdev agree with the standard library."""
    d = observed(SPREAD)
    assert (d.mean, d.stdev) == pytest.approx((statistics.fmean(SPREAD), statistics.pstdev(SPREAD)))


# COVERS FR-7.2 | edge
def test_empty_measure_has_no_summary() -> None:
    """Before any observation, there is nothing to take a min, max, mean or stdev of."""
    d = observed([])
    assert (d.count, d.total, d.min, d.max, d.mean, d.stdev) == (0, 0, None, None, None, None)


# COVERS FR-7.3 | positive
def test_quantiles_interpolate_between_ranks() -> None:
    """On 1 to 10: p0 is the min, p100 the max, p50 halfway between 5 and 6, p85 between 8 and 9."""
    d = observed([float(v) for v in range(10, 0, -1)], keep=All())
    assert d.quantiles(0, 1, 0.5) == (1, 10, 5.5)
    assert d.quantile(0.85) == pytest.approx(8.65)


# COVERS FR-7.3 | property
def test_quantiles_match_statistics_inclusive() -> None:
    """Every whole percentile agrees with statistics.quantiles(method="inclusive")."""
    d = observed(SPREAD, keep=All())
    expected = statistics.quantiles(SPREAD, n=100, method="inclusive")
    assert d.quantiles(*(k / 100 for k in range(1, 100))) == pytest.approx(expected)


# COVERS FR-7.3 | positive
def test_under_counts_strictly_or_inclusively() -> None:
    """u2 on 1, 2, 2, 3, 5 is one in five strictly below and three at or below."""
    d = observed([5, 2, 1, 3, 2], keep=All())
    assert (d.under(2), d.under(2, inclusive=True), d.under(0), d.under(9)) == (0.2, 0.6, 0, 1)


# COVERS FR-7.3 | positive
def test_kept_values_are_sorted() -> None:
    """The sample holds every observation in ascending order."""
    d = observed([3, 1, 2], keep=All())
    assert (d.sample.values if d.sample else None, d.complete) == ((1, 2, 3), True)


# COVERS FR-7.4 | positive
def test_window_keeps_the_most_recent() -> None:
    """With Last(3) after 1 to 5, the sample is 3, 4, 5 while the summary still covers all five."""
    d = observed([1, 2, 3, 4, 5], keep=Last(3))
    assert d.sample is not None
    assert (d.sample.values, d.sample.quantile(0), d.sample.under(5), d.count, d.mean) == ((3, 4, 5), 3, 2 / 3, 5, 3)


# COVERS FR-7.4 | negative
def test_window_refuses_all_time_quantiles() -> None:
    """A window cannot answer for every observation, so the distribution sends the caller to sample."""
    d = observed([1, 2, 3], keep=Last(5))
    with pytest.raises(StatsError, match=r"keeps a window, so ask \.sample"):
        d.quantile(0.5)
    with pytest.raises(StatsError, match="declared: none"):
        d.under(2)


# COVERS FR-7.4 | negative
@pytest.mark.parametrize("size", [0, -1])
def test_window_must_hold_something(size: int) -> None:
    """A window of fewer than one observation is refused."""
    with pytest.raises(StatsError, match="at least 1"):
        Last(size)


# COVERS FR-7.5 | positive
def test_declared_thresholds_answer_without_kept_values() -> None:
    """u2 and u4 on 1, 2, 2, 3, 5 come from counts alone, with nothing kept."""
    d = observed([5, 2, 1, 3, 2], under=(4, 2))
    assert d.sample is None
    assert (d.under(2), d.under(2, inclusive=True), d.under(4)) == (0.2, 0.6, 0.8)


# COVERS FR-7.5 | property
def test_declared_thresholds_agree_with_kept_values() -> None:
    """For every declared threshold, counting and sorting give the same share."""
    thresholds = (0.0, 10.0, 36.0, 50.0, 99.5, 100.0)
    counted = observed(SPREAD, under=thresholds)
    kept = observed(SPREAD, keep=All())
    for x in thresholds:
        for inclusive in (False, True):
            assert counted.under(x, inclusive=inclusive) == kept.under(x, inclusive=inclusive)


# COVERS FR-7.5 | negative
def test_undeclared_threshold_names_the_declared_ones() -> None:
    """Asking for an x nobody declared, with nothing kept, says which were."""
    d = observed([1, 2], under=(5, 1))
    with pytest.raises(StatsError, match=r"declared: 1, 5$"):
        d.under(3)
    with pytest.raises(StatsError, match=r"keep=All\(\)$"):
        d.quantile(0.5)


# COVERS FR-7.6 | negative
@pytest.mark.parametrize("q", [-0.01, 1.01])
def test_quantile_outside_zero_to_one_is_refused(q: float) -> None:
    """A quantile is a share, so it must be from 0 to 1."""
    with pytest.raises(StatsError, match="from 0 to 1"):
        observed([1], keep=All()).quantile(q)


# COVERS FR-7.6 | negative
def test_no_observations_answers_nothing() -> None:
    """With nothing observed there is no quantile and no share, declared or kept."""
    for d in (observed([], keep=All()), observed([], under=(1,))):
        with pytest.raises(StatsError, match="no observations"):
            d.under(1)
    with pytest.raises(StatsError, match="no observations"):
        observed([], keep=All()).quantile(0.5)


# COVERS FR-7.7 | negative
def test_snapshot_is_immutable_and_detached() -> None:
    """A snapshot refuses changes and does not move when recording continues."""
    recorder = StatsRecorder()
    count = recorder.counter("c")
    record = recorder.measure("m", keep=All())
    before = recorder.snapshot()
    count()
    record(1)
    counts: Any = before.counts
    with pytest.raises(TypeError):
        counts["c"] = 5
    assert (before.counts["c"], before.measures["m"].count) == (0, 0)


# COVERS FR-7.8 | positive
def test_reset_clears_in_place_and_metrics_keep_working() -> None:
    """After a reset everything reads empty, and metrics handed out before record into the fresh state."""
    recorder = StatsRecorder()
    count = recorder.counter("c")
    record = recorder.measure("m", keep=Last(2), under=(5,))
    count()
    record(1)
    recorder.reset()
    cleared = recorder.snapshot().measures["m"]
    assert (recorder.snapshot().counts["c"], cleared.count, cleared.min, cleared.thresholds[5]) == (0, 0, None, (0, 0))
    count()
    record(9)
    after = recorder.snapshot().measures["m"]
    assert (recorder.snapshot().counts["c"], after.sample.values if after.sample else None, after.under(5)) == (1, (9,), 0)


# COVERS FR-7.9 | negative
def test_a_name_is_one_kind_of_instrument() -> None:
    """A counter's name cannot become a measure, nor a measure's a counter."""
    recorder = StatsRecorder()
    recorder.counter("c")
    recorder.measure("m")
    with pytest.raises(StatsError, match="already a counter"):
        recorder.measure("c")
    with pytest.raises(StatsError, match="already a measure"):
        recorder.counter("m")


# COVERS FR-7.9 | negative
@pytest.mark.parametrize(("keep", "under"), [(All(), ()), (None, (1.0,)), (Last(3), (2.0,))])
def test_a_measure_keeps_its_first_configuration(keep: All | Last | None, under: tuple[float, ...]) -> None:
    """Asking for a measure again with different keep or under is refused."""
    recorder = StatsRecorder()
    recorder.measure("m", keep=Last(2), under=(2.0,))
    with pytest.raises(StatsError, match="already a measure with"):
        recorder.measure("m", keep=keep, under=under)


# COVERS FR-7.9 | positive
def test_same_measure_configuration_is_shared() -> None:
    """Asking again with equal keep and under, in any threshold order, records into the same measure."""
    recorder = StatsRecorder()
    first = recorder.measure("m", keep=Last(2), under=(2.0, 1.0))
    second = recorder.measure("m", keep=Last(2), under=(1.0, 2.0, 2.0))
    first(1)
    second(3)
    assert (recorder.snapshot().measures["m"].count,) == (2,)


# COVERS FR-7.10 | positive
def test_counter_works_without_a_recorder() -> None:
    """A Counter on its own counts, reports and resets."""
    count = Counter()
    count()
    count(4)
    before_reset = count.snapshot()
    count.reset()
    assert (isinstance(count, Metric), before_reset, count.snapshot()) == (True, 5, 0)


# COVERS FR-7.10 | positive
def test_measure_works_without_a_recorder() -> None:
    """A Measure on its own records, reports and resets, configured as a recorder would configure it."""
    measure = Measure(keep=All(), under=(2,))
    for x in (1, 2, 3):
        measure(x)
    d = measure.snapshot()
    measure.reset()
    assert (isinstance(measure, Metric), d.quantile(0.5), d.under(2), measure.snapshot().count) == (True, 2, 1 / 3, 0)


class Gauge(Metric[float]):
    """A metric no recorder knows: the last value set."""

    def __init__(self) -> None:
        """Start at zero."""
        self.value = 0.0

    def __call__(self, value: float) -> None:
        """Set the value."""
        self.value = value

    def snapshot(self) -> float:
        """Return the value."""
        return self.value

    def reset(self) -> None:
        """Return to zero."""
        self.value = 0.0


# COVERS FR-7.11 | positive
def test_any_metric_can_be_added_snapshotted_and_reset() -> None:
    """A kind of Metric the recorder has never heard of is held, snapshotted and reset like its own."""
    recorder = StatsRecorder()
    gauge = recorder.add("depth", Gauge())
    gauge(2.5)
    before = recorder.snapshot()
    recorder.reset()
    assert (before.metrics["depth"], recorder.snapshot().metrics["depth"]) == (2.5, 0)


# COVERS FR-7.11 | positive
def test_adding_the_held_metric_again_returns_it() -> None:
    """Adding the same object under its own name is harmless, and counter() finds an added Counter."""
    recorder = StatsRecorder()
    count = Counter()
    assert (recorder.add("c", count), recorder.add("c", count), recorder.counter("c")) == (count, count, count)


# COVERS FR-7.11 | negative
def test_adding_under_a_taken_name_is_refused() -> None:
    """A different metric cannot take a name already held, nor can counter() or measure() claim it."""
    recorder = StatsRecorder()
    recorder.add("depth", Gauge())
    with pytest.raises(StatsError, match="'depth' is already a gauge"):
        recorder.add("depth", Gauge())
    with pytest.raises(StatsError, match="'depth' is already a gauge"):
        recorder.counter("depth")
    with pytest.raises(StatsError, match="'depth' is already a gauge"):
        recorder.measure("depth")


# COVERS FR-7.12 | positive
def test_snapshot_reads_each_kind_back_typed() -> None:
    """Count and distribution return their kind, and counts and measures gather each kind."""
    recorder = StatsRecorder()
    recorder.counter("c")(2)
    recorder.measure("m")(4)
    recorder.add("g", Gauge())
    snapshot = recorder.snapshot()
    assert (snapshot.count("c"), snapshot.distribution("m").total) == (2, 4)
    assert (dict(snapshot.counts), list(snapshot.measures), sorted(snapshot.metrics)) == ({"c": 2}, ["m"], ["c", "g", "m"])


# COVERS FR-7.12 | negative
def test_snapshot_refuses_the_wrong_kind() -> None:
    """Reading a measure as a count, or a counter as a distribution, says what it is not."""
    recorder = StatsRecorder()
    recorder.counter("c")
    recorder.measure("m")
    snapshot = recorder.snapshot()
    with pytest.raises(StatsError, match="'m' is not a counter"):
        snapshot.count("m")
    with pytest.raises(StatsError, match="'c' is not a measure"):
        snapshot.distribution("c")


# COVERS FR-7.13 | negative
@pytest.mark.parametrize("attribute", ["keep", "under"])
def test_measure_configuration_is_read_only(attribute: str) -> None:
    """Keep and under are fixed when a measure is made, so its state always matches them."""
    measure = Measure(keep=Last(2), under=(2, 1))
    with pytest.raises(AttributeError):
        setattr(measure, attribute, None)
    assert (measure.keep, measure.under) == (Last(2), (1, 2))
