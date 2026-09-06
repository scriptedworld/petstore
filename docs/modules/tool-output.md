# Canonical tool output

Module: `petstore.tool_output`

Public API: `ResultEnvelope`, `reason`, `result`, `as_document`, `render_yaml`,
and `exit_code`

## Envelope contract

Every project tool emits one deterministic YAML mapping with one required
field and two optional fields:

| Field | Presence | Value |
| --- | --- | --- |
| `success` | Required | Boolean terminal result. |
| `reasons` | Conditional | Non-empty sequence present only when `success` is `false`. |
| `metadata` | Optional | Tool-defined mapping permitted for either success value. |

A successful result can contain only the required field:

```yaml
---
success: true
```

Optional statistics and evidence belong beneath `metadata`:

```yaml
---
success: true
metadata:
  tool: petstore.requirements-traceability
  statistics:
    requirements_active: 24
    requirements_covered: 24
```

A failure contains at least one reason. Every reason has a required `message`
and may add fields meaningful to the producing tool:

```yaml
---
success: false
reasons:
  - message: Active requirement PS-EXAMPLE-004 has no tests.
    code: TRACE_REQUIREMENT_UNTESTED
    location:
      path: docs/modules/example.requirements.yaml
metadata:
  tool: petstore.requirements-traceability
```

`reasons` is forbidden when `success` is true. A false result without at least
one reason is also invalid. `metadata` is independent of the outcome and is
omitted when no metadata was supplied.

The envelope contains no timestamp, host path, random identifier, or telemetry
field. Identical input must produce identical output. Process exit codes are
`0` for success and `1` for failure.

## Canonical requirements

[`tool-output.requirements.yaml`](tool-output.requirements.yaml) is the sole
normative requirements source for this module. Requirement IDs are never
deleted or reused.
