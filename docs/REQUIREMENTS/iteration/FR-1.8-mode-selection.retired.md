# FR-1.8, Mode selection

| ID | Requirement | |
|---|---|---|
| FR-1.8 | Modes shall be selectable using either a ZipMode member or its string value. An unsupported string shall raise ValueError with a diagnostic identifying the invalid mode and the supported choices. Mode validation shall be isolated behind the injectable _mode_parser seam. | [A] |

Retired: The validation path is directly testable and does not require an injected seam.
Superseded by FR-1.13.

Formerly PS-ITER-008.
