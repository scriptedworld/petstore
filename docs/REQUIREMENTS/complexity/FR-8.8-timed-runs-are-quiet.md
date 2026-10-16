# FR-8.8, Timed runs are quiet

| ID | Requirement | |
|---|---|---|
| FR-8.8 | During a timed block garbage collection shall be off and `probe.key(value)` shall return a plain `int`, and garbage collection shall be left as it was found once the block ends, whether or not the block raised. | [A] |

A collection landing in one run would be noise, and a probe key's counting
methods would be time spent on the probe rather than on the code under test.
