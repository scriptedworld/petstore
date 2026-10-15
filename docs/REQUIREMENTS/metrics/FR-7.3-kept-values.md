# FR-7.3, Kept values

| ID | Requirement | |
|---|---|---|
| FR-7.3 | A measure with `keep=All()` shall keep every observation and answer `quantile(q)` for any q from 0 to 1 by linear interpolation between nearest ranks, `quantiles(*qs)`, and `under(x)` for any x, strictly below by default and at or below when `inclusive`; it shall expose the sorted observations as `sample.values`. | [A] |
