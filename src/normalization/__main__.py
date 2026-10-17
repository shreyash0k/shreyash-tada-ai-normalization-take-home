"""Local entry point.

``normalize --entity company``, ``--entity employee``, ``--entity
direct-deposit``, ``--entity deduction`` and ``--entity payroll`` read a
capture bundle (see ``bundle.py``) and write a ``NormalizedOutput`` document
described by ``docs/canonical/normalized-output.schema.json``. ``normalize-company``
reads a folder holding all five bundles of one company and writes one linked
document (see ``company_document.py``).
"""
import argparse
import json
import sys
from pathlib import Path

from .adapters import ADAPTERS, ENTITIES
from .bundle import BUNDLE_ENTITIES, parse_bundle
from .canonical import IssueCode, NormalizedOutput
from .company_document import build_document, load_company_bundles
from .references import all_readiness_issues, load_reference, readiness_issues


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tada AI normalization starter")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-providers")
    commands.add_parser("check-inputs")
    run = commands.add_parser("normalize")
    run.add_argument("--provider", choices=ADAPTERS, required=True)
    run.add_argument("--entity", choices=ENTITIES, required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    whole = commands.add_parser("normalize-company")
    whole.add_argument("--input", type=Path, required=True, help="folder holding the five <entity>-bundle.json files")
    whole.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "list-providers":
        print("\n".join(ADAPTERS))
        return 0
    if args.command == "check-inputs":
        issues = all_readiness_issues()
        print(json.dumps(issues, indent=2))
        return 2 if any(issues.values()) else 0
    if args.command == "normalize-company":
        return _normalize_company(args.input, args.output)
    issues = readiness_issues(args.provider)
    if issues:
        print(json.dumps({"provider": args.provider, "readiness_issues": issues}, indent=2), file=sys.stderr)
        return 2
    try:
        with args.input.open(encoding="utf-8") as stream:
            response = json.load(stream)
        if args.entity in BUNDLE_ENTITIES:
            response = parse_bundle(response, source_path=str(args.input), entity=args.entity)
            if response.provider != args.provider:
                raise ValueError(f"bundle provider is {response.provider!r}, but --provider is {args.provider!r}")
        result = ADAPTERS[args.provider].normalize(args.entity, response, load_reference(args.provider))
        if isinstance(result, NormalizedOutput):
            if args.entity == "company":
                company = result.company
                counted = (f"1 company, {len(company.work_locations)} work locations, "
                           f"{len(company.pay_groups)} pay groups, {len(company.tax_ids)} tax ids")
            elif args.entity == "direct-deposit":
                counted = f"{len(result.direct_deposits)} direct deposits"
            elif args.entity == "deduction":
                counted = f"{len(result.deductions)} deductions"
            elif args.entity == "payroll":
                counted = f"{len(result.pay_runs)} pay runs, {len(result.paychecks)} paychecks"
            else:
                counted = f"{len(result.employees)} employees"
            summary = f"{counted}, {len(result.issues)} issues"
            result = result.to_dict()
        else:
            summary = None
        # Serialize first and refuse overwriting an existing file.
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    except (OSError, ValueError, TypeError, NotImplementedError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if summary:
        print(summary, file=sys.stderr)
    return 0


def _normalize_company(folder: Path, output: Path) -> int:
    try:
        bundles = load_company_bundles(folder)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    provider = bundles["company"].provider
    issues = readiness_issues(provider)
    if issues:
        print(json.dumps({"provider": provider, "readiness_issues": issues}, indent=2), file=sys.stderr)
        return 2
    try:
        document = build_document(bundles)
        serialized = json.dumps(document.to_dict(), indent=2, allow_nan=False) + "\n"
        with output.open("x", encoding="utf-8") as stream:
            stream.write(serialized)
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    broken = sum(1 for issue in document.issues if issue.code is IssueCode.BROKEN_LINK)
    print(f"1 company, {len(document.employees)} employees, {len(document.direct_deposits)} direct deposits, "
          f"{len(document.deductions)} deductions, {len(document.pay_runs)} pay runs, "
          f"{len(document.paychecks)} paychecks, {broken} broken links, {len(document.issues)} issues",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
