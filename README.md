# Payroll data normalization: PrismHR, isolved, and UKG Ready

This project reads company, employee, direct deposit, deduction, and payroll data
from three payroll providers (PrismHR, isolved, and UKG Ready) and converts it
into one canonical model. A record looks the same in that model no matter which
provider it came from, and records stay linked: employees to companies,
paychecks to employees.

The assignment is in [docs/ASSIGNMENT.md](docs/ASSIGNMENT.md).
Every assumption and decision is recorded in [docs/DECISIONS.md](docs/DECISIONS.md).

## Status

Implemented: **employee** normalization for all three providers (profile and
contact, status and dates, job and organization, current compensation), with a
minimal company stub so employee-to-company links resolve. Also implemented:
**direct deposit** normalization for all three providers, one record per bank
line, linked to its employee by `employee_key` (bank, routing number, last four
account digits, account type, allocation, priority, status, effective dates).
Each provider has seeded synthetic fixtures, a golden expected output, and
edge-case tests for both data types.

A local web app shows how each provider's employee and direct deposit fields
map into the canonical model: mapped, not mapped yet, or not offered (see
[Field coverage page](#field-coverage-page)).

Not implemented yet: company detail, deductions, payroll, the
optional write path, and grouped issue reporting. `normalize --entity company`
and `--entity payroll` still exit 1 with "not implemented". Known gaps in the
starter are tracked in
[docs/DECISIONS.md](docs/DECISIONS.md#starter-code-issues).

## Approach

- **Capture bundles as input.** One employee's data spans several endpoints,
  and some identifiers (PrismHR's `clientId`) exist only in the request. The
  adapter input is therefore one JSON "bundle" per provider and company:
  `{"bundle_version": 1, "provider", "captured_at", "request": {...},
  "responses": {<endpoint>: <raw response or map of responses>}}`.
  `src/normalization/bundle.py` lists the required and optional response keys
  per provider and data type, so one bundle can hold the calls for both
  employees and direct deposits; the fixtures under `tests/fixtures/` are
  complete examples.
- **Direct deposits are their own records.** They sit in a top-level
  `direct_deposits[]` list rather than inside the employee, each carrying the
  `employee_key` and `company_key` it belongs to.
- **One adapter per provider.** Each adapter turns a bundle into canonical
  records. Everything provider-specific stays inside its adapter, and every
  code table cites the spec path it rests on.
- **Coded values keep the raw code.** Every coded field is
  `{"raw", "label", "value"}`: the provider's code, its provider-side
  description when one exists, and the canonical enum member. A raw value maps
  to a canonical value only when the spec documents the meaning, the value is a
  member of a self-describing schema enum, or it matches a short, recorded
  allowlist of live-observed labels exactly. Otherwise `value` is `unknown`.
- **Nothing is dropped.** Provider fields with no canonical home are passed
  through in each record's `unmapped`, keyed by their source JSON path. SSNs
  and bank account numbers are reduced to their last four digits and redacted
  everywhere else, as are tokens inside provider links.
- **Report problems instead of guessing.** Undocumented codes, invalid values,
  missing sections, and spec/live mismatches become structured issues with a
  code, severity, source path, and the action taken.
- **Standard library only.** The canonical model is frozen dataclasses with
  strict type checks; the output shape is documented in
  [docs/canonical/employee.schema.json](docs/canonical/employee.schema.json)
  and validated in tests with a small built-in validator.
- **Deterministic, offline tests.** Fixtures are generated from a fixed seed and
  committed; a test asserts regeneration is byte-identical.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/normalization/__main__.py` | Command-line entry point |
| `src/normalization/bundle.py` | Capture-bundle envelope and per-provider shape checks |
| `src/normalization/canonical/` | Canonical model (employee, direct deposit, enums, issues) and the schema validator |
| `src/normalization/adapters/` | One adapter per provider plus shared helpers (`_common.py`) |
| `src/normalization/references.py` | Reference-pack readiness checks |
| `src/normalization/field_map.py` | Per-provider source and status of each canonical employee field |
| `src/normalization/deposit_field_map.py` | Per-provider source and status of each canonical direct deposit field |
| `scripts/generate_fixtures.py` | Seeded fixture generator |
| `scripts/export_web_data.py` | Writes the coverage data the web pages read |
| `web/` | Next.js field coverage pages (static export) |
| `web/public/logos/` | Provider logos used by the coverage page |
| `tests/` | Unit tests; `tests/fixtures/<provider>/` holds the employee and direct-deposit bundles, `tests/fixtures/expected/` the expected outputs |
| `docs/canonical/` | JSON Schema for the normalized output |
| `contracts/` | Provider API specifications and lookup references, as supplied |
| `docs/` | Assignment, decisions, and the reference audit |

## Setup

Developed and tested with Python 3.14. No third-party packages are needed.

```sh
git clone https://github.com/shreyash0k/shreyash-tada-ai-normalization-take-home.git
cd shreyash-tada-ai-normalization-take-home
```

The optional field coverage page also needs Node.js 24 (`web/.nvmrc`).

## Running

Run the tests:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

Command-line usage:

```sh
# List supported providers
PYTHONPATH=src python3 -m normalization list-providers

# Check each provider's reference pack (exits 2 if any issues are found)
PYTHONPATH=src python3 -m normalization check-inputs

# Normalize one capture bundle into a new output file
PYTHONPATH=src python3 -m normalization normalize \
  --provider prismhr --entity employee \
  --input tests/fixtures/prismhr/employee-bundle.json --output out/result.json

# Normalize direct deposits from a direct-deposit bundle
PYTHONPATH=src python3 -m normalization normalize \
  --provider ukg-ready --entity direct-deposit \
  --input tests/fixtures/ukg-ready/direct-deposit-bundle.json --output out/deposits.json
```

For `--entity employee` and `--entity direct-deposit` the input must be a
capture bundle whose `provider` matches `--provider` and that holds the
responses that data type needs. On success a summary such as
`7 employees, 16 issues` or `10 direct deposits, 6 issues` is printed to
stderr. The output is a `NormalizedOutput` document (`provider`, `company`,
`employees[]`, `direct_deposits[]`, `issues[]`, `schema_version`) described by
[docs/canonical/employee.schema.json](docs/canonical/employee.schema.json);
only the list for the requested data type is filled.

`normalize` will not overwrite an existing output file. Exit codes: 0 means
success, 1 means the input could not be read or normalized (including an
invalid bundle, a bundle missing the responses the requested data type needs,
or an entity that is not implemented), and 2 means the
reference pack or the command-line arguments are not usable.

Regenerate or verify the synthetic fixtures:

```sh
python3 scripts/generate_fixtures.py          # rewrite tests/fixtures/**
python3 scripts/generate_fixtures.py --check  # exit 1 if the committed files differ
```

## Field coverage page

Two pages, linked from a nav at the top, list every canonical field against
PrismHR, isolved and UKG Ready: employee fields at `/` and direct deposit
fields at `/direct-deposits`. Each cell is one of three states: mapped, not
mapped yet, or not offered. A mapped cell shows the provider field it comes
from. Hovering a state or a cell shows what the state means, the full source
path, and the spec entry it rests on. The data comes from
`src/normalization/field_map.py` and `src/normalization/deposit_field_map.py`
and holds statuses, source paths and evidence, never provider values. The
logos in `web/public/logos/` are trademarks of their owners.

```sh
python3 scripts/export_web_data.py          # rewrite web/src/data/coverage.json
python3 scripts/export_web_data.py --check  # exit 1 if the committed file is out of date

cd web
npm install
npm run dev     # http://localhost:3000
npm test        # unit tests for statuses and labels
npm run lint    # ESLint
npm run build   # static site in web/out/
```

The Python tests fail if either field map or the committed `coverage.json`
falls out of step. Each field map is checked against its golden outputs. After
changing a field map, re-run the export. After changing an adapter,
regenerate the fixtures with `scripts/generate_fixtures.py` first, since that
check reads the golden outputs.

## Live demo data (optional)

Live provider data is used only to check mapping assumptions. Tests never depend
on it. To explore it, put the organizer-supplied key in `.env` as
`DEMO_SIGNIN_API_KEY` and follow the sign-in steps in
[docs/ASSIGNMENT.md](docs/ASSIGNMENT.md#access-live-demo-data). Both `.env` and
`out/` are ignored by Git, so tokens and downloaded records stay local.
