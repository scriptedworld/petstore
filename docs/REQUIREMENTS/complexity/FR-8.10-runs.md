# FR-8.10, Runs

| ID | Requirement | |
|---|---|---|
| FR-8.10 | `probe.runs()` shall yield once on a counting `Probe` and `Clock.repeats` times on a `Stopwatch`, each iteration one run; a test that does not iterate `probe.runs()` shall be called `Clock.repeats` times per size on the timed pass, each call one run. | [A] |

Iterating `probe.runs()` lets setup be paid once per size, which is what makes
large sizes affordable.
