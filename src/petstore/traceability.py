"""Mechanical requirement-to-test traceability analysis."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

import yaml

from .tool_output import ResultEnvelope, exit_code, reason, render_yaml
from .tool_output import result as make_result

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence


TOOL_NAME = "petstore.requirements-traceability"
ALLOWED_TEST_TYPES = frozenset({"positive", "negative", "edge", "property", "invariant", "regression"})
ALLOWED_STATUSES = frozenset({"active", "draft", "retired"})


class SourceLocation(NamedTuple):
    """Source location associated with a traceability finding."""

    path: str
    line: int | None = None


class TraceabilityFinding(NamedTuple):
    """One normalized traceability failure."""

    code: str
    message: str
    location: SourceLocation


class Requirement(NamedTuple):
    """Normalized requirement from one canonical registry."""

    identifier: str
    status: str
    functionality: tuple[str, ...]
    required_test_types: tuple[str, ...]
    registry: str
    line: int | None


class Registry(NamedTuple):
    """Normalized canonical requirement registry."""

    path: str
    prefix: str
    next_id: int
    requirements: tuple[Requirement, ...]


class TestEvidence(NamedTuple):
    """Normalized traceability marker attached to one test definition."""

    node_id: str
    path: str
    line: int
    requirement_ids: tuple[str, ...]
    functionality: tuple[str, ...]
    test_type: str


class RegistryParse(NamedTuple):
    """Result of parsing one registry document."""

    registry: Registry | None
    findings: tuple[TraceabilityFinding, ...]


class TestParse(NamedTuple):
    """Result of parsing one test module."""

    tests: tuple[TestEvidence, ...]
    findings: tuple[TraceabilityFinding, ...]


class TraceabilityPolicy(NamedTuple):
    """Filesystem boundary functions used by project analysis."""

    registry_paths: Callable[[Path], tuple[Path, ...]]
    test_paths: Callable[[Path], tuple[Path, ...]]
    read_text: Callable[[Path], str]


class CliPolicy(NamedTuple):
    """Process boundary functions used by the command entry point."""

    current_directory: Callable[[], Path]
    write: Callable[[str], object]


def parse_registry(path: str, text: str) -> RegistryParse:
    """Parse and structurally validate one canonical registry document."""
    try:
        document = _mapping(yaml.safe_load(text), "registry root")
        prefix = _string(document["id_prefix"], "id_prefix")
        next_id = _integer(document["next_id"], "next_id")
        items = _sequence(document["requirements"], "requirements")
        requirements = tuple(_parse_requirement(path, prefix, item) for item in items)
        registry = Registry(path, prefix, next_id, requirements)
        findings = _registry_findings(registry)
    except (KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        finding = _finding("TRACE_REGISTRY_INVALID", f"invalid requirement registry: {error}", path)
        return RegistryParse(None, (finding,))
    return RegistryParse(registry, findings)


def parse_test_module(path: str, text: str) -> TestParse:
    """Extract direct requirement markers from collectable test definitions."""
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as error:
        finding = _finding("TRACE_TEST_INVALID", f"test module could not be parsed: {error.msg}", path, error.lineno)
        return TestParse((), (finding,))

    tests: list[TestEvidence] = []
    findings: list[TraceabilityFinding] = []
    for qualifier, node in _test_nodes(tree):
        parsed = _parse_test_marker(path, qualifier, node)
        if isinstance(parsed, TraceabilityFinding):
            findings.append(parsed)
        else:
            tests.append(parsed)
    return TestParse(tuple(tests), tuple(findings))


def analyze_traceability(
    registries: Iterable[Registry],
    tests: Iterable[TestEvidence],
    initial_findings: Iterable[TraceabilityFinding] = (),
) -> ResultEnvelope:
    """Compare normalized requirements with normalized test evidence."""
    registry_items = tuple(registries)
    test_items = tuple(tests)
    findings = list(initial_findings)
    requirements = _index_requirements(registry_items, findings)
    coverage = _index_coverage(requirements, test_items, findings)
    _check_active_requirements(requirements, coverage, findings)
    ordered_findings = tuple(sorted(findings, key=_finding_sort_key))
    active_count = sum(requirement.status == "active" for requirement in requirements.values())
    covered_count = sum(requirement.status == "active" and bool(coverage.get(identifier)) for identifier, requirement in requirements.items())
    summary = f"{covered_count} of {active_count} active requirements have test evidence"
    return make_result(
        success=not ordered_findings,
        reasons=tuple(_reason_record(finding) for finding in ordered_findings),
        metadata={
            "tool": TOOL_NAME,
            "summary": summary,
            "statistics": {
                "registries": len(registry_items),
                "requirements_active": active_count,
                "requirements_covered": covered_count,
                "tests": len(test_items),
                "reasons": len(ordered_findings),
            },
            "requirements": list(_requirement_records(requirements, coverage)),
            "tests": [_test_record(test) for test in test_items],
        },
    )


def make_checker(
    policy: TraceabilityPolicy | None = None,
) -> Callable[[Path], ResultEnvelope]:
    """Bind filesystem operations and return a project traceability checker."""
    selected_policy = policy or TraceabilityPolicy(_registry_paths, _test_paths, _read_text)

    def check(root: Path) -> ResultEnvelope:
        """Check requirement traceability beneath a project root."""
        return _check_project(root, policy=selected_policy)

    return check


def make_main(
    checker: Callable[[Path], ResultEnvelope] | None = None,
    policy: CliPolicy | None = None,
) -> Callable[[], int]:
    """Bind command boundaries and return the console entry point."""
    selected_checker = checker or check_requirements
    selected_policy = policy or CliPolicy(Path.cwd, _write_stdout)

    def entrypoint() -> int:
        """Analyze the current project and emit canonical YAML."""
        envelope = selected_checker(selected_policy.current_directory())
        selected_policy.write(render_yaml(envelope))
        return exit_code(envelope)

    return entrypoint


def _check_project(root: Path, *, policy: TraceabilityPolicy) -> ResultEnvelope:
    """Read, normalize, and analyze one project."""
    registries: list[Registry] = []
    tests: list[TestEvidence] = []
    findings: list[TraceabilityFinding] = []
    try:
        for path in policy.registry_paths(root):
            parsed_registry = parse_registry(_relative_path(root, path), policy.read_text(path))
            findings.extend(parsed_registry.findings)
            if parsed_registry.registry is not None:
                registries.append(parsed_registry.registry)
        for path in policy.test_paths(root):
            parsed_tests = parse_test_module(_relative_path(root, path), policy.read_text(path))
            findings.extend(parsed_tests.findings)
            tests.extend(parsed_tests.tests)
    except OSError as error:
        finding = _finding("TRACE_EXECUTION_ERROR", f"project files could not be read: {error}", str(root))
        return make_result(
            success=False,
            reasons=(_reason_record(finding),),
            metadata={"tool": TOOL_NAME, "summary": "traceability analysis could not run"},
        )
    return analyze_traceability(registries, tests, findings)


def _parse_requirement(path: str, prefix: str, value: object) -> Requirement:
    """Normalize one requirement mapping."""
    item = _mapping(value, "requirement")
    identifier = _string(item["id"], "requirement id")
    status = _string(item["status"], "requirement status")
    functionality = _strings(item["functionality"], "functionality")
    required_test_types = _strings(item["required_test_types"], "required_test_types")
    if status not in ALLOWED_STATUSES:
        msg = f"unsupported requirement status {status!r}"
        raise ValueError(msg)
    if not identifier.startswith(f"{prefix}-"):
        msg = f"requirement ID {identifier!r} does not use prefix {prefix!r}"
        raise ValueError(msg)
    if not set(required_test_types) <= ALLOWED_TEST_TYPES:
        msg = f"requirement {identifier!r} contains an unsupported test type"
        raise ValueError(msg)
    return Requirement(identifier, status, functionality, required_test_types, path, None)


def _registry_findings(registry: Registry) -> tuple[TraceabilityFinding, ...]:
    """Validate ID uniqueness and next-ID monotonicity within a registry."""
    identifiers = tuple(requirement.identifier for requirement in registry.requirements)
    findings: list[TraceabilityFinding] = []
    if len(identifiers) != len(set(identifiers)):
        findings.append(_finding("TRACE_REQUIREMENT_DUPLICATE", "registry contains duplicate requirement IDs", registry.path))
    numbers = tuple(_requirement_number(identifier, registry.prefix) for identifier in identifiers)
    expected_next = max(numbers, default=0) + 1
    if registry.next_id != expected_next:
        message = f"next_id is {registry.next_id}; expected {expected_next}"
        findings.append(_finding("TRACE_NEXT_ID_INVALID", message, registry.path))
    return tuple(findings)


def _parse_test_marker(
    path: str,
    qualifier: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> TestEvidence | TraceabilityFinding:
    """Parse the one required direct traceability marker on a test."""
    markers = tuple(decorator for decorator in node.decorator_list if _is_requirement_marker(decorator))
    location = SourceLocation(path, node.lineno)
    if len(markers) != 1:
        message = f"{qualifier} must declare exactly one direct pytest.mark.requirement marker"
        return TraceabilityFinding("TRACE_MARKER_MISSING", message, location)
    marker = cast("ast.Call", markers[0])
    try:
        requirement_ids = tuple(_literal_string(argument, "requirement ID") for argument in marker.args)
        keywords = _marker_keywords(marker)
        functionality = _literal_strings(keywords["functionality"], "functionality")
        test_type = _literal_string(keywords["test_type"], "test_type")
        _validate_marker_values(requirement_ids, keywords, test_type)
    except (KeyError, TypeError, ValueError) as error:
        message = f"{qualifier} has an invalid requirement marker: {error}"
        return TraceabilityFinding("TRACE_MARKER_INVALID", message, location)
    return TestEvidence(qualifier, path, node.lineno, requirement_ids, functionality, test_type)


def _validate_marker_values(
    requirement_ids: tuple[str, ...],
    keywords: Mapping[str, ast.expr],
    test_type: str,
) -> None:
    """Validate normalized marker values."""
    if not requirement_ids or len(requirement_ids) != len(set(requirement_ids)):
        message = "requirement IDs must be present and unique"
        raise ValueError(message)
    if test_type not in ALLOWED_TEST_TYPES:
        message = f"unsupported test type {test_type!r}"
        raise ValueError(message)
    if set(keywords) != {"functionality", "test_type"}:
        message = "marker requires only functionality and test_type keywords"
        raise ValueError(message)


def _index_requirements(registries: Sequence[Registry], findings: list[TraceabilityFinding]) -> dict[str, Requirement]:
    """Index globally unique requirements."""
    indexed: dict[str, Requirement] = {}
    for registry in registries:
        for requirement in registry.requirements:
            if requirement.identifier in indexed:
                message = f"requirement ID {requirement.identifier} is declared by multiple registries"
                findings.append(_finding("TRACE_REQUIREMENT_DUPLICATE", message, requirement.registry, requirement.line))
            else:
                indexed[requirement.identifier] = requirement
    return indexed


def _index_coverage(
    requirements: Mapping[str, Requirement],
    tests: Sequence[TestEvidence],
    findings: list[TraceabilityFinding],
) -> dict[str, list[TestEvidence]]:
    """Validate test references and index usable evidence by requirement."""
    coverage: dict[str, list[TestEvidence]] = {}
    for test in tests:
        referenced = tuple(requirements.get(identifier) for identifier in test.requirement_ids)
        _check_test_references(test, referenced, findings)
        active = tuple(requirement for requirement in referenced if requirement is not None and requirement.status == "active")
        _check_test_functionality(test, active, findings)
        _record_coverage(test, active, coverage)
    return coverage


def _check_test_functionality(
    test: TestEvidence,
    requirements: Sequence[Requirement],
    findings: list[TraceabilityFinding],
) -> None:
    """Validate that marker functionality belongs to its referenced IDs."""
    allowed = frozenset(item for requirement in requirements for item in requirement.functionality)
    unknown = set(test.functionality) - allowed
    if unknown:
        values = ", ".join(sorted(unknown))
        findings.append(_test_finding("TRACE_FUNCTIONALITY_UNKNOWN", f"undeclared functionality: {values}", test))
    for requirement in requirements:
        if not set(test.functionality) & set(requirement.functionality):
            message = f"test names no functionality belonging to {requirement.identifier}"
            findings.append(_test_finding("TRACE_FUNCTIONALITY_MISSING", message, test))


def _record_coverage(
    test: TestEvidence,
    requirements: Sequence[Requirement],
    coverage: dict[str, list[TestEvidence]],
) -> None:
    """Record one test against each active requirement it references."""
    for requirement in requirements:
        coverage.setdefault(requirement.identifier, []).append(test)


def _check_test_references(
    test: TestEvidence,
    referenced: Sequence[Requirement | None],
    findings: list[TraceabilityFinding],
) -> None:
    """Reject unknown and inactive requirement references."""
    for identifier, requirement in zip(test.requirement_ids, referenced, strict=True):
        if requirement is None:
            findings.append(_test_finding("TRACE_REQUIREMENT_UNKNOWN", f"unknown requirement ID {identifier}", test))
        elif requirement.status != "active":
            message = f"requirement {identifier} is {requirement.status} and cannot receive test evidence"
            findings.append(_test_finding("TRACE_REQUIREMENT_INACTIVE", message, test))


def _check_active_requirements(
    requirements: Mapping[str, Requirement],
    coverage: Mapping[str, Sequence[TestEvidence]],
    findings: list[TraceabilityFinding],
) -> None:
    """Require test, classification, and functionality evidence for active IDs."""
    for requirement in requirements.values():
        if requirement.status != "active":
            continue
        tests = tuple(coverage.get(requirement.identifier, ()))
        if not tests:
            message = f"active requirement {requirement.identifier} has no tests"
            findings.append(_requirement_finding("TRACE_REQUIREMENT_UNTESTED", message, requirement))
            continue
        observed_types = {test.test_type for test in tests}
        for missing_type in set(requirement.required_test_types) - observed_types:
            message = f"requirement {requirement.identifier} lacks required {missing_type!r} test evidence"
            findings.append(_requirement_finding("TRACE_TEST_TYPE_MISSING", message, requirement))
        observed_functionality = {item for test in tests for item in test.functionality}
        for missing_functionality in set(requirement.functionality) - observed_functionality:
            message = f"requirement {requirement.identifier} lacks evidence for {missing_functionality!r}"
            findings.append(_requirement_finding("TRACE_FUNCTIONALITY_UNTESTED", message, requirement))


def _requirement_records(
    requirements: Mapping[str, Requirement],
    coverage: Mapping[str, Sequence[TestEvidence]],
) -> tuple[dict[str, object], ...]:
    """Build normalized requirement evidence records."""
    records: list[dict[str, object]] = []
    for identifier, requirement in sorted(requirements.items()):
        records.append(
            {
                "id": identifier,
                "status": requirement.status,
                "registry": requirement.registry,
                "functionality": list(requirement.functionality),
                "required_test_types": list(requirement.required_test_types),
                "tests": [test.node_id for test in coverage.get(identifier, ())],
            }
        )
    return tuple(records)


def _test_record(test: TestEvidence) -> dict[str, object]:
    """Build one normalized test evidence record."""
    return {
        "id": test.node_id,
        "path": test.path,
        "line": test.line,
        "requirements": list(test.requirement_ids),
        "functionality": list(test.functionality),
        "test_type": test.test_type,
    }


def _test_nodes(tree: ast.Module) -> tuple[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef], ...]:
    """Return test definitions pytest can collect by standard naming rules."""
    nodes: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, function_types) and node.name.startswith("test"):
            nodes.append((node.name, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            nodes.extend(
                (f"{node.name}::{item.name}", item) for item in node.body if isinstance(item, function_types) and item.name.startswith("test")
            )
    return tuple(nodes)


def _is_requirement_marker(node: ast.expr) -> bool:
    """Return whether an expression is a direct pytest requirement marker."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "requirement"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "mark"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "pytest"
    )


