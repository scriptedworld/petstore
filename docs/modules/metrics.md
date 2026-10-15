# Metrics

Module: `petstore.metrics`, imported from the module itself and not from
`petstore`, so its `Counter` never shadows `collections.Counter`:

```python
from petstore.metrics import All, Last, StatsRecorder
```

Public API: `Metric`, `Counter`, `Measure`, `StatsRecorder`, `StatsSnapshot`,
`Distribution`, `Sample`, `All`, `Last`, `StatsError`

## Purpose

Count how often things happen and record values, then read back exact
summaries, quantiles and shares, without a dependency. A metric is an object
the measured code holds and calls; a recorder holds metrics by name so one
snapshot or one reset reaches all of them.

## Usage

```python
recorder = StatsRecorder()
hits = recorder.counter("hits")
load = recorder.measure("page_load", keep=All(), under=(1.0, 5.0))

hits()  # one more
hits(3)  # three more
load(2.4)  # one observation

snapshot = recorder.snapshot()
snapshot.count("hits")  # 4
d = snapshot.distribution("page_load")
d.mean, d.stdev  # running, exact, O(1) memory
d.quantile(0.85)  # p85, from the kept values
d.under(5.0)  # u5: the share of loads under 5.0
```

## What a measure can answer

A `Measure` always keeps an exact running summary: count, total, min, max,
mean and population standard deviation. Anything more depends on what it
keeps, chosen when it is made:

| Made with | Answers | Memory |
|---|---|---|
| nothing | the running summary | constant |
| `under=(x, ...)` | `u[x]` for each declared x, exact over all time | constant; nothing kept |
| `keep=All()` | any `p[x]` or `u[x]`, chosen afterwards, exact | grows with every observation |
| `keep=Last(n)` | any `p[x]` or `u[x]` over the most recent n, through `.sample` | n observations |

Everything a `Distribution` answers directly covers every observation since
the last reset. A recent window is reached only through `Distribution.sample`,
so a p95 cannot quietly change from all-time to recent when a window fills. A
question the measure cannot answer raises `StatsError` naming what it would
need, such as the thresholds that were declared.

Quantiles interpolate linearly between the two nearest ranks, numpy's default
and `statistics.quantiles(method="inclusive")`, so `quantile(0)` is the minimum
and `quantile(1)` the maximum.

## Recorders, snapshots and reset

- `counter(name)` and `measure(name, keep=..., under=...)` return the metric
  under that name, making it on first use. Asking again returns the same
  object; asking for a measure with a different configuration, or for a name
  held by another kind of metric, raises `StatsError`.
- `add(name, metric)` holds any `Metric`, including one of your own: a
  subclass implementing `snapshot()` and `reset()`.
- `snapshot()` returns a `StatsSnapshot`, immutable and detached from later
  recording. `count(name)` and `distribution(name)` read one metric back
  typed; `counts`, `measures` and `metrics` view them all.
- `reset()` clears every metric in place, so code already holding a metric
  keeps recording into the same recorder.

A `Counter` or `Measure` also works on its own, without a recorder.

## Threads

Not thread-safe. Recording is a read-modify-write on a metric's state, so two
threads recording at once can lose an update. Give each thread its own
recorder, or guard calls with a lock of your own.

## Requirements

[`docs/REQUIREMENTS/metrics/`](../REQUIREMENTS/metrics/) holds this module's
requirements, `FR-7.x`, one file each. Tests cite them with a
`# COVERS <ids> | <kind>` comment directly above the test.
