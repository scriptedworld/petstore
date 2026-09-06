# Requirement traceability

Module: `petstore.traceability`

Command: `uv run poe requirements`

## Purpose

The checker proves structural traceability between canonical YAML requirement
registries and test definitions. It parses test source with Python's AST and
does not import or execute test modules.

For every directly collectable `test*` function and every `test*` method in a
`Test*` class, exactly one direct marker is required:

```python
@pytest.mark.requirement(
    "PS-MODULE-001",
    functionality=("module.read", "module.history"),
    test_type="positive",
)
```

`functionality` accepts one string or a literal tuple/list of strings. Multiple
values are necessary when one test covers requirements belonging to different
functional areas.

The checker mechanically verifies:

- registry structure, status, ID prefix, uniqueness, and `next_id`;
- exactly one direct, statically readable marker on every test definition;
- known active requirement references;
- at least one test for every active requirement;
- every required test classification for each active requirement;
- every declared functionality name for each active requirement; and
- deterministic normalized requirement and test evidence.

Draft and retired requirements cannot receive test evidence. Draft requirements
do not require tests. Retired records remain in their canonical registry and
their IDs can never be reused.

The checker does not claim that an assertion semantically proves a requirement.
Its normalized YAML evidence is intentionally suitable as input to a later
agent skill that evaluates test intent, classifications, exercised behavior,
and missing scenarios.

## Reason codes

Failed envelopes place the human explanation in `message` and the following
stable identifier in the reason's `code` field.

| Code | Meaning |
| --- | --- |
| `TRACE_EXECUTION_ERROR` | Required project files could not be read. |
| `TRACE_REGISTRY_INVALID` | A registry is malformed or contains invalid values. |
| `TRACE_REQUIREMENT_DUPLICATE` | An ID is repeated locally or globally. |
| `TRACE_NEXT_ID_INVALID` | `next_id` does not follow the greatest allocated ID. |
| `TRACE_TEST_INVALID` | A test module contains invalid Python syntax. |
| `TRACE_MARKER_MISSING` | A test lacks exactly one direct marker. |
| `TRACE_MARKER_INVALID` | Marker arguments are not canonical literals. |
| `TRACE_REQUIREMENT_UNKNOWN` | A marker references an undeclared ID. |
| `TRACE_REQUIREMENT_INACTIVE` | A marker references a draft or retired ID. |
| `TRACE_REQUIREMENT_UNTESTED` | An active requirement has no test evidence. |
| `TRACE_TEST_TYPE_MISSING` | A required test classification is absent. |
| `TRACE_FUNCTIONALITY_UNKNOWN` | Marker functionality is undeclared. |
| `TRACE_FUNCTIONALITY_MISSING` | A multi-ID marker does not represent one referenced ID. |
| `TRACE_FUNCTIONALITY_UNTESTED` | Declared functionality has no test evidence. |

## Canonical requirements

[`traceability.requirements.yaml`](traceability.requirements.yaml) is the sole
normative requirements source for this module. Requirement IDs are never
deleted or reused.
