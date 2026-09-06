"""Tests for mechanical requirement traceability analysis."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from petstore.tool_output import ResultEnvelope
from petstore.tool_output import result as make_result
from petstore.traceability import (
    CliPolicy,
    Registry,
    Requirement,
    TraceabilityPolicy,
    analyze_traceability,
    check_requirements,
    main,
    make_checker,
    make_main,
    parse_registry,
    parse_test_module,
)
from petstore.traceability import TestEvidence as CollectedTestEvidence
from tests.conftest import generate

VALID_REGISTRY = """\
schema_version: 1
module: example
id_prefix: EX
next_id: 2
requirements:
  - id: EX-001
    title: Example
    status: active
    functionality:
      - example.run
    required_test_types:
      - positive
"""

VALID_TEST_MODULE = """\
import pytest

@pytest.mark.requirement(
    "EX-001",
    functionality="example.run",
    test_type="positive",
)
def test_example():
    pass
"""


def _requirement(
    identifier: str,
    *,
    status: str = "active",
    functionality: tuple[str, ...] = ("example.run",),
    test_types: tuple[str, ...] = ("positive",),
    registry: str = "requirements.yaml",
) -> Requirement:
    """Build normalized requirement input for analysis tests."""
    return Requirement(identifier, status, functionality, test_types, registry, None)


def _test(
    *identifiers: str,
    functionality: tuple[str, ...] = ("example.run",),
    test_type: str = "positive",
) -> CollectedTestEvidence:
    """Build normalized test evidence for analysis tests."""
    return CollectedTestEvidence("test_example", "test_example.py", 10, identifiers, functionality, test_type)


def _registry(*requirements: Requirement, path: str = "requirements.yaml") -> Registry:
    """Build one normalized registry for analysis tests."""
    return Registry(path, "EX", len(requirements) + 1, requirements)


def _codes(envelope: ResultEnvelope) -> set[str]:
    """Return the reason codes in a result envelope."""
    return {str(item["code"]) for item in envelope.reasons}


def _metadata(envelope: ResultEnvelope) -> dict[str, object]:
    """Return metadata known to be present in traceability results."""
    assert envelope.metadata is not None
    return envelope.metadata


@pytest.mark.requirement(
    "PS-TRACE-001",
    functionality="traceability.project",
    test_type="positive",
)
def test_project_checker_discovers_and_analyzes_repository_files(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify default boundaries analyze the current project without execution."""
    expected_minimum_registries = 4
    result = check_requirements(Path.cwd())

    assert result.success
    statistics = _metadata(result)["statistics"]
    assert isinstance(statistics, dict)
    registry_count = statistics["registries"]
    assert isinstance(registry_count, int)
    assert registry_count >= expected_minimum_registries
    assert main() == 0
    assert yaml.safe_load(capsys.readouterr().out)["success"] is True


@pytest.mark.requirement(
    "PS-TRACE-002",
    functionality="traceability.test_parser",
    test_type="positive",
)
def test_parser_extracts_sync_async_and_class_test_markers() -> None:
    """Verify direct markers and collectable test identities are normalized."""
    source = (
        VALID_TEST_MODULE
        + """\

@pytest.mark.requirement("EX-001", functionality=("example.run", "example.read"), test_type="edge")
async def test_async():
    pass

class TestGroup:
    @pytest.mark.requirement("EX-001", functionality=["example.run"], test_type="positive")
    def test_method(self):
        pass

def helper():
    pass

class Ignored:
    def test_method(self):
        pass
"""
    )

    parsed = parse_test_module("tests/test_example.py", source)

    assert not parsed.findings
    assert [test.node_id for test in parsed.tests] == ["test_example", "test_async", "TestGroup::test_method"]
    assert parsed.tests[1].functionality == ("example.run", "example.read")
    assert parsed.tests[2].line > parsed.tests[1].line


@pytest.mark.requirement(
    "PS-TRACE-003",
    functionality="traceability.registry_parser",
    test_type="negative",
)
@pytest.mark.parametrize(
    "document",
    [
        "not: [valid",
        "[]",
        "1: invalid",
        "requirements: []",
        VALID_REGISTRY.replace("id_prefix: EX", "id_prefix: ''"),
        VALID_REGISTRY.replace("status: active", "status: unknown"),
        VALID_REGISTRY.replace("id: EX-001", "id: OTHER-001"),
        VALID_REGISTRY.replace("id: EX-001", "id: EX-zero"),
        VALID_REGISTRY.replace("next_id: 2", "next_id: false"),
        VALID_REGISTRY.replace("next_id: 2", "next_id: zero"),
        VALID_REGISTRY.replace("next_id: 2", "next_id: 0"),
        VALID_REGISTRY.replace("- positive", "- unsupported"),
        VALID_REGISTRY.replace("- example.run", "- ''"),
        VALID_REGISTRY.replace("- example.run", "- example.run\n      - example.run"),
        VALID_REGISTRY.replace("functionality:\n      - example.run", "functionality: example.run"),
    ],
)
def test_registry_parser_rejects_invalid_documents(document: str) -> None:
    """Verify malformed registry structures become stable findings."""
    parsed = parse_registry("requirements.yaml", document)

    assert parsed.registry is None
    assert parsed.findings[0].code == "TRACE_REGISTRY_INVALID"


