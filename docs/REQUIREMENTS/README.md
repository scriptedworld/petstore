# Requirements

One directory per module, one file per requirement. The row in each file is
the requirement; a file ending `.retired.md` holds an ID that has gone and
is never reused. Tests cite them with `# COVERS <ids> | <kind>` directly
above the test, and toolbox's `test-traceability.py` checks both directions.

    iteration   FR-1.x     validation  FR-2.x     stubs     FR-3.x
    generate    FR-4.x     locking     FR-5.x     proc      FR-6.x
    metrics     FR-7.x     complexity  FR-8.x     release   FR-9.x

## Earlier IDs

A `PS-` ID comes from the YAML registries under `docs/modules/` that this
directory replaces, and maps to its FR ID below. The `PS-TRACE` and `PS-OUT`
requirements retired with `petstore.traceability` and `petstore.tool_output`
and have no replacement.

| Earlier ID | Now | Status |
|---|---|---|
| PS-ITER-001 | FR-1.1 | active |
| PS-ITER-002 | FR-1.2 | active |
| PS-ITER-003 | FR-1.3 | active |
| PS-ITER-004 | FR-1.4 | active |
| PS-ITER-005 | FR-1.5 | retired |
| PS-ITER-006 | FR-1.6 | retired |
| PS-ITER-007 | FR-1.7 | active |
| PS-ITER-008 | FR-1.8 | retired |
| PS-ITER-009 | FR-1.9 | active |
| PS-ITER-010 | FR-1.10 | active |
| PS-ITER-011 | FR-1.11 | retired |
| PS-ITER-012 | FR-1.12 | retired |
| PS-ITER-013 | FR-1.13 | active |
| PS-ITER-014 | FR-1.14 | active |
| PS-ITER-015 | FR-1.15 | retired |
| PS-ITER-016 | FR-1.16 | active |
| PS-VALID-001 | FR-2.1 | active |
| PS-VALID-002 | FR-2.2 | active |
| PS-VALID-003 | FR-2.3 | active |
| PS-VALID-004 | FR-2.4 | active |
| PS-VALID-005 | FR-2.5 | active |
| PS-STUB-001 | FR-3.1 | active |
| PS-STUB-002 | FR-3.2 | active |
| PS-STUB-003 | FR-3.3 | active |
| PS-STUB-004 | FR-3.4 | active |
| PS-STUB-005 | FR-3.5 | active |
| PS-STUB-006 | FR-3.6 | active |
| PS-STUB-007 | FR-3.7 | active |
| PS-STUB-008 | FR-3.8 | retired |
| PS-STUB-009 | FR-3.9 | retired |
| PS-STUB-010 | FR-3.10 | active |
| PS-STUB-011 | FR-3.11 | active |
| PS-STUB-012 | FR-3.12 | active |
| PS-TEST-001 | FR-4.1 | retired |
| PS-TEST-002 | FR-4.2 | retired |
| PS-TEST-003 | FR-4.3 | retired |
| PS-TEST-004 | FR-4.4 | retired |
| PS-TEST-005 | FR-4.5 | retired |
| PS-TEST-006 | FR-4.6 | retired |
| PS-TEST-007 | FR-4.7 | active |
| PS-TEST-008 | FR-4.8 | active |
| PS-TEST-009 | FR-4.9 | retired |
| PS-TEST-010 | FR-4.10 | active |
| PS-TEST-011 | FR-4.11 | active |
| PS-TEST-012 | FR-4.12 | active |
| PS-TEST-013 | FR-4.13 | active |
| PS-LOCK-001 | FR-5.1 | active |
| PS-LOCK-002 | FR-5.2 | active |
| PS-LOCK-003 | FR-5.3 | active |
| PS-LOCK-004 | FR-5.4 | active |
| PS-LOCK-005 | FR-5.5 | active |
| PS-LOCK-006 | FR-5.6 | active |
| PS-TRACE-001 | none | retired with `petstore.traceability` |
| PS-TRACE-002 | none | retired with `petstore.traceability` |
| PS-TRACE-003 | none | retired with `petstore.traceability` |
| PS-TRACE-004 | none | retired with `petstore.traceability` |
| PS-TRACE-005 | none | retired with `petstore.traceability` |
| PS-TRACE-006 | none | retired with `petstore.traceability` |
| PS-TRACE-007 | none | retired with `petstore.traceability` |
| PS-TRACE-008 | none | retired with `petstore.traceability` |
| PS-TRACE-009 | none | retired with `petstore.traceability` |
| PS-TRACE-010 | none | retired with `petstore.traceability` |
| PS-TRACE-011 | none | retired with `petstore.traceability` |
| PS-OUT-001 | none | retired with `petstore.tool_output` |
| PS-OUT-002 | none | retired with `petstore.tool_output` |
| PS-OUT-003 | none | retired with `petstore.tool_output` |
| PS-OUT-004 | none | retired with `petstore.tool_output` |
| PS-OUT-005 | none | retired with `petstore.tool_output` |
| PS-OUT-006 | none | retired with `petstore.tool_output` |
| PS-OUT-007 | none | retired with `petstore.tool_output` |
| PS-OUT-008 | none | retired with `petstore.tool_output` |
