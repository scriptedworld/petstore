# FR-8.4, Memory decorator

| ID | Requirement | |
|---|---|---|
| FR-8.4 | `memory_complexity(growth, sizes=..., measure=...)` shall run the decorated test once per size with a fresh `Meter`, read with `tracemalloc` the bytes allocated inside `meter.measuring()` and still held at its end, or with `measure="peak"` the most allocated at once inside it, hold them to growth treating readings under `noise` bytes (default 4096) as noise, and fail a test that never entered `meter.measuring()`. | [A] |
