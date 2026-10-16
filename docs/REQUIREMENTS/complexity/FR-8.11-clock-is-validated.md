# FR-8.11, Clock is validated

| ID | Requirement | |
|---|---|---|
| FR-8.11 | `Clock` shall raise `petstore.ValidationError` for `repeats` below 1 or `tolerance` of 1 or less. | [A] |

No repeats leaves nothing to read, and a tolerance of 1 or less fails a block
whose time does not change at all.
