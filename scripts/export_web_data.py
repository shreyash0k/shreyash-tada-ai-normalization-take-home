"""Export the employee, direct deposit and deduction field coverage into ``web/src/data/coverage.json``.

Usage::

    python scripts/export_web_data.py          # write the file
    python scripts/export_web_data.py --check  # exit 1 if the committed file is out of date

The file holds statuses, source paths and evidence only, never provider
values, so the web app needs neither Python nor the fixtures.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from normalization import deduction_field_map, deposit_field_map, field_map  # noqa: E402
from normalization.bundle import PROVIDER_SPECS  # noqa: E402
from normalization.field_map import MAPPED, NOT_OFFERED  # noqa: E402

OUTPUT = ROOT / "web" / "src" / "data" / "coverage.json"
EXPORT_VERSION = 2
PROVIDER_NAMES = {"prismhr": "PrismHR", "isolved": "isolved", "ukg-ready": "UKG Ready"}
ENTITY_MAPS = {"employee": field_map, "direct-deposit": deposit_field_map, "deduction": deduction_field_map}


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


def render() -> str:
    data = {
        "export_version": EXPORT_VERSION,
        "entities": {entity: [provider_coverage(entity, provider) for provider in PROVIDER_SPECS]
                     for entity in ENTITY_MAPS},
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
