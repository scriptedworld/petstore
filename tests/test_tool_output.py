"""Tests for canonical project-tool output."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
import yaml

from petstore.tool_output import ResultEnvelope, as_document, exit_code, reason, render_yaml, result

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.requirement(
    "PS-OUT-004",
    functionality="tool_output.success",
    test_type="positive",
)
def test_success_is_the_only_required_envelope_field() -> None:
    """Verify a successful result needs no optional fields."""
    envelope = result(success=True)

    assert envelope == ResultEnvelope(success=True, reasons=(), metadata=None)
    assert as_document(envelope) == {"success": True}


@pytest.mark.requirement(
    "PS-OUT-005",
    functionality="tool_output.reasons",
    test_type="positive",
)
def test_failure_contains_non_empty_reasons_with_extensible_details() -> None:
    """Verify failure reasons require messages and retain tool-specific fields."""
    envelope = result(success=False, reasons=(reason("failed", code="EXAMPLE", count=2),))

    assert as_document(envelope) == {
        "success": False,
        "reasons": [{"message": "failed", "code": "EXAMPLE", "count": 2}],
    }


@pytest.mark.requirement(
    "PS-OUT-005",
    functionality="tool_output.reasons",
    test_type="negative",
)
@pytest.mark.parametrize(
    "configuration",
    [
        {"success": True, "reasons": ({"message": "not allowed"},)},
        {"success": False, "reasons": ()},
        {"success": False, "reasons": ({},)},
        {"success": False, "reasons": ({"message": ""},)},
    ],
)
def test_conditional_reason_invariants_are_enforced(configuration: dict[str, object]) -> None:
    """Verify reasons are absent on success and meaningful on failure."""
    invalid_result = cast("Callable[..., ResultEnvelope]", result)

    with pytest.raises(ValueError, match="reason"):
        invalid_result(**configuration)

    with pytest.raises(ValueError, match="non-empty"):
        reason("")


@pytest.mark.requirement(
    "PS-OUT-006",
    functionality="tool_output.metadata",
    test_type="invariant",
)
def test_metadata_is_optional_independently_of_success() -> None:
    """Verify metadata can accompany either terminal outcome."""
    successful = result(success=True, metadata={"checked": 3})
    failed = result(success=False, reasons=(reason("failed"),), metadata={"checked": 3})

    assert as_document(successful)["metadata"] == {"checked": 3}
    assert as_document(failed)["metadata"] == {"checked": 3}


@pytest.mark.requirement(
    "PS-OUT-007",
    functionality="tool_output.yaml",
    test_type="invariant",
)
def test_yaml_rendering_is_deterministic_and_round_trippable() -> None:
    """Verify canonical rendering is stable and retains the envelope."""
    envelope = result(success=True, metadata={"tool": "example"})

    first = render_yaml(envelope)
    second = render_yaml(envelope)

    assert first == second
    assert first.startswith("---\n")
    assert yaml.safe_load(first) == as_document(envelope)


@pytest.mark.requirement(
    "PS-OUT-008",
    functionality="tool_output.exit_code",
    test_type="edge",
)
def test_success_controls_the_process_exit_code() -> None:
    """Verify process exit semantics use the envelope's Boolean result."""
    assert exit_code(result(success=True)) == 0
    assert exit_code(result(success=False, reasons=(reason("failed"),))) == 1