def _marker_keywords(marker: ast.Call) -> dict[str, ast.expr]:
    """Index explicit marker keyword arguments."""
    keywords: dict[str, ast.expr] = {}
    for keyword in marker.keywords:
        if keyword.arg is None or keyword.arg in keywords:
            message = "marker keywords must be explicit and unique"
            raise ValueError(message)
        keywords[keyword.arg] = keyword.value
    return keywords


def _literal_strings(node: ast.expr, name: str) -> tuple[str, ...]:
    """Read one string or a non-empty tuple/list of strings from an AST node."""
    if isinstance(node, ast.Constant):
        return (_literal_string(node, name),)
    if not isinstance(node, (ast.Tuple, ast.List)) or not node.elts:
        message = f"{name} must be a string or non-empty string sequence"
        raise ValueError(message)
    values = tuple(_literal_string(item, name) for item in node.elts)
    if len(values) != len(set(values)):
        message = f"{name} values must be unique"
        raise ValueError(message)
    return values


def _literal_string(node: ast.expr, name: str) -> str:
    """Read one non-empty string literal from an AST node."""
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not node.value:
        message = f"{name} must be a non-empty string literal"
        raise ValueError(message)
    return node.value


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """Require a string-keyed mapping."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        message = f"{name} must be a string-keyed mapping"
        raise TypeError(message)
    return cast("Mapping[str, object]", value)


def _sequence(value: object, name: str) -> Sequence[object]:
    """Require a non-string sequence."""
    if not isinstance(value, list):
        message = f"{name} must be a sequence"
        raise TypeError(message)
    return cast("Sequence[object]", value)


def _strings(value: object, name: str) -> tuple[str, ...]:
    """Require a duplicate-free sequence of strings."""
    values = _sequence(value, name)
    if not all(isinstance(item, str) and item for item in values):
        message = f"{name} must contain non-empty strings"
        raise TypeError(message)
    strings = cast("tuple[str, ...]", tuple(values))
    if len(strings) != len(set(strings)):
        message = f"{name} values must be unique"
        raise ValueError(message)
    return strings


def _string(value: object, name: str) -> str:
    """Require a non-empty string."""
    if not isinstance(value, str) or not value:
        message = f"{name} must be a non-empty string"
        raise TypeError(message)
    return value


def _integer(value: object, name: str) -> int:
    """Require a positive integer that is not a Boolean."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message = f"{name} must be a positive integer"
        raise TypeError(message)
    return value


