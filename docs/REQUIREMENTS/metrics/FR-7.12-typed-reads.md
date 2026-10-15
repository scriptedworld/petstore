# FR-7.12, Typed reads

| ID | Requirement | |
|---|---|---|
| FR-7.12 | A `StatsSnapshot` shall hold every metric's snapshot by name in `metrics`, read a counter back with `count(name)` and a measure with `distribution(name)`, refusing the wrong kind with `StatsError`, and gather each kind in `counts` and `measures`. | [A] |
