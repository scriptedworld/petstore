# FR-8.12, Blocks belong to a run

| ID | Requirement | |
|---|---|---|
| FR-8.12 | In a timed call that iterates `probe.runs()`, a `probe.counting()` block entered before or after the loop shall fail the test. | [A] |

Such a block belongs to no run, so its time would be added to the wrong one or
lost.
