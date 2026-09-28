"""Tests for generate, the one-behavior form of Stub."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from petstore import Stub, generate

if TYPE_CHECKING:
    from collections.abc import Callable


def _invoke_without_arguments(operation: Callable[[], object]) -> object:
    """Invoke a callable without exposing its concrete signature to linting."""
    return operation()


@pytest.mark.requirement(
    "PS-TEST-013",
    "PS-TEST-012",
    functionality=("generate.return_behavior", "generate.call_history"),
    test_type="positive",
)
def test_generate_returns_value_and_records_unbounded_calls() -> None:
    """Verify return behavior and ordered metadata for arbitrary arguments."""
    expected_call_count = 2
    generated = generate(returns="result")

    assert generated.call_count == 0
    assert not generated.calls

    first_result = generated(1, name="first")
    second_result = generated(2, name="second")

    assert isinstance(generated, Stub)
    assert first_result == "result"
    assert second_result == "result"
    assert generated.call_count == expected_call_count
    assert generated.calls[0].args == (1,)
    assert dict(generated.calls[0].kwargs) == {"name": "first"}
    assert generated.calls[1].args == (2,)


@pytest.mark.requirement(
    "PS-TEST-007",
    "PS-TEST-012",
    functionality=("generate.raise_behavior", "generate.call_history"),
    test_type="negative",
)
@pytest.mark.parametrize("exception", [RuntimeError, ValueError("failure")])
def test_generate_raises_after_recording(exception: BaseException | type[BaseException]) -> None:
    """Verify class and instance exceptions are raised after call capture."""
    generated = generate(raises=exception)

    with pytest.raises(exception if isinstance(exception, type) else type(exception)):
        generated("argument", keyword=3)

    assert generated.call_count == 1
    assert generated.calls[0].args == ("argument",)
    assert dict(generated.calls[0].kwargs) == {"keyword": 3}


@pytest.mark.requirement(
    "PS-TEST-008",
    "PS-TEST-012",
    functionality=("generate.yield_behavior", "generate.call_history"),
    test_type="positive",
)
def test_generate_yields_fresh_sequence_for_each_call() -> None:
    """Verify yield behavior returns an independent iterator per invocation."""
    expected_call_count = 2
    generated = generate(yields=[1, 2, 3])

    assert list(generated("first")) == [1, 2, 3]
    assert list(generated("second")) == [1, 2, 3]
    assert generated.call_count == expected_call_count


@pytest.mark.requirement(
    "PS-TEST-010",
    functionality="generate.explicit_signature",
    test_type="positive",
)
def test_generate_builds_signature_from_parameter_names() -> None:
    """Verify explicit parameter names constrain and describe calls."""
    generated = generate(returns="combined", parameters=["left", "right"])

    result = generated(1, right=2)

    assert result == "combined"
    assert dict(generated.calls[0].bound_arguments or {}) == {"left": 1, "right": 2}
    with pytest.raises(TypeError, match="missing a required argument"):
        generated(1)
    assert generated.call_count == 1


@pytest.mark.requirement(
    "PS-TEST-010",
    functionality="generate.callable_signature",
    test_type="positive",
)
def test_generate_derives_signature_from_callable() -> None:
    """Verify callable-derived functions enforce the inspected signature."""

    def operation(identifier: int, *, enabled: bool = False) -> str:
        """Provide a signature without executing this implementation."""
        return f"{identifier}:{enabled}"

    generated = generate(returns="generated", signature_from=operation)
    result = generated(7, enabled=True)

    assert result == "generated"
    assert dict(generated.calls[0].bound_arguments or {}) == {"identifier": 7, "enabled": True}
    with pytest.raises(TypeError, match="missing a required argument"):
        _invoke_without_arguments(generated)
    assert generated.call_count == 1


@pytest.mark.requirement(
    "PS-TEST-011",
    functionality="generate.configuration_validation",
    test_type="negative",
)
@pytest.mark.parametrize(
    "configuration",
    [
        {},
        {"returns": None, "raises": RuntimeError},
        {"returns": None, "yields": []},
        {"raises": RuntimeError, "yields": []},
    ],
)
def test_generate_requires_exactly_one_behavior(configuration: dict[str, object]) -> None:
    """Verify ambiguous or missing behavior configuration is rejected."""
    invalid_generate = cast("Callable[..., object]", generate)

    with pytest.raises(ValueError, match="exactly one"):
        invalid_generate(**configuration)


@pytest.mark.requirement(
    "PS-TEST-011",
    functionality="generate.signature_validation",
    test_type="negative",
)
def test_generate_rejects_two_signature_sources() -> None:
    """Verify explicit and inspected signatures cannot be combined."""

    def operation(value: object) -> object:
        """Provide a signature for validation."""
        return value

    with pytest.raises(ValueError, match="mutually exclusive"):
        generate(returns=None, parameters=["value"], signature_from=operation)
