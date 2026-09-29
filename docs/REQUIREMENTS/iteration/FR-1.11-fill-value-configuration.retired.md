# FR-1.11, Fill-value configuration

| ID | Requirement | |
|---|---|---|
| FR-1.11 | First and longest modes shall accept exactly one fill value for each input. Omitting fillvalues shall use None for every position. A mismatched number of fill values shall raise ValueError. Validation shall be isolated behind the injectable _fillvalue_parser seam. | [A] |

Retired: Fill-count failures are directly testable and do not require an injected seam.
Superseded by FR-1.14.

Formerly PS-ITER-011.
