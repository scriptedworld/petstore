# FR-8.9, A run is its counting blocks

| ID | Requirement | |
|---|---|---|
| FR-8.9 | A timed run's time shall be the sum of every `probe.counting()` block entered during it, and a run that enters none shall fail the test. | [A] |

A reading of zero from a run that measured nothing would let any test pass.
