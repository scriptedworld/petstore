"""Canonical YAML result envelopes for project tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


class ResultEnvelope(NamedTuple):
    """Validated tool result ready for canonical serialization."""

    success: bool
    reasons: tuple[dict[str, object], ...]
    metadata: dict[str, object] | None


def reason(message: str, **details: object) -> dict[str, object]:
    """Create one failure reason with a required message and optional details."""
    if not message:
        error_message = "reason message must be a non-empty string"
        raise ValueError(error_message)
    return {"message": message, **details}


def result(
    *,
    success: bool,
    reasons: Iterable[Mapping[str, object]] = (),
    metadata: Mapping[str, object] | None = None,
) -> ResultEnvelope:
    """Create an envelope while enforcing conditional reason semantics."""
    normalized_reasons = tuple(dict(item) for item in reasons)
    _validate_reasons(success=success, reasons=normalized_reasons)
    normalized_metadata = dict(metadata) if metadata is not None else None
    return ResultEnvelope(success, normalized_reasons, normalized_metadata)


def as_document(envelope: ResultEnvelope) -> dict[str, object]:
    """Convert an envelope into its canonical three-field document shape."""
    document: dict[str, object] = {"success": envelope.success}
    if not envelope.success:
        document["reasons"] = list(envelope.reasons)
    if envelope.metadata is not None:
        document["metadata"] = envelope.metadata
    return document


def render_yaml(envelope: ResultEnvelope) -> str:
    """Render an envelope as deterministic block-style YAML."""
    return yaml.safe_dump(
        as_document(envelope),
        allow_unicode=True,
        default_flow_style=False,
        explicit_start=True,
        sort_keys=False,
        width=150,
    )


def exit_code(envelope: ResultEnvelope) -> int:
    """Return zero for success and one for failure."""
    return 0 if envelope.success else 1


def _validate_reasons(*, success: bool, reasons: tuple[dict[str, object], ...]) -> None:
    """Enforce absence on success and a non-empty reason list on failure."""
    if success and reasons:
        message = "successful results must not contain reasons"
        raise ValueError(message)
    if not success and not reasons:
        message = "failed results must contain at least one reason"
        raise ValueError(message)
    for item in reasons:
        if not isinstance(item.get("message"), str) or not item["message"]:
            message = "every reason must contain a non-empty string message"
            raise ValueError(message)
