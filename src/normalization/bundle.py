"""Capture bundles: the input format every adapter reads.

One employee's data spans several provider endpoints, and some identifiers
(PrismHR's ``clientId``) exist only in the request. A bundle keeps the request
context and one raw response per endpoint together in a single JSON document::

    {
      "bundle_version": 1,
      "provider": "ukg-ready",
      "captured_at": "2026-10-15",
      "request": {"company_id": "33704016"},
      "responses": {"employees": {...}, "employee": {"<aid>": {...}}, ...}
    }

Synthetic fixtures and hand-saved live downloads both use this shape, so
tests and live checks run through the same adapter code.

Which responses must be present depends on the entity being normalized
(``employee``, ``direct-deposit``, ``deduction`` or ``payroll``). A bundle may carry
responses for more than one entity, so one capture can feed several runs.
"""
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

BUNDLE_VERSION = 1


BUNDLE_ENTITIES = ("employee", "direct-deposit", "deduction", "payroll")


@dataclass(frozen=True, slots=True)
class ResponseSpec:
    """What one provider's ``responses`` object must and may contain, per entity."""

    request_keys: tuple[str, ...]
    required: dict[str, dict[str, type]]
    optional: dict[str, dict[str, type]]

    def known(self) -> dict[str, type]:
        """Every response key any entity of this provider reads, with its container type."""
        keys: dict[str, type] = {}
        for table in (*self.required.values(), *self.optional.values()):
            keys.update(table)
        return keys


# Keys are the endpoint names used inside ``responses``. Values are the JSON
# container type the adapter expects for that key.
PROVIDER_SPECS: dict[str, ResponseSpec] = {
    "prismhr": ResponseSpec(
        request_keys=("client_id",),
        required={
            # getEmployee returns at most 20 employees per call, so a company is a
            # list of responses, each holding `employee[]`.
            "employee": {"get_employee": list},
            # The same call requested with options=DirectDeposit.
            "direct-deposit": {"get_employee_direct_deposit": list},
            # employeeId -> the getDeductions response.
            "deduction": {"get_deductions": dict},
            # One getBatchListByDate response, and batchId -> the list of
            # getPayrollVoucherForBatch pages.
            "payroll": {"get_batch_list_by_date": dict, "get_payroll_voucher_for_batch": dict},
        },
        optional={
            # Maps of employeeId -> response.
            "employee": {"get_employee_list": dict, "get_address_info": dict},
            "direct-deposit": {},
            # getEmployeeList names the population, so an employee with no
            # getDeductions entry can be reported.
            "deduction": {"get_employee_list": dict},
            # batchId -> getBatchInfo response; adds the batch description.
            "payroll": {"get_batch_info": dict},
        },
    ),
    "isolved": ResponseSpec(
        request_keys=("client_id", "legal_id"),
        required={
            # One paged response per page, each holding `results[]`.
            "employee": {"employees": list},
            # Employee id (string) -> the /directdeposits array. The employee
            # pages supply the population and the legal code.
            "direct-deposit": {"employees": list, "direct_deposits": dict},
            # Employee id (string) -> the /payItems array, 404 saved as [].
            "deduction": {"employees": list, "pay_items": dict},
            # Pay group id -> the payrollRunHistory array, and employee id ->
            # the list of /checks pages.
            "payroll": {"employees": list, "payroll_run_history": dict, "checks": dict},
        },
        optional={
            # Maps of employee id (string) -> response.
            "employee": {"employee_detail": dict, "personal": dict, "name_address": dict},
            "direct-deposit": {},
            "deduction": {},
            # Check id -> the /checks/{id} detail; adds tax lines and benefits.
            "payroll": {"check_detail": dict},
        },
    ),
    "ukg-ready": ResponseSpec(
        request_keys=("company_id",),
        required={
            "employee": {
                "employees": dict,  # the list response: {"employees": [...]}
                "employee": dict,  # account id -> detail response
                "demographics": dict,  # account id -> demographics response
                "pay_info": dict,  # account id -> pay-info response
                "compensation_history": dict,  # account id -> {"compensations": [...]}
                "lookup_employee_types": dict,
                "lookup_pay_types": dict,
                "lookup_eins": dict,
            },
            # Account id -> the /direct-deposits response ({"deposits": [...]}).
            "direct-deposit": {"employees": dict, "direct_deposits": dict},
            # Account id -> the /deductions list response, and deduction id ->
            # the /deductions/{id} detail response.
            "deduction": {"employees": dict, "deductions": dict, "deduction_detail": dict},
            # The /payrolls list response, payroll id -> the /pay-statements
            # list response, and statement id -> the statement detail.
            "payroll": {"payrolls": dict, "pay_statements": dict, "pay_statement_detail": dict},
        },
        optional={
            "employee": {},
            "direct-deposit": {"lookup_eins": dict},
            "deduction": {"lookup_eins": dict},
            "payroll": {"lookup_eins": dict},
        },
    ),
}


@dataclass(frozen=True, slots=True)
class Bundle:
    provider: str
    captured_at: date
    request: dict[str, str]
    responses: dict[str, Any]
    bundle_version: int = BUNDLE_VERSION
    source_path: str | None = field(default=None, compare=False)

    def response(self, name: str, default: Any = None) -> Any:
        return self.responses.get(name, default)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"Invalid bundle: {message}")


def parse_bundle(data: Any, source_path: str | None = None, entity: str = "employee") -> Bundle:
    """Validate raw JSON data for ``entity`` and return a ``Bundle``.

    Raises ValueError with the offending path.
    """
    if entity not in BUNDLE_ENTITIES:
        raise ValueError(f"entity {entity!r} is not read from a capture bundle")
    _expect(isinstance(data, dict), "top level must be an object")
    for key in ("bundle_version", "provider", "captured_at", "request", "responses"):
        _expect(key in data, f"missing key '{key}'")
    _expect(data["bundle_version"] == BUNDLE_VERSION,
            f"bundle_version must be {BUNDLE_VERSION}, got {data['bundle_version']!r}")
    provider = data["provider"]
    _expect(provider in PROVIDER_SPECS, f"unknown provider {provider!r}")
    spec = PROVIDER_SPECS[provider]

    captured = data["captured_at"]
    _expect(isinstance(captured, str), "captured_at must be a YYYY-MM-DD string")
    try:
        captured_at = date.fromisoformat(captured)
    except ValueError as exc:
        raise ValueError(f"Invalid bundle: captured_at {captured!r} is not a date") from exc

    request = data["request"]
    _expect(isinstance(request, dict), "request must be an object")
    for key in spec.request_keys:
        _expect(isinstance(request.get(key), str) and request[key] != "",
                f"request.{key} must be a non-empty string")
    for key, value in request.items():
        _expect(isinstance(value, str), f"request.{key} must be a string")

    responses = data["responses"]
    _expect(isinstance(responses, dict), "responses must be an object")
    for key in spec.required[entity]:
        _expect(key in responses, f"responses.{key} is required for {provider} {entity}")
    known = spec.known()
    for key, container in known.items():
        if key in responses:
            _expect(isinstance(responses[key], container),
                    f"responses.{key} must be a JSON {container.__name__}")
    unknown = sorted(set(responses) - set(known))
    _expect(not unknown, f"responses has unknown keys for {provider}: {unknown}")

    return Bundle(provider=provider, captured_at=captured_at, request=dict(request),
                  responses=responses, source_path=source_path)


def load_bundle(path: Path, entity: str = "employee") -> Bundle:
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    return parse_bundle(data, source_path=str(path), entity=entity)
