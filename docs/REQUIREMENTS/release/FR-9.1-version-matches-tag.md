# FR-9.1, One version, matching the release tag

| ID | Requirement | |
|---|---|---|
| FR-9.1 | The version shall be written once, in pyproject.toml, and `petstore.__version__` shall read it back from the installed metadata. It shall equal the release tag on the commit that carries one, written without the `v`, and shall be no lower than the latest release tag the commit descends from. | [A] |
