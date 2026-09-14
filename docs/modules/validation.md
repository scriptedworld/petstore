# Attribute validation

Module: `petstore.validation`

Public API: `petstore.Validated`, `petstore.ValidationError`, `petstore.Rule`

## Purpose

This module validates attribute values at the moment they are assigned, so that
a constructed object is a valid one and nothing downstream re-checks it. Rules
are ordinary functions, and `Validated` holds every mechanical concern: storage,
the write that works on frozen instances, the attribute name, and decorating a
failure with the attribute's label.

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

## Canonical requirements

[`validation.requirements.yaml`](validation.requirements.yaml) is the sole
normative source for this module's requirements. Requirement statements must
not be duplicated or edited in this Markdown file.

The YAML registry is append-only after requirements become active. IDs are
never deleted or reused; replaced behavior is retained with `status: retired`
and linked to its replacement through `superseded_by`.

| ID | Status | Title |
| --- | --- | --- |
| `PS-VALID-001` | Active | Validation on assignment |
| `PS-VALID-002` | Active | Rule sequencing |
| `PS-VALID-003` | Active | Failure labelling |
| `PS-VALID-004` | Active | Frozen owners |
| `PS-VALID-005` | Active | Class access |
