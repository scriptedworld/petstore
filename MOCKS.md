# Approved mocks and patches

Mocking and runtime patching are prohibited by default. This ledger records
only cases explicitly approved by a human before implementation. An entry must
include the exact location, mechanism, reason it was allowed, approver,
approval date, expiry date, and removal condition.

Functions returned by `generate` in `tests/conftest.py` are not mock-ledger
entries. They are plain callables passed through explicit seams and do not
replace or patch runtime objects.

## Approved entries

None.

## Entry format

The following row is an example only. It is not an approval and must be removed
or replaced when recording a real decision.

| Location | Mechanism | Reason allowed | Approved by | Approval date | Expiry date | Removal condition |
| --- | --- | --- | --- | --- | --- | --- |
| `tests/example_test.py::test_example` | `example.patch.target` | Example justification, not an approved mock. | `EXAMPLE ONLY` | `YYYY-MM-DD` | `YYYY-MM-DD` | Example removal condition. |
