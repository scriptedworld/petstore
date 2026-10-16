# FR-8.6, Timed pass is asked for

| ID | Requirement | |
|---|---|---|
| FR-8.6 | `time_complexity` shall run no timed pass when `clock` is `None`, the default. Given a `Clock`, it shall run the timed pass only once the counted pass has passed. | [A] |

A count is the same on every machine and a timing is not, so a caller chooses
the timed pass. A count that already fails says what is wrong without timing
anything.
