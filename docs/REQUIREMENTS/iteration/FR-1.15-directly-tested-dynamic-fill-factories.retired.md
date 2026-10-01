# FR-1.15, Directly tested dynamic fill factories

| ID | Requirement | |
|---|---|---|
| FR-1.15 | A fill specification wrapped in FillFactory shall invoke its zero-argument factory once for each missing output position and only when that position is missing. An unwrapped callable shall remain a static value and shall not be invoked. | [A] |

Retired: a fill value is a zero-argument callable with no FillFactory wrapper, which keeps the public interface to functions.
Superseded by FR-1.16.
