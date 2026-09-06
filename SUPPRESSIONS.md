# Static-analysis suppressions

Inline `# noqa` and `# nosec` declarations are prohibited unless a human has
approved the exact suppression before it is added. Findings from Bandit or any
other safety or security tool follow the same approval and recording process,
whether suppressed inline, in configuration, or through a tool baseline.

Every approved declaration must be recorded here with:

- its file and line;
- the originating tool;
- the complete rule identifier;
- the specific reason the exception was allowed and why the condition is safe;
- the approving person and approval date;
- a mandatory expiry date;
- the condition for removal rather than renewal.

Expired entries are invalid and must fail the quality gate. Renewal requires a
new human approval and a recorded justification; expiry dates may not be
extended silently.

Quality scores must be enforced per finding or per function. Findings must not
be hidden by averaging a score across a file.

## Approved suppressions

None.
