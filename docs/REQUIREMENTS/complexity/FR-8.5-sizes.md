# FR-8.5, Sizes

| ID | Requirement | |
|---|---|---|
| FR-8.5 | The decorators and `assert_growth` shall refuse, with `ValueError` naming the problem, fewer than 2 sizes, sizes not strictly ascending, a size below 1, or sizes spanning less than the class's `min_span`: 10 for polynomial classes and `Growth` by default, 2 for exponential and factorial. | [A] |
