"""One linked document per company.

``normalize-company`` reads the five capture bundles of one company from a
folder, normalizes each data type, and merges the results into a single
``NormalizedOutput``: the full company record and every record list. Each
key a record holds (``company_key``, ``employee_key``, ``pay_run_key``) is
then checked against the records in that document, and a key that does not
resolve becomes a ``broken_link`` issue.
"""
import dataclasses
import json
from pathlib import Path

from .adapters import ADAPTERS
from .bundle import BUNDLE_ENTITIES, Bundle, load_bundle
from .canonical import Issue, IssueCode, NormalizedOutput, Severity
from .references import load_reference

BUNDLE_FILES = {entity: f"{entity}-bundle.json" for entity in BUNDLE_ENTITIES}


def load_company_bundles(folder: Path) -> dict[str, Bundle]:
    """The five bundles of one company, keyed by data type. Raises ValueError when they do not fit together."""
    folder = Path(folder)
    missing = [name for name in BUNDLE_FILES.values() if not (folder / name).is_file()]
    if missing:
        raise ValueError(f"{folder} is missing {', '.join(missing)}")
    bundles = {entity: load_bundle(folder / name, entity=entity) for entity, name in BUNDLE_FILES.items()}
    first = bundles["company"]
    for entity, bundle in bundles.items():
        name = BUNDLE_FILES[entity]
        if bundle.provider != first.provider:
            raise ValueError(f"{name} is for provider {bundle.provider!r}, but "
                             f"{BUNDLE_FILES['company']} is for {first.provider!r}")
        if bundle.request != first.request:
            raise ValueError(f"{name} is for company {bundle.request}, but "
                             f"{BUNDLE_FILES['company']} is for {first.request}")
    return bundles


def build_document(bundles: dict[str, Bundle]) -> NormalizedOutput:
    provider = bundles["company"].provider
    adapter, reference = ADAPTERS[provider], load_reference(provider)
    outputs = [adapter.normalize(entity, bundles[entity], reference) for entity in BUNDLE_ENTITIES]
    by_entity = dict(zip(BUNDLE_ENTITIES, outputs))
    issues, seen = [], set()
    for output in outputs:
        for issue in output.issues:
            marker = json.dumps(issue.to_dict(), sort_keys=True)
            if marker not in seen:
                seen.add(marker)
                issues.append(issue)
    document = NormalizedOutput(
        provider=provider,
        company=by_entity["company"].company,
        employees=by_entity["employee"].employees,
        direct_deposits=by_entity["direct-deposit"].direct_deposits,
        deductions=by_entity["deduction"].deductions,
        pay_runs=by_entity["payroll"].pay_runs,
        paychecks=by_entity["payroll"].paychecks,
        issues=issues,
    )
    return dataclasses.replace(document, issues=issues + link_issues(document))


def link_issues(document: NormalizedOutput) -> list[Issue]:
    """One ``broken_link`` warning per key that names no record in ``document``."""
    company_key = document.company.key
    employee_keys = {employee.key for employee in document.employees}
    run_keys = {run.key for run in document.pay_runs}
    found: list[Issue] = []

    def check(record, field: str, known) -> None:
        target = getattr(record, field)
        if target is not None and target not in known:
            found.append(Issue(IssueCode.BROKEN_LINK, Severity.WARNING, field, "record kept", record.key, target,
                               f"{field} names a record that is not in this document"))

    for employee in document.employees:
        check(employee, "company_key", {company_key})
    for run in document.pay_runs:
        check(run, "company_key", {company_key})
    for records in (document.direct_deposits, document.deductions, document.paychecks):
        for record in records:
            check(record, "company_key", {company_key})
            check(record, "employee_key", employee_keys)
    for paycheck in document.paychecks:
        check(paycheck, "pay_run_key", run_keys)
    return found
