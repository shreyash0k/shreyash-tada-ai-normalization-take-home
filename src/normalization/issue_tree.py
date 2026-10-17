"""Places each normalization issue under its provider, client and employee for the web issues page.

Record keys look like ``provider:client``, ``provider:client:run|pg:id``,
``provider:client:employee`` or ``provider:client:employee:dd|ded|chk:id``.
An issue without a key belongs to the provider as a whole.
"""
import re
from dataclasses import dataclass
from typing import Optional

ENTITIES = ("company", "employee", "direct-deposit", "deduction", "payroll")
COMPANY_RECORDS = ("run", "pg")
EMPLOYEE_RECORDS = ("dd", "ded", "chk")


class IssueTreeError(ValueError):
    pass


@dataclass(frozen=True)
class Place:
    company: Optional[str]
    employee: Optional[str]
    record: Optional[str]
    record_id: Optional[str]


def parse_key(provider: str, key: Optional[str]) -> Place:
    if key is None:
        return Place(None, None, None, None)
    parts = key.split(":")
    if parts[0] != provider:
        raise IssueTreeError(f"{provider}: record key {key!r} names another provider")
    if all(parts):
        if len(parts) == 2:
            return Place(parts[1], None, "company", None)
        if len(parts) == 3 and parts[2] not in COMPANY_RECORDS:
            return Place(parts[1], parts[2], "employee", None)
        if len(parts) == 4 and parts[2] in COMPANY_RECORDS:
            return Place(parts[1], None, parts[2], parts[3])
        if len(parts) == 5 and parts[3] in EMPLOYEE_RECORDS:
            return Place(parts[1], parts[2], parts[3], parts[4])
    raise IssueTreeError(f"{provider}: cannot place record key {key!r}")


_EXPECTED = (
    ("value is not a YYYY-MM-DD date or ISO 8601 date-time", "YYYY-MM-DD"),
    ("label is not on the documented allowlist", "allowlist"),
    ("has no documented values and this label is not on the allowlist", "allowlist"),
    ("code has no documented meaning", "documented code"),
    ("value is not one of the documented codes", "documented code"),
    ("is not one of the labels seen live", "label seen live"),
    ("must be a boolean, T or F", "boolean, T or F"),
    ("must be a boolean", "boolean"),
    ("provider returned a masked value", "unmasked value"),
    ("hours must be a number of milliseconds", "milliseconds"),
    ("schema minimum is 1", ">= 1"),
    ("identifier has fewer than four digits", ">= 4 digits"),
)

# What a missing bundle section was supposed to contain. The field name is already shown.
_BUNDLE_ENTRY = {
    "pay_items": "deduction lines",
    "checks": "paychecks",
    "check_detail": "check detail",
    "direct_deposits": "direct deposits",
    "get_deductions": "deductions",
    "deduction_detail": "deduction detail",
    "deductions": "deductions",
    "demographics": "demographics",
    "tax_info": "tax info",
    "pay_statements": "pay statements",
    "pay_statement_detail": "pay statement detail",
}


def expected_text(message: Optional[str]) -> Optional[str]:
    """The constraint in an issue message, without the field prefix or the spec citation."""
    if not message:
        return None
    text = message.split(" (contracts/", 1)[0].strip()
    prefixed = re.match(r"^([\w.]+): (.+)$", text)
    if prefixed:
        text = prefixed.group(2)
    for needle, short in _EXPECTED:
        if needle in text:
            return short
    named = re.search(r"names (?:the array )?'([^']+)'", text)
    if named:
        return named.group(1)
    missing = re.match(r"bundle has no responses\.(\w+)\['[^']+'\] entry", text)
    if missing:
        return _BUNDLE_ENTRY.get(missing.group(1), f"{missing.group(1)} entry")
    return text


def build_provider(provider: str, name: str, outputs: dict) -> dict:
    """``outputs`` maps every name in ``ENTITIES`` to the provider's normalized output."""
    companies = {}

    def company(company_id):
        if company_id not in companies:
            companies[company_id] = {"id": company_id, "key": f"{provider}:{company_id}",
                                     "name": f"Client {company_id}", "issues": [],
                                     "unknown_employees": {}, "employees": {}}
        return companies[company_id]

    profile = outputs["company"]["company"]
    profile_name = profile["legal_name"] or profile["name"]
    node = company(parse_key(provider, profile["key"]).company)
    if profile_name:
        node["name"] = profile_name

    for employee in outputs["employee"]["employees"]:
        place = parse_key(provider, employee["key"])
        if place.record != "employee":
            raise IssueTreeError(f"{provider}: employee key {employee['key']!r} is not an employee key")
        person = employee["person"]
        full_name = " ".join(part for part in (person["first_name"], person["last_name"]) if part)
        company(place.company)["employees"][place.employee] = {
            "key": employee["key"], "id": place.employee, "name": full_name or place.employee, "issues": []}

    provider_issues = []
    for entity in ENTITIES:
        for issue in outputs[entity]["issues"]:
            place = parse_key(provider, issue["record_key"])
            shown = {"code": issue["code"], "severity": issue["severity"], "source_path": issue["source_path"],
                     "raw_value": issue["raw_value"], "action": issue["action"],
                     "expected": expected_text(issue.get("message")),
                     "record": place.record, "record_id": place.record_id}
            if place.company is None:
                provider_issues.append(shown)
            elif place.employee is None:
                company(place.company)["issues"].append(shown)
            else:
                node = company(place.company)
                person = node["employees"].get(place.employee) or node["unknown_employees"].setdefault(
                    place.employee, {"key": f"{provider}:{place.company}:{place.employee}",
                                     "id": place.employee, "issues": []})
                person["issues"].append(shown)

    return {
        "id": provider,
        "name": name,
        "issues": provider_issues,
        "companies": [
            {**node,
             "unknown_employees": [node["unknown_employees"][key] for key in sorted(node["unknown_employees"])],
             "employees": list(node["employees"].values())}
            for _, node in sorted(companies.items())
        ],
    }
