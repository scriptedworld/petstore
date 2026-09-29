# FR-1.1, Deferred iteration

| ID | Requirement | |
|---|---|---|
| FR-1.1 | zip_iter shall return a lazy, single-pass iterator. It shall not call iter() on an input until the result is first advanced, and it shall not cache the input values. | [A] |

Formerly PS-ITER-001.
