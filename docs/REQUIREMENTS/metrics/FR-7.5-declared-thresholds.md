# FR-7.5, Declared thresholds

| ID | Requirement | |
|---|---|---|
| FR-7.5 | A measure with `under=(x, ...)` shall answer `under(x)` exactly over every observation for each declared x, without keeping observations; an undeclared x with no complete sample shall be refused with `StatsError` naming the declared thresholds. | [A] |
