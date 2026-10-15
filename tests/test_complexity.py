"""Tests for petstore.complexity."""

import inspect
import itertools
import math
import re
from collections.abc import Callable

import pytest

from petstore.complexity import Complexity, Growth, GrowthClass, Meter, Probe, assert_growth, memory_complexity, time_complexity

Work = Callable[[int, Probe], None]
Used = Callable[[int, Meter], None]

SIZES = (10, 100, 1_000)
MEMORY_SIZES = (100, 1_000, 10_000)


def lookup(n: int, probe: Probe) -> None:
    """Look up a key in a dict of n: constant work."""
    table = dict.fromkeys(range(n))
    with probe.counting():
        _ = probe.key(n // 2) in table


def halve(n: int, probe: Probe) -> None:
    """Halve n down to one in a Python loop: log n steps."""
    with probe.counting():
        while n > 1:
            n //= 2


def scan(n: int, probe: Probe) -> None:
    """Look for a missing key in a list of n inside C: n comparisons in one instruction."""
    values = list(range(n))
    with probe.counting():
        _ = probe.key(-1) in values


def walk(n: int, probe: Probe) -> None:
    """Sum a list of n in a Python loop touching no probe key: n steps."""
    values = list(range(n))
    with probe.counting():
        total = 0
        for value in values:
            total += value


def packed(n: int, probe: Probe) -> None:
    """Loop n times inside one line, a comprehension touching no probe key: n steps on one line."""
    with probe.counting():
        _ = [v * 2 for v in range(n)]


def sort(n: int, probe: Probe) -> None:
    """Sort n shuffled keys: at most n log n comparisons."""
    keys = [probe.key((i * 7919) % n) for i in range(n)]
    with probe.counting():
        sorted(keys)


def pairs(n: int, probe: Probe) -> None:
    """Count once for every pair, by hand: n^2 units."""
    with probe.counting():
        probe.tick(n * n)


def roots(n: int, probe: Probe) -> None:
    """Count once per step of a square-root search, by hand: sqrt n units."""
    with probe.counting():
        probe.tick(math.isqrt(n))


def triples(n: int, probe: Probe) -> None:
    """Count once for every triple, by hand: n^3 units."""
    with probe.counting():
        probe.tick(n**3)


def subsets(n: int, probe: Probe) -> None:
    """Count once for every subset, by hand: 2^n units."""
    with probe.counting():
        probe.tick(2**n)


def orderings(n: int, probe: Probe) -> None:
    """Walk every ordering of n items in a Python loop: n! steps."""
    with probe.counting():
        for _ in itertools.permutations(range(n)):
            pass


# COVERS FR-8.1 | positive
@pytest.mark.parametrize(
    ("work", "growth"),
    [
        (lookup, Complexity.CONSTANT),
        (halve, Complexity.LOGARITHMIC),
        (scan, Complexity.LINEAR),
        (walk, Complexity.LINEAR),
        (packed, Complexity.LINEAR),
        (sort, Complexity.LINEARITHMIC),
        (pairs, Complexity.QUADRATIC),
        (roots, Complexity.SQUARE_ROOT),
        (triples, Complexity.CUBIC),
    ],
    ids=["constant", "logarithmic", "linear-in-c", "linear-in-python", "linear-in-one-line", "linearithmic", "quadratic", "square-root", "cubic"],
)
def test_work_passes_its_own_class(work: Work, growth: Complexity) -> None:
    """Each kind of work is accepted by the class it belongs to."""
    time_complexity(growth, sizes=SIZES)(work)()


# COVERS FR-8.1 | positive
@pytest.mark.parametrize(
    ("work", "growth", "sizes"),
    [
        (subsets, Complexity.EXPONENTIAL, (2, 8, 20)),
        (orderings, Complexity.FACTORIAL, (4, 6, 8)),
    ],
    ids=["exponential", "factorial"],
)
def test_superpolynomial_work_passes_its_own_class(work: Work, growth: Complexity, sizes: tuple[int, ...]) -> None:
    """Exponential and factorial work is accepted over the small sizes it can be run at."""
    time_complexity(growth, sizes=sizes)(work)()


# COVERS FR-8.1 | negative
@pytest.mark.parametrize(
    ("work", "growth", "sizes"),
    [
        (triples, Complexity.QUADRATIC, SIZES),
        (pairs, Complexity.SQUARE_ROOT, SIZES),
        (subsets, Complexity.CUBIC, (2, 8, 20)),
        (orderings, Complexity.EXPONENTIAL, (4, 6, 8)),
    ],
    ids=["cubic-as-quadratic", "quadratic-as-square-root", "exponential-as-cubic", "factorial-as-exponential"],
)
def test_faster_growth_fails_up_to_factorial(work: Work, growth: Complexity, sizes: tuple[int, ...]) -> None:
    """Each class up to factorial refuses work from a faster class."""
    with pytest.raises(AssertionError, match=rf"^expected O\({re.escape(growth.label)}\)"):
        time_complexity(growth, sizes=sizes)(work)()


# COVERS FR-8.1 | edge
def test_growth_beyond_any_float_is_compared_and_reported() -> None:
    """Measurements and growth past float range compare in log space, and a failure writes the factor as a power of ten."""
    assert_growth(Complexity.FACTORIAL, (200, 400), (math.factorial(200), math.factorial(400)))
    with pytest.raises(AssertionError, match=r"grew about 10\^\d+x"):
        assert_growth(Complexity.CONSTANT, (200, 2_000), (1, 10**400))


# COVERS FR-8.1 | negative
@pytest.mark.parametrize(
    ("work", "growth"),
    [
        (scan, Complexity.CONSTANT),
        (walk, Complexity.CONSTANT),
        (packed, Complexity.CONSTANT),
        (scan, Complexity.LOGARITHMIC),
        (sort, Complexity.LINEAR),
        (pairs, Complexity.LINEARITHMIC),
    ],
    ids=[
        "c-loop-as-constant",
        "python-loop-as-constant",
        "one-line-loop-as-constant",
        "linear-as-logarithmic",
        "linearithmic-as-linear",
        "quadratic-as-linearithmic",
    ],
)
def test_work_fails_a_tighter_class(work: Work, growth: Complexity) -> None:
    """Work growing faster than the class allows fails, naming the class, the sizes and what was measured."""
    pattern = rf"^expected O\({growth.label}\), but at sizes \(10, 100, 1000\) measured \(.*\): .*\(operations counted\)$"
    with pytest.raises(AssertionError, match=pattern):
        time_complexity(growth, sizes=SIZES)(work)()


# COVERS FR-8.2 | edge
def test_line_granularity_is_blind_to_one_line_loops() -> None:
    """Counting lines sees a loop across lines but not one packed into a line, which is why instructions are the default."""
    time_complexity(Complexity.CONSTANT, sizes=SIZES, granularity="lines")(packed)()
    with pytest.raises(AssertionError, match=r"^expected O\(1\)"):
        time_complexity(Complexity.CONSTANT, sizes=SIZES, granularity="lines")(walk)()


# COVERS FR-8.1 | positive
def test_any_growth_class_can_be_used() -> None:
    """A class outside the enum, such as n^4, is held to like the rest."""

    def quadruples(n: int, probe: Probe) -> None:
        with probe.counting():
            probe.tick(n**4)

    fourth: GrowthClass = Growth("n^4", lambda n: n**4)
    time_complexity(fourth, sizes=SIZES)(quadruples)()
    with pytest.raises(AssertionError, match=r"^expected O\(n\^3\)"):
        time_complexity(Complexity.CUBIC, sizes=SIZES)(quadruples)()


# COVERS FR-8.1 | positive
def test_complexity_members_carry_label_and_function() -> None:
    """Each member is labelled as written in O(...) and grows as its class does."""
    labels = tuple(member.label for member in Complexity)
    at_5 = tuple(round(member.function(5)) for member in Complexity)
    expected_labels = ("1", "log n", "sqrt n", "n", "n log n", "n^2", "n^3", "2^n", "n!")
    assert (labels, at_5) == (expected_labels, (1, 3, 2, 5, 13, 25, 125, 32, 120))


# COVERS FR-8.1 | edge
def test_tolerance_decides_how_much_growth_passes() -> None:
    """A measure that triples passes O(1) at a tolerance of 3 and fails at the default of 2."""
    assert_growth(Complexity.CONSTANT, (10, 100), (5, 15), tolerance=3)
    with pytest.raises(AssertionError, match=r"grew 3\.0x, more than the 2\.0x allowed"):
        assert_growth(Complexity.CONSTANT, (10, 100), (5, 15))


# COVERS FR-8.1 | edge
def test_readings_below_the_floor_are_noise() -> None:
    """Zero and small readings are raised to the floor, so noise does not read as growth."""
    assert_growth(Complexity.CONSTANT, (10, 100), (0, 2))
    assert_growth(Complexity.CONSTANT, (10, 100), (100, 900), floor=1000)


# COVERS FR-8.2 | positive
def test_probe_keys_count_hashing_and_comparing() -> None:
    """A probe key equals its value, and the same hashing and comparing counts more on it than on a plain int."""
    below, value, above = 4, 5, 6

    def operate(probe: Probe, key: int) -> tuple[bool, ...]:
        with probe.counting():
            return (hash(key) == hash(value), key == value, key != above, key < above, key <= value, key > below, key >= value)

    probed, plain = Probe(), Probe()
    results = operate(probed, probed.key(value))
    operate(plain, value)
    assert (results, probed.count > plain.count) == ((True,) * 7, True)


# COVERS FR-8.2 | positive
def test_probe_counts_instructions_run_in_python() -> None:
    """A loop touching no probe key still counts, the same number of instructions more for every pass."""
    counts = []
    for n in (10, 20, 30):
        probe = Probe()
        walk(n, probe)
        counts.append(probe.count)
    assert counts[2] - counts[1] == counts[1] - counts[0] > 0


# COVERS FR-8.2 | negative
def test_probe_counts_nothing_outside_counting() -> None:
    """Setup outside counting() is free, by key, by instruction or by hand."""
    probe = Probe()
    key = probe.key(1)
    _ = key in {1, 2}
    probe.tick(5)
    with probe.counting():
        pass
    inside = probe.count
    probe.tick()
    assert (probe.count, probe.entered) == (inside, True)


# COVERS FR-8.3 | positive
def test_decorated_test_takes_no_arguments() -> None:
    """Pytest sees a test with no parameters, under the original name and docstring."""

    def example(n: int, probe: Probe) -> None:
        """Do nothing, as an example."""
        del n, probe

    decorated = time_complexity(Complexity.CONSTANT, sizes=SIZES)(example)
    signature_and_names = (dict(inspect.signature(decorated).parameters), decorated.__name__, decorated.__doc__)
    assert signature_and_names == ({}, "example", "Do nothing, as an example.")


# COVERS FR-8.3 | negative
def test_never_entering_the_block_fails() -> None:
    """A test that forgets counting() or measuring() fails instead of passing on nothing."""

    def uncounted(n: int, probe: Probe) -> None:
        del n, probe

    def unmeasured(n: int, meter: Meter) -> None:
        del n, meter

    with pytest.raises(AssertionError, match=r"^uncounted never entered probe\.counting\(\), so it measured nothing$"):
        time_complexity(Complexity.CONSTANT, sizes=SIZES)(uncounted)()
    with pytest.raises(AssertionError, match=r"^unmeasured never entered meter\.measuring\(\), so it measured nothing$"):
        memory_complexity(Complexity.CONSTANT, sizes=SIZES)(unmeasured)()


def keep(n: int, meter: Meter) -> None:
    """Allocate a list of n that outlives the block: linear retained memory."""
    with meter.measuring():
        kept = list(range(n))
    del kept


def churn(n: int, meter: Meter) -> None:
    """Allocate a list of n and drop it inside the block: nothing retained, linear peak."""
    with meter.measuring():
        _ = len(list(range(n)))


def prepared(n: int, meter: Meter) -> None:
    """Build a list of n before the block, then do constant work in it."""
    values = list(range(n))
    with meter.measuring():
        _ = values[0]


# COVERS FR-8.4 | positive
@pytest.mark.parametrize(
    ("used", "growth", "peak"),
    [
        (keep, Complexity.LINEAR, False),
        (churn, Complexity.CONSTANT, False),
        (churn, Complexity.LINEAR, True),
        (prepared, Complexity.CONSTANT, False),
        (prepared, Complexity.CONSTANT, True),
    ],
    ids=["kept-linear", "dropped-retains-nothing", "dropped-peaks-linear", "setup-is-free", "setup-is-free-at-peak"],
)
def test_memory_passes_its_own_class(used: Used, growth: Complexity, *, peak: bool) -> None:
    """Retained and peak memory inside the block are each accepted by their class; setup outside it is free."""
    memory_complexity(growth, sizes=MEMORY_SIZES, measure="peak" if peak else "retained")(used)()


# COVERS FR-8.4 | negative
@pytest.mark.parametrize(
    ("used", "peak"),
    [(keep, False), (keep, True), (churn, True)],
    ids=["kept", "kept-at-peak", "dropped-at-peak"],
)
def test_memory_fails_a_tighter_class(used: Used, *, peak: bool) -> None:
    """Linear memory, retained or at peak, fails O(1) and says which was read."""
    measure = "peak" if peak else "retained"
    with pytest.raises(AssertionError, match=rf"^expected O\(1\).*\(bytes {measure}\)$"):
        memory_complexity(Complexity.CONSTANT, sizes=MEMORY_SIZES, measure="peak" if peak else "retained")(used)()


# COVERS FR-8.5 | negative
@pytest.mark.parametrize(
    ("sizes", "problem"),
    [((10,), "at least 2 sizes"), ((100, 10), "ascending"), ((10, 10, 100), "ascending"), ((0, 100), "positive"), ((10, 50), "factor of 10")],
)
def test_sizes_that_cannot_tell_classes_apart_are_refused(sizes: tuple[int, ...], problem: str) -> None:
    """Too few sizes, unordered or repeated ones, a zero, or too narrow a span are refused when decorating."""
    with pytest.raises(ValueError, match=problem):
        time_complexity(Complexity.CONSTANT, sizes=sizes)
    with pytest.raises(ValueError, match=problem):
        memory_complexity(Complexity.CONSTANT, sizes=sizes)


# COVERS FR-8.5 | edge
def test_superpolynomial_classes_need_only_a_doubling() -> None:
    """Exponential and factorial accept sizes spanning a factor of 2 and refuse narrower ones, which polynomial classes refuse."""
    time_complexity(Complexity.FACTORIAL, sizes=(4, 8))
    with pytest.raises(ValueError, match="factor of 2,"):
        time_complexity(Complexity.EXPONENTIAL, sizes=(4, 6))
    with pytest.raises(ValueError, match="factor of 10,"):
        time_complexity(Complexity.CUBIC, sizes=(4, 8))
