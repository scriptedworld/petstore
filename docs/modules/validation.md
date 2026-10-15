# Attribute validation

Module: `petstore.validation`

Public API: `petstore.Validated`, `petstore.validate`, `petstore.ValidationError`,
`petstore.Rule`

## Purpose

This module validates attribute values at the moment they are assigned, so that
a constructed object is a valid one and nothing downstream re-checks it. Rules
are ordinary functions, and `Validated` holds every mechanical concern: storage,
the write that works on frozen instances, the attribute name, and decorating a
failure with the attribute's label.

`validate` is what runs the rules: it applies them to a value in order and
labels the first failure. `Validated` calls it on every assignment. Called
directly, it checks a plain value, such as a function argument, that has no
attribute to hang a descriptor on.

## Usage

```python
from dataclasses import dataclass

from petstore import Validated, ValidationError


def positive(value: int) -> None:
    if value <= 0:
        message = "must be positive"
        raise ValidationError(message)


def even(value: int) -> None:
    if value % 2:
        message = "must be even"
        raise ValidationError(message)


@dataclass(frozen=True)
class Batch:
    size: Validated[int] = Validated(positive, even)


assert Batch(4).size == 4
```

The rule supplies only what is wrong; the descriptor supplies which attribute
it was:

```python
try:
    Batch(3)
except ValidationError as error:
    assert str(error) == "size must be even"
```

### The first failing rule is the one reported

Rules run in the order they are given, and validation stops at the first rule
that rejects the value. That rule's message is the failure; the rules after it
are not run at all. So a value with several problems reports one of them, the
first, and the next appears only once that one is fixed:

```python
try:
    Batch(-3)  # neither positive nor even
except ValidationError as error:
    assert str(error) == "size must be positive"  # even never ran

try:
    Batch(3)  # positive now, still odd
except ValidationError as error:
    assert str(error) == "size must be even"
```

Two things follow. Order the rules so the one a reader most needs to hear comes
first, usually the broadest. And a later rule may rely on every earlier rule
having passed: `even` above never sees a value that `positive` rejected.

The label defaults to the attribute name and can be replaced at declaration when
the attribute name is not what a reader should see:

```python
@dataclass
class Order:
    qty: Validated[int] = Validated(positive, label="order quantity")
```

Validation applies to later assignment exactly as it does to construction, so a
mutable owner cannot be moved into an invalid state after the fact. Reading the
attribute from the class rather than an instance returns the descriptor itself.

## Validating a plain value

A function argument has no attribute to hang a descriptor on. `validate` takes
the value, the rules and a label, and returns the value unchanged when every
rule accepts it, so the check sits on the assignment:

```python
from petstore import ValidationError, validate


def reserve(count: int) -> int:
    count = validate(count, positive, even, label="count")
    return count


assert reserve(4) == 4

try:
    reserve(3)
except ValidationError as error:
    assert str(error) == "count must be even"
```

What `validate` does with the rules, and so what every `Validated` attribute
does too:

- Rules run in order, and the first to reject the value is the one reported.
  The rules after it are not run. `validate(-3, positive, even, label="count")`
  fails with `count must be positive`, and `even` is never called.
- The failure is a new `ValidationError` reading `<label> <rule message>`,
  raised `from None`, so the rule's own exception is not chained onto it.
- An exception other than `ValidationError` raised by a rule propagates
  unchanged; it is a broken rule, not a rejected value.
- With no rules, the value is returned unchecked.

`label` is keyword-only and has no default. A failure that does not say which
value it is about is what this function exists to prevent, so the call site has
to name it.

## Requirements

[`docs/REQUIREMENTS/validation/`](../REQUIREMENTS/validation/) holds this
module's requirements, `FR-2.x`, one file each. Tests cite them with a
`# COVERS <ids> | <kind>` comment directly above the test.
