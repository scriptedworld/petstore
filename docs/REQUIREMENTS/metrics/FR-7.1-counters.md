# FR-7.1, Counters

| ID | Requirement | |
|---|---|---|
| FR-7.1 | `StatsRecorder.counter(name)` shall return the `Counter` under name, adding one if there is none; calling it adds n (default 1), refusing a negative n with `StatsError`; asking again for the same name shall return the same counter. | [A] |
