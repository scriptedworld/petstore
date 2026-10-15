# FR-8.1, Growth classes

| ID | Requirement | |
|---|---|---|
| FR-8.1 | `assert_growth` shall accept measurements that, divided by the growth function, stay within `tolerance` (default 2) of their value at the smallest size, and fail otherwise naming the class, the sizes and the measurements; readings below `floor` shall count as `floor`. Ratios shall be compared in log space, so measurements and growth beyond float range work, and a factor too large to write shall be written as a power of ten. `Complexity` shall name the constant, logarithmic, square-root, linear, linearithmic, quadratic, cubic, exponential and factorial classes, each accepting work of its own class and refusing faster-growing work, and any object with a `label`, growth `function` and `min_span`, such as a `Growth`, shall serve as a class. | [A] |
