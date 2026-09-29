# FR-1.12, Dynamic fill factories

| ID | Requirement | |
|---|---|---|
| FR-1.12 | A fill specification wrapped in FillFactory shall invoke its zero-argument factory once for each missing output position and only when that position is missing. An unwrapped callable shall remain a static value and shall not be invoked. Factory resolution shall be isolated behind the injectable _fillvalue_resolver seam. | [A] |

Retired: User-supplied factory failures are directly testable and do not require an injected resolver seam.
Superseded by FR-1.15.

Formerly PS-ITER-012.
