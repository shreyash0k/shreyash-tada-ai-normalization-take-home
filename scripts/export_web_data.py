"""Export the field coverage the web app shows into ``web/src/data/coverage.json``.

Usage::

    python scripts/export_web_data.py          # write the file
    python scripts/export_web_data.py --check  # exit 1 if the committed file is out of date

The file holds statuses, counts, source paths and evidence only, never
provider values, so the web app needs neither Python nor the fixtures.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from normalization.bundle import PROVIDER_SPECS  # noqa: E402
from normalization.field_map import (  # noqa: E402
    FIELD_MAP, MAPPED, NOT_OFFERED, canonical_fields, is_filled,
)

EXPECTED = ROOT / "tests" / "fixtures" / "expected"
OUTPUT = ROOT / "web" / "src" / "data" / "coverage.json"
EXPORT_VERSION = 1
PROVIDER_NAMES = {"prismhr": "PrismHR", "isolved": "isolved", "ukg-ready": "UKG Ready"}


class ExportError(ValueError):
    pass


def _employees(provider: str) -> list[dict]:
    path = EXPECTED / f"{provider}-employees.json"
    if not path.exists():
        raise ExportError(f"{provider}: golden output {path.relative_to(ROOT)} is missing")
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)["employees"]


def provider_coverage(provider: str) -> dict:
    entries = FIELD_MAP.get(provider, {})
    missing = [field for field in canonical_fields() if field not in entries]
    if missing:
        raise ExportError(f"{provider}: field map has no entry for {', '.join(missing)}")
    employees = _employees(provider)
    rows = []
    for field in canonical_fields():
        entry = entries[field]
        rows.append({
            "field": field,
            "section": field.split(".", 1)[0],
            "status": entry.status,
            "filled": sum(1 for employee in employees if is_filled(employee, field)),
            "total": len(employees),
            "source": entry.source,
            "evidence": entry.evidence,
            "reason": entry.reason,
            "sample_gap": entry.sample_gap,
        })
    return {
        "id": provider,
        "name": PROVIDER_NAMES[provider],
        "summary": {
            "employees": len(employees),
            "fields_total": len(rows),
            "fields_offered": sum(1 for row in rows if row["status"] != NOT_OFFERED),
            "fields_mapped": sum(1 for row in rows if row["status"] == MAPPED),
        },
        "coverage": rows,
    }


def render() -> str:
    data = {
        "export_version": EXPORT_VERSION,
        "providers": [provider_coverage(provider) for provider in PROVIDER_SPECS],
    }
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="compare with the committed file instead of writing")
    args = parser.parse_args(argv)
    try:
        content = render()
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print(f"stale export: {OUTPUT.relative_to(ROOT)}", file=sys.stderr)
            return 1
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