@pytest.mark.requirement(
    "PS-TRACE-003",
    functionality="traceability.registry_parser",
    test_type="negative",
)
def test_registry_parser_reports_duplicate_ids_and_invalid_next_id() -> None:
    """Verify registry-level allocation invariants produce distinct findings."""
    duplicate = VALID_REGISTRY.replace("next_id: 2", "next_id: 4").replace(
        "    required_test_types:\n      - positive",
        "    required_test_types:\n      - positive\n  - id: EX-001\n    status: retired\n    functionality: []\n    required_test_types: []",
    )

    parsed = parse_registry("requirements.yaml", duplicate)

    assert parsed.registry is not None
    assert {finding.code for finding in parsed.findings} == {"TRACE_REQUIREMENT_DUPLICATE", "TRACE_NEXT_ID_INVALID"}


@pytest.mark.requirement(
    "PS-TRACE-004",
    functionality="traceability.references",
    test_type="negative",
)
def test_analysis_rejects_unknown_inactive_and_globally_duplicate_ids() -> None:
    """Verify only globally unique active requirements can receive evidence."""
    active = _requirement("EX-001")
    retired = _requirement("EX-002", status="retired")
    registries = (_registry(active, retired), _registry(active, path="other.yaml"))
    tests = (_test("EX-001"), _test("EX-002"), _test("EX-999"))

    result = analyze_traceability(registries, tests)

    assert {"TRACE_REQUIREMENT_DUPLICATE", "TRACE_REQUIREMENT_INACTIVE", "TRACE_REQUIREMENT_UNKNOWN"} <= _codes(result)


@pytest.mark.requirement(
    "PS-TRACE-005",
    functionality="traceability.requirement_coverage",
    test_type="negative",
)
def test_analysis_requires_tests_only_for_active_requirements() -> None:
    """Verify uncovered active IDs fail while draft and retired IDs do not."""
    requirements = (
        _requirement("EX-001"),
        _requirement("EX-002", status="draft"),
        _requirement("EX-003", status="retired"),
    )

    result = analyze_traceability((_registry(*requirements),), ())

    assert _codes(result) == {"TRACE_REQUIREMENT_UNTESTED"}
    assert _metadata(result)["summary"] == "0 of 1 active requirements have test evidence"


@pytest.mark.requirement(
    "PS-TRACE-006",
    functionality="traceability.test_type_coverage",
    test_type="negative",
)
def test_analysis_requires_every_declared_test_classification() -> None:
    """Verify partial classification evidence identifies the missing type."""
    requirement = _requirement("EX-001", test_types=("positive", "edge"))

    result = analyze_traceability((_registry(requirement),), (_test("EX-001"),))

    assert _codes(result) == {"TRACE_TEST_TYPE_MISSING"}
    assert "'edge'" in str(result.reasons[0]["message"])


@pytest.mark.requirement(
    "PS-TRACE-007",
    functionality="traceability.functionality_coverage",
    test_type="negative",
)
def test_analysis_rejects_unknown_and_missing_functionality() -> None:
    """Verify test-wide and per-requirement functionality checks both run."""
    first = _requirement("EX-001", functionality=("example.run", "example.read"))
    second = _requirement("EX-002", functionality=("example.write",))
    test = _test("EX-001", "EX-002", functionality=("example.run", "example.unknown"))

    result = analyze_traceability((_registry(first, second),), (test,))

    assert {
        "TRACE_FUNCTIONALITY_UNKNOWN",
        "TRACE_FUNCTIONALITY_MISSING",
        "TRACE_FUNCTIONALITY_UNTESTED",
    } <= _codes(result)


