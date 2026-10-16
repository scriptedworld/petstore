# Python 3.14 is the floor

petstore requires Python 3.14 or later.

The reason is coverage. From 3.14, coverage measures through `sys.monitoring`
by default, branches included. Before 3.14 its default is a `sys.settrace`
tracer, which adds a fixed cost to every line the suite runs. Under that tracer
the timed pass of `petstore.complexity.time_complexity` hides growth behind the
tracer's own cost, so a complexity test run in the gate could pass code that
fails outside it. coverage's `env.py` sets `SYSMON_DEFAULT` from the Python
version, which is where this is read from. Its `timid` and `core` settings,
dynamic contexts, and `gevent`-style `concurrency` still select a tracer on
3.14, so the gate leaves them unset.

`.python-version` pins the development environment to 3.14, matching the Dev
Container. A consumer on an older Python cannot install petstore at all.
