# FR-8.2, Probe

| ID | Requirement | |
|---|---|---|
| FR-8.2 | Inside `counting()` a `Probe` shall count every Python bytecode instruction executed (or with `granularity="lines"` every line), every hash and comparison made on keys from `probe.key()`, and every `tick(n)`; outside it, nothing. | [A] |
