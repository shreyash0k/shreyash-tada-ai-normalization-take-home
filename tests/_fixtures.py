"""Shared loaders for the committed synthetic fixtures."""
import json
from pathlib import Path

from normalization.bundle import load_bundle

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
SCHEMA_PATH = TESTS.parent / "docs" / "canonical" / "employee.schema.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def bundle_path(provider: str) -> Path:
    return FIXTURES / provider / "employee-bundle.json"


def expected_path(provider: str) -> Path:
    return FIXTURES / "expected" / f"{provider}-employees.json"


def fixture_bundle(provider: str):
    return load_bundle(bundle_path(provider))


def raw_bundle(provider: str) -> dict:
    return load_json(bundle_path(provider))


def expected_output(provider: str) -> dict:
    return load_json(expected_path(provider))


def schema() -> dict:
    return load_json(SCHEMA_PATH)


def issues_with(output: dict, code: str, path_contains: str = None) -> list:
    return [issue for issue in output["issues"]
            if issue["code"] == code and (path_contains is None or path_contains in issue["source_path"])]


def employee_by_source_id(output: dict, employee_id: str) -> dict:
    for employee in output["employees"]:
        if employee["source"]["employee_id"] == employee_id:
            return employee
    raise KeyError(employee_id)
