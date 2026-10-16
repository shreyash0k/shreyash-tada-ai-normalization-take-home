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
"""
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

BUNDLE_VERSION = 1


@dataclass(frozen=True, slots=True)
class ResponseSpec:
    """What one provider's ``responses`` object must and may contain."""

    request_keys: tuple[str, ...]
    required: dict[str, type]
    optional: dict[str, type]


# Keys are the endpoint names used inside ``responses``. Values are the JSON
# container type the adapter expects for that key.
PROVIDER_SPECS: dict[str, ResponseSpec] = {
    "prismhr": ResponseSpec(
        request_keys=("client_id",),
        # getEmployee returns at most 20 employees per call, so a company is a
        # list of responses, each holding `employee[]`.
        required={"get_employee": list},
        # Maps of employeeId -> response.
        optional={"get_employee_list": dict, "get_address_info": dict},
    ),
    "isolved": ResponseSpec(
        request_keys=("client_id", "legal_id"),
        # One paged response per page, each holding `results[]`.
        required={"employees": list},
        # Maps of employee id (string) -> response.
        optional={"employee_detail": dict, "personal": dict, "name_address": dict},
    ),
    "ukg-ready": ResponseSpec(
        request_keys=("company_id",),
        required={
            "employees": dict,  # the list response: {"employees": [...]}
            "employee": dict,  # account id -> detail response
            "demographics": dict,  # account id -> demographics response
            "pay_info": dict,  # account id -> pay-info response
            "compensation_history": dict,  # account id -> {"compensations": [...]}
            "lookup_employee_types": dict,
            "lookup_pay_types": dict,
            "lookup_eins": dict,
        },
        optional={},
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


def parse_bundle(data: Any, source_path: str | None = None) -> Bundle:
    """Validate raw JSON data and return a ``Bundle``. Raises ValueError with the offending path."""
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
    for key, container in spec.required.items():
        _expect(key in responses, f"responses.{key} is required for {provider}")
        _expect(isinstance(responses[key], container),
                f"responses.{key} must be a JSON {container.__name__}")
    for key, container in spec.optional.items():
        if key in responses:
            _expect(isinstance(responses[key], container),
                    f"responses.{key} must be a JSON {container.__name__}")
    unknown = sorted(set(responses) - set(spec.required) - set(spec.optional))
    _expect(not unknown, f"responses has unknown keys for {provider}: {unknown}")

    return Bundle(provider=provider, captured_at=captured_at, request=dict(request),
                  responses=responses, source_path=source_path)


def load_bundle(path: Path) -> Bundle:
    with Path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    return parse_bundle(data, source_path=str(path))
