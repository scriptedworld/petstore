"""Tests for lazy iterable combination."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from petstore import ZipMode, zip_iter

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.mark.requirement(
    "PS-ITER-002",
    functionality="zip_iter.shortest",
    test_type="positive",
)
def test_shortest_matches_python_zip() -> None:
    """Verify that shortest mode matches ordinary Python zip behavior."""
    actual = list(zip_iter([1, 2, 3], ["a", "b"], mode="shortest"))
    assert actual == [(1, "a"), (2, "b")]


@pytest.mark.requirement(
    "PS-ITER-003",
    "PS-ITER-013",
    functionality="zip_iter.strict",
    test_type="positive",
)
def test_strict_accepts_equal_lengths() -> None:
    """Verify strict mode accepts inputs having equal lengths."""
    actual = list(zip_iter([1, 2], ["a", "b"], mode=ZipMode.STRICT))
    assert actual == [(1, "a"), (2, "b")]


@pytest.mark.requirement(
    "PS-ITER-004",
    functionality="zip_iter.strict",
    test_type="negative",
)
def test_strict_rejects_different_lengths() -> None:
    """Verify strict mode rejects differently sized inputs."""
    with pytest.raises(ValueError, match="shorter"):
        list(zip_iter([1, 2], ["a"], mode="strict"))


@pytest.mark.requirement(
    "PS-ITER-009",
    "PS-ITER-014",
    functionality="zip_iter.first",
    test_type="positive",
)
def test_first_uses_first_iterable_length_and_pads() -> None:
    """Verify first mode pads inputs shorter than the first input."""
    actual = list(zip_iter([1, 2, 3], ["a"], mode="first", fillvalues=("unused", "?")))
    assert actual == [(1, "a"), (2, "?"), (3, "?")]


@pytest.mark.requirement(
    "PS-ITER-009",
    "PS-ITER-014",
    functionality="zip_iter.first",
    test_type="invariant",
)
def test_first_ignores_excess_values() -> None:
    """Verify first mode leaves excess values unconsumed."""
    other = iter(["a", "b", "c"])
    actual = list(zip_iter([1], other, mode="first"))
    assert actual == [(1, "a")]
    assert next(other) == "b"


@pytest.mark.requirement(
    "PS-ITER-010",
    "PS-ITER-014",
    functionality="zip_iter.longest",
    test_type="positive",
)
def test_longest_uses_all_values_and_pads() -> None:
    """Verify longest mode exhausts every input and pads missing values."""
    actual = list(
        zip_iter(
            [1],
            ["a", "b"],
            [True, False, True],
            mode="longest",
            fillvalues=(0, "?", None),
        )
    )
    assert actual == [(1, "a", True), (0, "b", False), (0, "?", True)]


@pytest.mark.requirement(
    "PS-ITER-014",
    functionality="zip_iter.fillvalue_validation",
    test_type="negative",
)
def test_fillvalues_must_match_iterable_count() -> None:
    """Verify fill configuration requires one value per input."""
    with pytest.raises(ValueError, match="expected 2 fill values, received 1"):
        zip_iter([1], [2], mode="longest", fillvalues=(None,))


@pytest.mark.parametrize("mode", ZipMode)
@pytest.mark.requirement(
    "PS-ITER-007",
    "PS-ITER-013",
    functionality="zip_iter.empty",
    test_type="edge",
)
def test_empty_input_matches_builtin_zip(mode: ZipMode) -> None:
    """Verify every mode handles an invocation without inputs."""
    assert not list(zip_iter(mode=mode))


@pytest.mark.requirement(
    "PS-ITER-001",
    functionality="zip_iter.lifecycle",
    test_type="invariant",
)
def test_iterators_are_not_created_until_iteration_begins() -> None:
    """Verify input iterator creation is deferred until consumption."""
    events: list[str] = []

    class TrackedIterable:
        """Record when iteration starts."""

        def __iter__(self) -> Iterator[int]:
            """Record iterator creation before yielding a value."""
            events.append("iterated")
            yield 1

    result = zip_iter(TrackedIterable(), mode="shortest")
    assert not events
    assert next(result) == (1,)
    assert events == ["iterated"]


@pytest.mark.requirement(
    "PS-ITER-013",
    functionality="zip_iter.mode_validation",
    test_type="negative",
)
def test_unknown_mode_has_helpful_error() -> None:
    """Verify invalid mode diagnostics explain the accepted values."""
    with pytest.raises(ValueError, match="unsupported zip mode"):
        zip_iter([1], mode="mystery")


@pytest.mark.requirement(
    "PS-ITER-016",
    functionality="zip_iter.dynamic_fill",
    test_type="positive",
)
def test_callable_fill_is_invoked_once_for_each_missing_position() -> None:
    """Verify callable fills are created independently and only when missing."""
    created_values = iter(["first", "second"])
    factory_calls: list[str] = []

    def create_fill() -> str:
        """Record and return the next dynamic fill value."""
        factory_calls.append("called")
        return next(created_values)

    result = zip_iter([1, 2, 3], ["present"], mode="first", fillvalues=(None, create_fill))

    assert not factory_calls
    assert list(result) == [(1, "present"), (2, "first"), (3, "second")]
    assert factory_calls == ["called", "called"]
