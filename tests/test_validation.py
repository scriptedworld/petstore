"""Tests for declarative attribute validation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from petstore.validation import Validated, ValidationError


def reject_blank(value: str) -> None:
    """Reject a value that is empty or only whitespace."""
    if not value.strip():
        message = "must not be blank"
        raise ValidationError(message)


def reject_short(value: str) -> None:
    """Reject a value shorter than three characters."""
    minimum_length = 3
    if len(value) < minimum_length:
        message = "must be at least three characters"
        raise ValidationError(message)


# Bound to names rather than called in the class body: a call there is a
# dataclass-default construction, which the lint configuration rejects.
ORDERED_RULES: Validated[str] = Validated(reject_blank, reject_short)
LABELLED_RULE: Validated[str] = Validated(reject_blank, label="note body")
NO_RULES: Validated[str] = Validated()


@dataclass(frozen=True)
class Label:
    """A frozen owner whose text is validated by two ordered rules."""

    text: Validated[str] = ORDERED_RULES


@dataclass
class Note:
    """A mutable owner whose body carries an explicit failure label."""

    body: Validated[str] = LABELLED_RULE


@dataclass
class Anything:
    """An owner whose attribute declares no rules at all."""

    payload: Validated[str] = NO_RULES


# COVERS FR-2.1 | positive
def test_constructor_validates_and_stores_an_acceptable_value() -> None:
    """Verify a dataclass constructor runs the rules and keeps the value."""
    label = Label("hello")

    assert label.text == "hello"


# COVERS FR-2.1 | property
def test_later_assignment_is_validated_like_construction() -> None:
    """Verify assignment after construction applies the same rules."""
    note = Note("first body")

    note.body = "second body"

    assert note.body == "second body"
    with pytest.raises(ValidationError):
        note.body = "   "


# COVERS FR-2.2 | positive
def test_an_attribute_without_rules_accepts_any_value() -> None:
    """Verify declaring no rules leaves the value unchecked."""
    anything = Anything("")

    assert anything.payload == ""


# COVERS FR-2.2 | negative
def test_the_first_failing_rule_determines_the_reported_failure() -> None:
    """Verify rules run in order and later rules do not mask the first failure."""
    with pytest.raises(ValidationError) as blank_failure:
        Label("  ")

    with pytest.raises(ValidationError) as short_failure:
        Label("ab")

    assert "must not be blank" in str(blank_failure.value)
    assert "must be at least three characters" in str(short_failure.value)


# COVERS FR-2.3 | negative
def test_a_failure_is_prefixed_with_the_attribute_name_by_default() -> None:
    """Verify the attribute name labels the rule's own message."""
    with pytest.raises(ValidationError, match=r"^text must not be blank$"):
        Label("")


# COVERS FR-2.3 | edge
def test_an_explicit_label_replaces_the_attribute_name() -> None:
    """Verify a declared label is used in place of the attribute name."""
    with pytest.raises(ValidationError, match=r"^note body must not be blank$"):
        Note("")


# COVERS FR-2.4 | property
def test_values_are_stored_on_frozen_instances() -> None:
    """Verify a frozen owner, which rejects ordinary assignment, still stores values."""
    first = Label("first value")
    second = Label("second value")

    assert first.text == "first value"
    assert second.text == "second value"


# COVERS FR-2.5 | edge
def test_class_access_returns_the_descriptor() -> None:
    """Verify reading the attribute from the class exposes the descriptor."""
    descriptor = Label.text

    assert isinstance(descriptor, Validated)
