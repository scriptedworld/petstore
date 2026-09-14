"""Tests for scripted test doubles."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from petstore.stubs import Stub, StubExhaustedError


def example(path: str, *, retries: int = 0) -> None:
    """Provide a signature for stubs configured from a real callable."""
    del path, retries


def _drain(produced: object) -> list[object]:
    """Return the values of a scripted generator link."""
    assert isinstance(produced, Iterator)
    return list(produced)


@pytest.mark.requirement(
    "PS-STUB-001",
    functionality="stub.script",
    test_type="positive",
)
def test_links_are_consumed_in_declaration_order() -> None:
    """Verify successive calls take successive links."""
    stub = Stub().returns("first").returns("second")

    assert stub() == "first"
    assert stub() == "second"


@pytest.mark.requirement(
    "PS-STUB-002",
    functionality="stub.outcomes",
    test_type="positive",
)
def test_a_returns_link_produces_its_value() -> None:
    """Verify a scripted value is handed back unchanged."""
    sentinel = object()

    assert Stub().returns(sentinel)() is sentinel


@pytest.mark.requirement(
    "PS-STUB-002",
    functionality="stub.outcomes",
    test_type="negative",
)
def test_a_raises_link_accepts_a_type_or_an_instance() -> None:
    """Verify both spellings of a scripted exception are raised."""
    stub = Stub().raises(TimeoutError).raises(ValueError("boom"))

    with pytest.raises(TimeoutError):
        stub()

    with pytest.raises(ValueError, match=r"^boom$"):
        stub()


@pytest.mark.requirement(
    "PS-STUB-003",
    functionality="stub.generators",
    test_type="positive",
)
def test_consecutive_yield_links_build_one_iterator() -> None:
    """Verify yields and yields_from accumulate into a single call."""
    stub = Stub().yields(1).yields_from([2, 3]).yields(4)

    assert _drain(stub()) == [1, 2, 3, 4]


@pytest.mark.requirement(
    "PS-STUB-003",
    functionality="stub.generators",
    test_type="edge",
)
def test_a_returns_link_closes_an_open_generator() -> None:
    """Verify a later yield link starts a new call rather than extending the last."""
    stub = Stub().yields("a").returns(None).yields("b")

    assert _drain(stub()) == ["a"]
    assert stub() is None
    assert _drain(stub()) == ["b"]


@pytest.mark.requirement(
    "PS-STUB-004",
    functionality="stub.exhaustion",
    test_type="negative",
)
def test_calling_past_the_script_raises() -> None:
    """Verify an unscripted call fails rather than repeating the last link."""
    stub = Stub(name="fetch").returns(1)

    assert stub() == 1
    with pytest.raises(StubExhaustedError, match=r"fetch called 2 time"):
        stub()


@pytest.mark.requirement(
    "PS-STUB-004",
    functionality="stub.exhaustion",
    test_type="edge",
)
def test_an_unscripted_call_is_still_recorded() -> None:
    """Verify history survives the failure so it can be inspected afterwards."""
    stub = Stub()

    with pytest.raises(StubExhaustedError):
        stub("evidence")

    assert stub.call_count == 1
    assert stub.calls[0].args == ("evidence",)


@pytest.mark.requirement(
    "PS-STUB-005",
    functionality="stub.history",
    test_type="positive",
)
def test_arguments_are_recorded_for_each_call() -> None:
    """Verify positional and keyword arguments are captured."""
    stub = Stub().returns(None).returns(None)

    stub("one", flag=True)
    stub("two")

    assert stub.calls[0].args == ("one",)
    assert dict(stub.calls[0].kwargs) == {"flag": True}
    assert stub.calls[1].args == ("two",)


@pytest.mark.requirement(
    "PS-STUB-005",
    functionality="stub.history",
    test_type="invariant",
)
def test_the_call_count_matches_the_recorded_calls() -> None:
    """Verify the counter and the history never disagree."""
    stub = Stub().returns(None).returns(None)

    assert stub.call_count == len(stub.calls) == 0
    for expected_count in (1, 2):
        stub()
        assert stub.call_count == len(stub.calls) == expected_count


@pytest.mark.requirement(
    "PS-STUB-006",
    functionality="stub.signature",
    test_type="positive",
)
def test_a_declared_signature_binds_arguments_to_names() -> None:
    """Verify both signature sources bind arguments to parameter names."""
    named = Stub(parameters=["path"]).returns(None)
    copied = Stub(example).returns(None)

    named("alpha")
    copied("beta", retries=3)

    assert named.calls[0].bound_arguments == {"path": "alpha"}
    assert copied.calls[0].bound_arguments == {"path": "beta", "retries": 3}


@pytest.mark.requirement(
    "PS-STUB-006",
    functionality="stub.signature",
    test_type="negative",
)
def test_the_two_signature_sources_are_mutually_exclusive() -> None:
    """Verify declaring both sources is rejected at construction."""
    with pytest.raises(ValueError, match=r"mutually exclusive"):
        Stub(example, parameters=["path"])


@pytest.mark.requirement(
    "PS-STUB-006",
    functionality="stub.signature",
    test_type="edge",
)
def test_without_a_signature_no_arguments_are_bound() -> None:
    """Verify an undeclared signature records no binding and accepts anything."""
    stub = Stub().returns(None)

    stub("anything", at="all")

    assert stub.calls[0].bound_arguments is None


@pytest.mark.requirement(
    "PS-STUB-007",
    functionality="stub.always",
    test_type="positive",
)
def test_always_repeats_the_final_link_for_every_later_call() -> None:
    """Verify earlier links play once and the repeating link never runs out."""
    stub = Stub().returns("warming up").returns("ready").always()

    assert [stub() for _ in range(4)] == ["warming up", "ready", "ready", "ready"]


@pytest.mark.requirement(
    "PS-STUB-007",
    functionality="stub.always",
    test_type="edge",
)
def test_a_repeated_generator_or_raise_link_behaves_the_same_every_call() -> None:
    """Verify a repeated generator is fresh each call and a repeated raise keeps raising."""
    producing = Stub().yields(1).yields_from([2, 3]).always()
    failing = Stub().raises(TimeoutError).always()

    assert _drain(producing()) == [1, 2, 3]
    assert _drain(producing()) == [1, 2, 3]
    for _ in range(3):
        with pytest.raises(TimeoutError):
            failing()


@pytest.mark.requirement(
    "PS-STUB-007",
    functionality="stub.always",
    test_type="negative",
)
def test_always_rejects_an_empty_script_and_any_later_link() -> None:
    """Verify always needs something to repeat and nothing may follow it."""
    with pytest.raises(ValueError, match=r"needs a preceding link"):
        Stub().always()

    with pytest.raises(ValueError, match=r"no link may follow always"):
        Stub().returns(1).always().returns(2)

    with pytest.raises(ValueError, match=r"no link may follow always"):
        Stub().yields(1).always().yields(2)


class FakeClock:
    """A clock that moves only when a test moves it."""

    def __init__(self) -> None:
        """Start the clock at zero seconds."""
        self.now = 0.0

    def __call__(self) -> float:
        """Report the time the test last set."""
        return self.now


@pytest.mark.requirement(
    "PS-STUB-010",
    functionality="stub.times",
    test_type="positive",
)
def test_times_covers_a_counted_run_of_calls() -> None:
    """Verify a counted link plays its count before the next link applies."""
    stub = Stub().returns("not ready").times(3).returns("ready")

    assert [stub() for _ in range(4)] == ["not ready", "not ready", "not ready", "ready"]
    with pytest.raises(StubExhaustedError):
        stub()


@pytest.mark.requirement(
    "PS-STUB-010",
    functionality="stub.times",
    test_type="edge",
)
def test_a_counted_generator_link_builds_a_fresh_iterator_each_call() -> None:
    """Verify each counted call of a generator link produces the whole sequence."""
    stub = Stub().yields_from([1, 2]).times(2).returns("done")

    assert _drain(stub()) == [1, 2]
    assert _drain(stub()) == [1, 2]
    assert stub() == "done"


@pytest.mark.requirement(
    "PS-STUB-010",
    functionality="stub.times",
    test_type="negative",
)
def test_times_rejects_bad_counts_missing_links_and_second_modifiers() -> None:
    """Verify times needs a positive count, a link, and an unmodified link."""
    with pytest.raises(ValueError, match=r"at least one"):
        Stub().returns(1).times(0)

    with pytest.raises(ValueError, match=r"times\(\) needs a preceding link"):
        Stub().times(2)

    with pytest.raises(ValueError, match=r"at most one"):
        Stub().returns(1).times(2).always()


@pytest.mark.requirement(
    "PS-STUB-011",
    functionality="stub.over",
    test_type="positive",
)
def test_over_covers_every_call_inside_its_window() -> None:
    """Verify a timed link applies until its window closes, then the next link does."""
    clock = FakeClock()
    stub = Stub(clock=clock).returns("warming").over(seconds=30).returns("up")

    outcomes = []
    for moment in (0.0, 10.0, 29.9, 30.0):
        clock.now = moment
        outcomes.append(stub())

    assert outcomes == ["warming", "warming", "warming", "up"]


@pytest.mark.requirement(
    "PS-STUB-011",
    functionality="stub.over",
    test_type="edge",
)
def test_a_timed_window_opens_at_the_first_call_that_reaches_it() -> None:
    """Verify the window is measured from arrival, and a closed final window exhausts."""
    clock = FakeClock()
    stub = Stub(clock=clock).returns("first").returns("timed").over(minutes=1)

    assert stub() == "first"
    clock.now = 500.0
    assert stub() == "timed"
    clock.now = 559.0
    assert stub() == "timed"
    clock.now = 560.0
    with pytest.raises(StubExhaustedError):
        stub()


@pytest.mark.requirement(
    "PS-STUB-011",
    functionality="stub.over",
    test_type="negative",
)
def test_over_rejects_a_duration_that_is_not_positive() -> None:
    """Verify an empty or negative window is refused at declaration."""
    with pytest.raises(ValueError, match=r"positive duration"):
        Stub().returns(1).over()

    with pytest.raises(ValueError, match=r"positive duration"):
        Stub().returns(1).over(seconds=-5)


@pytest.mark.requirement(
    "PS-STUB-011",
    functionality="stub.over",
    test_type="positive",
)
def test_the_default_clock_is_the_real_monotonic_clock() -> None:
    """Verify a stub built without a clock still serves a timed link."""
    stub = Stub().returns("within the hour").over(hours=1)

    assert stub() == "within the hour"
