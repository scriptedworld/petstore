# FR-1.15, Directly tested dynamic fill factories

| ID | Requirement | |
|---|---|---|
| FR-1.15 | A fill specification wrapped in FillFactory shall invoke its zero-argument factory once for each missing output position and only when that position is missing. An unwrapped callable shall remain a static value and shall not be invoked. | [A] |

Retired: Replaced the FillFactory wrapper with direct zero-argument callable fill values to keep the public interface functional and minimal.
Superseded by FR-1.16.

Formerly PS-ITER-015.
