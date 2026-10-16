# FR-8.13, Runs is iterated once, in full

| ID | Requirement | |
|---|---|---|
| FR-8.13 | A timed call that leaves `probe.runs()` before it is exhausted, or iterates it more than once, shall fail the test. | [A] |

A call that always leaves early would otherwise be called again forever, since
it never gives a whole run, and a partial run would be judged against whole
ones. A second loop runs every block again on setup the first loop has already
used.
