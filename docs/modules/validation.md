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

`validate` applies the same rules to a plain value, such as a function argument,
with the same failure format. `Validated` runs its rules through it, so the two
cannot drift apart.

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

Rules run in declaration order, and the first to reject a value determines the
failure. The rule supplies only what is wrong; the descriptor supplies which
attribute it was:

```python
try:
    Batch(3)
except ValidationError as error:
    assert str(error) == "size must be even"
```

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

It behaves exactly as the descriptor does, because the descriptor calls it:

- Rules run in order, and the first to reject the value determines the failure.
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
