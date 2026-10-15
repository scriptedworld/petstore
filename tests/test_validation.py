"""Tests for declarative attribute validation."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

from petstore.validation import Validated, ValidationError, validate


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


def reject_odd_length(value: str) -> None:
    """Fail with something other than ValidationError, as a broken rule might."""
    if len(value) % 2:
        message = "odd length"
        raise TypeError(message)


class Recorder:
    """A rule that accepts everything and remembers each value it was asked about."""

    def __init__(self) -> None:
        """Start with nothing seen."""
        self.seen: list[str] = []

    def __call__(self, value: str) -> None:
        """Record value and accept it."""
        self.seen.append(value)


# COVERS FR-2.2, FR-2.6 | negative
def test_rules_after_the_first_failure_are_not_run() -> None:
    """Verify a rule after the failing one is never called, by the function or the descriptor."""
    after = Recorder()
    with pytest.raises(ValidationError, match=r"^greeting must not be blank$"):
        validate("  ", reject_blank, after, label="greeting")

    owner_rules: Validated[str] = Validated(reject_blank, after)

    @dataclass
    class Owner:
        text: Validated[str] = owner_rules

    with pytest.raises(ValidationError, match=r"^text must not be blank$"):
        Owner("  ")

    assert after.seen == []


# COVERS FR-2.6 | positive
def test_validate_returns_an_accepted_value_unchanged() -> None:
    """Verify an accepted value comes back as the same object."""
    value = "hello"

    assert validate(value, reject_blank, reject_short, label="greeting") is value


# COVERS FR-2.6 | edge
def test_validate_with_no_rules_returns_the_value() -> None:
    """Verify no rules means no check, as with a descriptor declaring none."""
    assert validate("", label="anything") == ""


# COVERS FR-2.6 | negative
def test_validate_reports_only_the_first_failing_rule() -> None:
    """Verify rules run in order and a later rule does not mask the first failure."""
    with pytest.raises(ValidationError, match=r"^greeting must not be blank$"):
        validate("  ", reject_blank, reject_short, label="greeting")
    with pytest.raises(ValidationError, match=r"^greeting must be at least three characters$"):
        validate("ab", reject_blank, reject_short, label="greeting")


# COVERS FR-2.6, FR-2.3 | property
def test_validate_fails_exactly_as_the_descriptor_does() -> None:
    """Verify the message, type and chaining match the descriptor's failure."""
    with pytest.raises(ValidationError) as from_descriptor:
        Note("")
    with pytest.raises(ValidationError) as from_function:
        validate("", reject_blank, label="note body")

    assert type(from_function.value) is type(from_descriptor.value) is ValidationError
    assert str(from_function.value) == str(from_descriptor.value) == "note body must not be blank"
    assert from_function.value.__cause__ is from_descriptor.value.__cause__ is None
    assert from_function.value.__suppress_context__ is from_descriptor.value.__suppress_context__ is True


# COVERS FR-2.6 | negative
def test_validate_lets_other_exceptions_through_unchanged() -> None:
    """Verify an exception other than ValidationError is neither wrapped nor relabelled."""
    with pytest.raises(TypeError, match=r"^odd length$") as failure:
        validate("abc", reject_blank, reject_odd_length, label="code")

    assert not isinstance(failure.value, ValidationError)


# COVERS FR-2.6 | edge
def test_validate_requires_a_keyword_label() -> None:
    """Verify the label can be passed only by keyword, and has no default."""
    label = inspect.signature(validate).parameters["label"]

    assert label.kind is inspect.Parameter.KEYWORD_ONLY
    assert label.default is inspect.Parameter.empty
