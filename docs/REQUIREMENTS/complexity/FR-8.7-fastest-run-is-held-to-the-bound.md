# FR-8.7, Fastest run is held to the bound

| ID | Requirement | |
|---|---|---|
| FR-8.7 | On the timed pass, `time_complexity` shall fail a test whose fastest of `Clock.repeats` timed runs at each size grows faster than the bound by more than `Clock.tolerance`, naming nanoseconds and the number of runs in the failure. | [A] |

The fastest run is the one least disturbed by everything else on the machine,
so it is the reading closest to the work itself.
