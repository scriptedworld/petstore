# FR-8.3, Time decorator

| ID | Requirement | |
|---|---|---|
| FR-8.3 | `time_complexity(growth, sizes=...)` shall run the decorated test once per size with a fresh `Probe`, hold the counts to growth, fail a test that never entered `probe.counting()`, and present pytest with a test of no parameters under the original name and docstring. | [A] |
