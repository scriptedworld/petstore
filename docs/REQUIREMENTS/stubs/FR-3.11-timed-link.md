# FR-3.11, Timed link

| ID | Requirement | |
|---|---|---|
| FR-3.11 | over shall make the most recent link cover every call made within a duration given in hours, minutes, and seconds. The window shall open at the first call that reaches the link and shall be measured by the stub's clock, which shall be replaceable. A non-positive duration shall raise ValueError, and a timed final link whose window has closed shall leave the stub exhausted. | [A] |

Formerly PS-STUB-011.
