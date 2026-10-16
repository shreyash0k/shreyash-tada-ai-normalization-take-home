"""Shared loaders for the committed synthetic fixtures."""
import functools
import json
from pathlib import Path

from normalization.bundle import load_bundle

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
FIXTURES = TESTS / "fixtures"
SCHEMA_PATH = TESTS.parent / "docs" / "canonical" / "employee.schema.json"


def load_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


PROVIDERS = ("prismhr", "isolved", "ukg-ready")
ENTITIES = ("employee", "direct-deposit", "deduction", "payroll")
_GOLDEN_SUFFIX = {"employee": "employees", "direct-deposit": "direct-deposits", "deduction": "deductions",
                  "payroll": "payroll"}


def bundle_path(provider: str, entity: str = "employee") -> Path:
    return FIXTURES / provider / f"{entity}-bundle.json"


def expected_path(provider: str, entity: str = "employee") -> Path:
    return FIXTURES / "expected" / f"{provider}-{_GOLDEN_SUFFIX[entity]}.json"


def fixture_bundle(provider: str, entity: str = "employee"):
    return load_bundle(bundle_path(provider, entity), entity=entity)


def raw_bundle(provider: str, entity: str = "employee") -> dict:
    return load_json(bundle_path(provider, entity))


def expected_output(provider: str, entity: str = "employee") -> dict:
    return load_json(expected_path(provider, entity))


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


def deposits_of(output: dict, employee_id: str) -> list:
    return [d for d in output["direct_deposits"] if d["source"]["employee_id"] == employee_id]


def deposit_by_id(output: dict, deposit_id: str) -> dict:
    for deposit in output["direct_deposits"]:
        if deposit["source"]["deposit_id"] == deposit_id:
            return deposit
    raise KeyError(deposit_id)


def deductions_of(output: dict, employee_id: str) -> list:
    return [d for d in output["deductions"] if d["source"]["employee_id"] == employee_id]


def deduction_by_key(output: dict, key: str) -> dict:
    for record in output["deductions"]:
        if record["key"] == key:
            return record
    raise KeyError(key)


@functools.lru_cache(maxsize=None)
def _cached_json(path: str):
    return load_json(Path(path))


def resolve_code_table(table):
    """Resolve the pointer a ``CodeTable`` cites (its evidence text up to the first space)."""
    return resolve_evidence(table.evidence.split(" ", 1)[0])


def resolve_evidence(evidence: str):
    """Follow ``<file>#<JSON pointer>`` into a JSON file under the repository root."""
    path, pointer = evidence.split("#", 1)
    node = _cached_json(str(ROOT / path))
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[int(token)] if isinstance(node, list) else node[token]
    return node
