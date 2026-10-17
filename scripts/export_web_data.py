"""Export the field coverage into ``web/src/data/coverage.json`` and the issue tree into ``web/src/data/issues.json``.

Usage::

    python scripts/export_web_data.py          # write both files
    python scripts/export_web_data.py --check  # exit 1 if either committed file is out of date

``coverage.json`` holds statuses, source paths and evidence only, never
provider values. ``issues.json`` holds the issues from the golden outputs,
with synthetic employee and company names and the already-redacted raw
values. The web app needs neither Python nor the fixtures.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from normalization import (  # noqa: E402
    company_field_map,
    deduction_field_map,
    deposit_field_map,
    field_map,
    payroll_field_map,
)
from normalization.bundle import PROVIDER_SPECS  # noqa: E402
from normalization.field_map import MAPPED, NOT_OFFERED  # noqa: E402
from normalization.issue_tree import ENTITIES, IssueTreeError, build_provider  # noqa: E402

OUTPUT = ROOT / "web" / "src" / "data" / "coverage.json"
ISSUES_OUTPUT = ROOT / "web" / "src" / "data" / "issues.json"
EXPORT_VERSION = 2
ISSUES_EXPORT_VERSION = 1
GOLDEN = ROOT / "tests" / "fixtures" / "expected"
GOLDEN_SUFFIX = {"company": "company", "employee": "employees", "direct-deposit": "direct-deposits",
                 "deduction": "deductions", "payroll": "payroll"}
PROVIDER_NAMES = {"prismhr": "PrismHR", "isolved": "isolved", "ukg-ready": "UKG Ready"}
ENTITY_MAPS = {"employee": field_map, "direct-deposit": deposit_field_map, "deduction": deduction_field_map,
               "payroll": payroll_field_map, "company": company_field_map}


class ExportError(ValueError):
    pass


def provider_coverage(entity: str, provider: str) -> dict:
    module = ENTITY_MAPS[entity]
    entries = module.FIELD_MAP.get(provider, {})
    missing = [field for field in module.canonical_fields() if field not in entries]
    if missing:
        raise ExportError(f"{provider} {entity}: field map has no entry for {', '.join(missing)}")
    rows = []
    for field in module.canonical_fields():
        entry = entries[field]
        rows.append({
            "field": field,
            "section": module.section(field),
            "status": entry.status,
            "source": entry.source,
            "evidence": entry.evidence,
            "reason": entry.reason,
        })
    return {
        "id": provider,
        "name": PROVIDER_NAMES[provider],
        "summary": {
            "fields_total": len(rows),
            "fields_offered": sum(1 for row in rows if row["status"] != NOT_OFFERED),
            "fields_mapped": sum(1 for row in rows if row["status"] == MAPPED),
        },
        "coverage": rows,
    }


def dump(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def render() -> str:
    return dump({
        "export_version": EXPORT_VERSION,
        "entities": {entity: [provider_coverage(entity, provider) for provider in PROVIDER_SPECS]
                     for entity in ENTITY_MAPS},
    })


def load_golden(provider: str, entity: str) -> dict:
    path = GOLDEN / f"{provider}-{GOLDEN_SUFFIX[entity]}.json"
    if not path.exists():
        raise ExportError(f"{provider} {entity}: golden output missing at {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def provider_issue_tree(provider: str) -> dict:
    outputs = {entity: load_golden(provider, entity) for entity in ENTITIES}
    try:
        return build_provider(provider, PROVIDER_NAMES[provider], outputs)
    except IssueTreeError as exc:
        raise ExportError(str(exc)) from exc


def render_issues() -> str:
    return dump({"export_version": ISSUES_EXPORT_VERSION,
                 "providers": [provider_issue_tree(provider) for provider in PROVIDER_SPECS]})


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="compare with the committed files instead of writing")
    args = parser.parse_args(argv)
    try:
        files = {OUTPUT: render(), ISSUES_OUTPUT: render_issues()}
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.check:
        stale = [path for path, content in files.items()
                 if not path.exists() or path.read_text(encoding="utf-8") != content]
        for path in stale:
            print(f"stale export: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