@pytest.mark.requirement(
    "PS-TRACE-008",
    functionality="traceability.evidence",
    test_type="positive",
)
def test_passing_analysis_emits_complete_normalized_evidence() -> None:
    """Verify successful reports preserve requirement and test evidence."""
    requirement = _requirement("EX-001")
    test = _test("EX-001")

    result = analyze_traceability((_registry(requirement),), (test,))

    assert result.success
    metadata = _metadata(result)
    assert metadata["summary"] == "1 of 1 active requirements have test evidence"
    requirements = metadata["requirements"]
    tests = metadata["tests"]
    assert isinstance(requirements, list)
    assert isinstance(tests, list)
    assert requirements[0]["tests"] == ["test_example"]
    assert tests[0]["requirements"] == ["EX-001"]


@pytest.mark.requirement(
    "PS-TRACE-009",
    functionality="traceability.input_findings",
    test_type="negative",
)
def test_invalid_python_and_filesystem_failures_become_findings() -> None:
    """Verify syntax and I/O failures are reported without escaping."""
    parsed = parse_test_module("tests/test_broken.py", "def test_broken(:")

    def fail_discovery(root: Path) -> tuple[Path, ...]:
        """Raise a deterministic filesystem failure."""
        raise OSError(root)

    def no_tests(root: Path) -> tuple[Path, ...]:
        """Return no test paths for the unreachable fallback boundary."""
        del root
        return ()

    def no_text(path: Path) -> str:
        """Return no text for the unreachable fallback boundary."""
        del path
        return ""

    checker = make_checker(TraceabilityPolicy(fail_discovery, no_tests, no_text))
    result = checker(Path("project"))

    assert parsed.findings[0].code == "TRACE_TEST_INVALID"
    assert not result.success
    assert result.reasons[0]["code"] == "TRACE_EXECUTION_ERROR"


@pytest.mark.requirement(
    "PS-TRACE-001",
    "PS-TRACE-009",
    functionality=("traceability.project", "traceability.input_findings"),
    test_type="negative",
)
def test_project_checker_retains_registry_parse_findings(tmp_path: Path) -> None:
    """Verify malformed discovered files are skipped and reported."""
    docs = tmp_path / "docs"
    tests = tmp_path / "tests"
    docs.mkdir()
    tests.mkdir()
    (docs / "broken.requirements.yaml").write_text("not: [valid", encoding="utf-8")
    (tests / "test_example.py").write_text(VALID_TEST_MODULE, encoding="utf-8")

    envelope = check_requirements(tmp_path)

    assert not envelope.success
    assert "TRACE_REGISTRY_INVALID" in _codes(envelope)


@pytest.mark.requirement(
    "PS-TRACE-009",
    "PS-TRACE-010",
    functionality=("traceability.input_findings", "traceability.marker_presence"),
    test_type="negative",
)
@pytest.mark.parametrize(
    "marker",
    [
        "",
        "@pytest.mark.requirement()\n",
        "@pytest.mark.requirement('EX-001', 'EX-001', functionality='example.run', test_type='positive')\n",
        "@pytest.mark.requirement(1, functionality='example.run', test_type='positive')\n",
        "@pytest.mark.requirement('EX-001', functionality=(), test_type='positive')\n",
        "@pytest.mark.requirement('EX-001', functionality=('example.run', 'example.run'), test_type='positive')\n",
        "@pytest.mark.requirement('EX-001', functionality='example.run', test_type='unknown')\n",
        "@pytest.mark.requirement('EX-001', functionality='example.run', test_type='positive', extra=True)\n",
        "@pytest.mark.requirement('EX-001', **{'functionality': 'example.run', 'test_type': 'positive'})\n",
    ],
)
def test_missing_or_malformed_markers_become_findings(marker: str) -> None:
    """Verify every test requires one statically analyzable direct marker."""
    source = f"import pytest\n{marker}def test_example():\n    pass\n"

    parsed = parse_test_module("tests/test_example.py", source)

    assert len(parsed.findings) == 1
    assert parsed.findings[0].code in {"TRACE_MARKER_MISSING", "TRACE_MARKER_INVALID"}


@pytest.mark.requirement(
    "PS-TRACE-011",
    functionality="traceability.command",
    test_type="positive",
)
def test_composed_command_emits_yaml_and_returns_the_result_exit_code() -> None:
    """Verify command composition forwards the current root and result."""
    project_root = Path("project")
    expected_result = make_result(success=True, metadata={"tool": "example"})
    checker = generate(returns=expected_result, parameters=["root"])
    current_directory = generate(returns=project_root)
    writer = generate(returns=None, parameters=["value"])
    command = make_main(checker=checker, policy=CliPolicy(current_directory, writer))

    actual_exit_code = command()

    assert actual_exit_code == 0
    assert checker.calls[0].args == (project_root,)
    rendered = writer.calls[0].args[0]
    assert isinstance(rendered, str)
    assert yaml.safe_load(rendered)["success"] is True
