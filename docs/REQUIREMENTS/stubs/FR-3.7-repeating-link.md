# FR-3.7, Repeating link

| ID | Requirement | |
|---|---|---|
| FR-3.7 | always shall make the most recent link describe this and every later call, so a stub whose final link repeats is never called more times than its script describes. A repeated generator link shall build a fresh iterator on each call. always without a preceding link, and any link added after always, shall raise ValueError. | [A] |

Formerly PS-STUB-007.