def _requirement_number(identifier: str, prefix: str) -> int:
    """Extract the positive numeric suffix from a requirement ID."""
    suffix = identifier.removeprefix(f"{prefix}-")
    if not suffix.isdigit() or int(suffix) < 1:
        message = f"requirement ID {identifier!r} must end in a positive number"
        raise ValueError(message)
    return int(suffix)


def _registry_paths(root: Path) -> tuple[Path, ...]:
    """Discover canonical requirement registries."""
    return tuple(sorted(root.glob("docs/**/*.requirements.yaml")))


def _test_paths(root: Path) -> tuple[Path, ...]:
    """Discover Python test modules."""
    return tuple(sorted(root.glob("tests/**/test_*.py")))


def _read_text(path: Path) -> str:
    """Read UTF-8 text at the filesystem boundary."""
    return path.read_text(encoding="utf-8")


def _relative_path(root: Path, path: Path) -> str:
    """Return a portable project-relative path."""
    return path.relative_to(root).as_posix()


def _write_stdout(value: str) -> object:
    """Write text at the process-output boundary."""
    return sys.stdout.write(value)


def _finding(code: str, message: str, path: str, line: int | None = None) -> TraceabilityFinding:
    """Create an error finding at an optional source line."""
    return TraceabilityFinding(code, message, SourceLocation(path, line))


def _test_finding(code: str, message: str, test: TestEvidence) -> TraceabilityFinding:
    """Create a finding located at a test definition."""
    return _finding(code, message, test.path, test.line)


def _requirement_finding(code: str, message: str, requirement: Requirement) -> TraceabilityFinding:
    """Create a finding located at a requirement registry."""
    return _finding(code, message, requirement.registry, requirement.line)


def _finding_sort_key(finding: TraceabilityFinding) -> tuple[str, int, str, str]:
    """Return a deterministic finding order key."""
    return finding.location.path, finding.location.line or 0, finding.code, finding.message


def _reason_record(finding: TraceabilityFinding) -> dict[str, object]:
    """Convert a traceability finding into a standard failure reason."""
    location: dict[str, object] = {"path": finding.location.path}
    if finding.location.line is not None:
        location["line"] = finding.location.line
    return reason(finding.message, code=finding.code, location=location)


check_requirements = make_checker()
main = make_main()
