# FR-2.6, Plain value validation

| ID | Requirement | |
|---|---|---|
| FR-2.6 | `validate(value, *rules, label=...)` shall apply the rules to a value in order and return the value unchanged when every rule accepts it. The first ValidationError a rule raises shall stop validation, the rules after it not running, and shall be re-raised as ValidationError with the message `<label> <rule message>`, chained `from None`; any other exception from a rule shall propagate unchanged. `label` shall be keyword-only and required. `Validated` shall check each assignment by calling this function, so rule order and failure messages are defined once. | [A] |
