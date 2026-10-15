# FR-7.11, Any metric

| ID | Requirement | |
|---|---|---|
| FR-7.11 | `StatsRecorder.add(name, metric)` shall hold any `Metric` under name and return it, include it in every snapshot and reset, return it again when the same object is added under its name, and refuse with `StatsError` a different metric under a taken name. | [A] |
