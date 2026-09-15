"""Declarative attribute validation through a reusable data descriptor.

A rule is an ordinary function: value in, raise on problem, return nothing.

    def positive(value: int) -> None:
        if value <= 0:
            message = "must be positive"
            raise ValidationError(message)

``Validated`` holds every mechanical concern (storage, the write that works on
frozen instances, the attribute name, and decorating a failure with the field's
label), so a rule never has to know any of it. An attribute then becomes a
declaration rather than a method:

    RULES = Validated(positive)

    @dataclass(frozen=True)
    class Reading:
        count: Validated[int] = RULES

Validation runs inside ``__init__`` as well as on later assignment, because a
dataclass constructor assigns through the ordinary attribute machinery and that
machinery honours a data descriptor. A constructed object is therefore a valid
one, and nothing downstream needs to re-check it.

One instance belongs to one attribute of one class. Python calls
``__set_name__`` for each class body the instance appears in, so sharing a
single instance between two classes leaves it labelled for whichever class was
defined last.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar, cast, overload

__all__ = ["Rule", "Validated", "ValidationError"]

T = TypeVar("T")

Rule = Callable[[T], None]
"""A check over one value: return for acceptable input, raise otherwise."""


class ValidationError(ValueError):
    """Raised when a value fails a rule attached to a validated attribute."""


class Validated(Generic[T]):
    """Run rules against a value, then store it on the owning instance.

    A descriptor lives on the class and is shared by every instance, so nothing
    per-instance is kept here: only the rules and the label, both fixed when
    the owning class body is executed. The value itself is stored on the
    instance under a private name derived from the attribute name.
    """

    def __init__(self, *rules: Rule[T], label: str | None = None) -> None:
        """Accept the rules to apply, and optionally the name used in errors.

        Args:
            rules: Applied in order; the first failure is reported.
            label: Names the attribute in error messages. Defaults to the
                attribute name the descriptor is assigned to.

        """
        self._rules = rules
        self._label = "" if label is None else label
        self._private_name = ""

    def __set_name__(self, owner: type[object], name: str) -> None:
        """Record the attribute name, and adopt it as the label if none was given."""
        del owner
        self._private_name = f"_{name}"
        if not self._label:
            self._label = name

    @overload
    def __get__(self, obj: None, owner: type[object] | None = ...) -> Validated[T]: ...

    @overload
    def __get__(self, obj: object, owner: type[object] | None = ...) -> T: ...

    def __get__(self, obj: object | None, owner: type[object] | None = None) -> Validated[T] | T:
        """Return the descriptor itself for class access, or the stored value."""
        del owner
        if obj is None:
            return self
        return cast("T", getattr(obj, self._private_name))

    def __set__(self, obj: object, value: T) -> None:
        """Apply every rule to *value*, then store it on *obj*.

        Raises:
            ValidationError: If any rule rejects the value. The rule's own
                message is prefixed with this attribute's label.

        """
        try:
            for rule in self._rules:
                rule(value)
        except ValidationError as problem:
            message = f"{self._label} {problem}"
            raise ValidationError(message) from None
        # object.__setattr__ rather than setattr: a frozen dataclass rejects the
        # ordinary path, and the plain machinery still honours a data descriptor.
        object.__setattr__(obj, self._private_name, value)
