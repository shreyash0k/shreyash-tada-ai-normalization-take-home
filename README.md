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
And **deduction** normalization for all three providers, one record per
recurring deduction rule, linked the same way (code, category, calculation
method with amount or percent, frequency, limits, employer match, payee,
priority, effective dates). isolved deductions are read from pay items, and
UKG Ready's are built from its reference pages, because neither provider's
deduction call answered for the demo companies.

And **payroll** normalization for all three providers: one record per pay
run (type, status, pay date, period, pay group) and one per employee
paycheck, linked to its run, employee and company by key, with the
provider's gross and net pay and its earning, tax, deduction, employer
contribution and payment lines. isolved payroll is read from legal company
5797, the one with payroll data.

And **company** normalization for all three providers: one company record
with its profile (name, legal name, status, EIN, address, contact details,
industry codes, parent) and three nested lists that employee and payroll
records point at: tax ids, work locations and pay groups. UKG Ready has no
company profile endpoint, so its record holds only the EIN lookup and the
pay-period profiles. The other data types keep a minimal company record with
the same key.

Each provider has seeded synthetic fixtures, a golden expected output, and
edge-case tests for all five data types.

A local web app shows how each provider's employee, direct deposit,
deduction, payroll and company fields map into the canonical model: mapped,
not mapped yet, or not offered (see [Field coverage page](#field-coverage-page)).
It also has an issues page that drills from provider to client to employee
and lists everything normalization flagged on each person (see
[Issues page](#issues-page)).

Not implemented yet: the optional write path and grouped issue reporting.
Known gaps in the starter are tracked in
[docs/DECISIONS.md](docs/DECISIONS.md#starter-code-issues).

## Approach

- **Capture bundles as input.** One employee's data spans several endpoints,
  and some identifiers (PrismHR's `clientId`) exist only in the request. The
  adapter input is therefore one JSON "bundle" per provider and company:
  `{"bundle_version": 1, "provider", "captured_at", "request": {...},
  "responses": {<endpoint>: <raw response or map of responses>}}`.
  `src/normalization/bundle.py` lists the required and optional response keys
  per provider and data type, so one bundle can hold the calls for the
  company, employees, direct deposits, deductions and payroll; the fixtures
  under `tests/fixtures/` are complete examples.
- **Direct deposits, deductions, pay runs and paychecks are their own
  records.** They sit in top-level `direct_deposits[]`, `deductions[]`,
  `pay_runs[]` and `paychecks[]` lists rather than inside the employee, each
  carrying the keys it links by (`employee_key`, `company_key`, and for a
  paycheck `pay_run_key`). Paycheck totals are copied from the provider,
  never summed from the lines. A company's tax ids, work locations and pay
  groups are nested inside its record, each with its own key; employees and
  pay runs reach them through the provider's raw code.
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
| `src/normalization/canonical/` | Canonical model (company with tax ids, work locations and pay groups; employee, direct deposit, deduction, payroll, enums, issues) and the schema validator |
| `src/normalization/adapters/` | One adapter per provider plus shared helpers (`_common.py`) |
| `src/normalization/references.py` | Reference-pack readiness checks |
| `src/normalization/field_map.py` | Per-provider source and status of each canonical employee field |
| `src/normalization/deposit_field_map.py` | Per-provider source and status of each canonical direct deposit field |
| `src/normalization/deduction_field_map.py` | Per-provider source and status of each canonical deduction field |
| `src/normalization/payroll_field_map.py` | Per-provider source and status of each canonical payroll field |
| `src/normalization/company_field_map.py` | Per-provider source and status of each canonical company field |
| `src/normalization/issue_tree.py` | Places each issue under its provider, client and employee for the issues page |
| `scripts/generate_fixtures.py` | Seeded fixture generator |
| `scripts/export_web_data.py` | Writes the coverage and issue data the web pages read |
| `web/` | Next.js field coverage and issues pages (static export) |
| `web/public/logos/` | Provider logos used by the coverage page |
| `tests/` | Unit tests; `tests/fixtures/<provider>/` holds the company, employee, direct-deposit, deduction and payroll bundles, `tests/fixtures/expected/` the expected outputs |
| `docs/canonical/` | JSON Schema for the normalized output |
| `contracts/` | Provider API specifications and lookup references, as supplied |
| `docs/` | Assignment, decisions, and the reference audit |

## Setup

Developed and tested with Python 3.14. No third-party packages are needed.

```sh
git clone https://github.com/shreyash0k/shreyash-tada-ai-normalization-take-home.git
cd shreyash-tada-ai-normalization-take-home
```

The optional web pages also need Node.js 24 (`web/.nvmrc`).

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

# Normalize deductions from a deduction bundle
PYTHONPATH=src python3 -m normalization normalize \
  --provider prismhr --entity deduction \
  --input tests/fixtures/prismhr/deduction-bundle.json --output out/deductions.json

# Normalize pay runs and paychecks from a payroll bundle
PYTHONPATH=src python3 -m normalization normalize \
  --provider ukg-ready --entity payroll \
  --input tests/fixtures/ukg-ready/payroll-bundle.json --output out/payroll.json

# Normalize the full company record from a company bundle
PYTHONPATH=src python3 -m normalization normalize \
  --provider prismhr --entity company \
  --input tests/fixtures/prismhr/company-bundle.json --output out/company.json
```

For every `--entity` the input must be a capture bundle whose `provider`
matches `--provider` and that holds the responses that data type needs. On
success a summary such as `7 employees, 11 issues`, `10 direct deposits, 6
issues`, `11 deductions, 9 issues`, `4 pay runs, 5 paychecks, 12 issues` or
`1 company, 5 work locations, 3 pay groups, 1 tax ids, 2 issues` is printed
to stderr. The output is a `NormalizedOutput` document (`provider`,
`company`, `employees[]`, `direct_deposits[]`, `deductions[]`, `pay_runs[]`,
`paychecks[]`, `issues[]`, `schema_version`) described by
[docs/canonical/employee.schema.json](docs/canonical/employee.schema.json);
only the lists for the requested data type are filled. `--entity company`
fills the whole `company` object; the other data types leave its profile and
nested lists empty and fill only its key, source and, where known, EIN.

`normalize` will not overwrite an existing output file. Exit codes: 0 means
success, 1 means the input could not be read or normalized (including an
invalid bundle or a bundle missing the responses the requested data type
needs), and 2 means the reference pack or the command-line arguments are not
usable.

Regenerate or verify the synthetic fixtures:

```sh
python3 scripts/generate_fixtures.py          # rewrite tests/fixtures/**
python3 scripts/generate_fixtures.py --check  # exit 1 if the committed files differ
```

## Field coverage page

Five pages, linked from a nav at the top, list every canonical field against
PrismHR, isolved and UKG Ready: employee fields at `/`, direct deposit fields
at `/direct-deposits`, deduction fields at `/deductions`, payroll fields at
`/payroll` and company fields at `/company`. Each cell is one of three states:
mapped, not mapped yet, or not offered. A mapped cell shows the provider field
it comes from. Hovering a state or a cell shows what the state means, the full
source path, and the spec entry it rests on. The data comes from
`src/normalization/field_map.py`, `src/normalization/deposit_field_map.py`,
`src/normalization/deduction_field_map.py`,
`src/normalization/payroll_field_map.py` and
`src/normalization/company_field_map.py` and holds statuses, source paths and
evidence, never provider values. The logos in `web/public/logos/` are
trademarks of their owners.

```sh
python3 scripts/export_web_data.py          # rewrite web/src/data/coverage.json and issues.json
python3 scripts/export_web_data.py --check  # exit 1 if either committed file is out of date

cd web
npm install
npm run dev     # http://localhost:3000
npm test        # unit tests for statuses, labels and issue counts
npm run lint    # ESLint
npm run build   # static site in web/out/
```

The Python tests fail if any field map or the committed `coverage.json`
falls out of step. Each field map is checked against its golden outputs. After
changing a field map, re-run the export. After changing an adapter,
regenerate the fixtures with `scripts/generate_fixtures.py` first, since that
check reads the golden outputs.

## Issues page

`/issues` answers one question: can this employee's data be trusted? It
starts with a tile per provider, showing that provider's logo, then a tile
per client, then a tile per employee. Each tile has a badge with the number of issues under it, including
zero. Provider tiles stay in the field-mapping order: PrismHR, isolved,
UKG Ready. Client and employee tiles are ordered by that count. Clicking an employee opens
their issues as four columns: the field, what the provider sent, the
constraint that failed, and the short result (`null`, `unknown`, `unmapped`,
`none`). Issues that belong to no listed employee (provider-wide findings, pay
runs, company records, an employee missing from the employee list) are one
link away under the tiles, and are counted in the badges.

The data is `web/src/data/issues.json`, written by the same export script
from the golden outputs. Unlike `coverage.json`, it holds the synthetic
employee and company names and the already-redacted raw values. After
regenerating the fixtures, re-run the export; the Python tests fail if the
committed file is stale.

## Live demo data (optional)

Live provider data is used only to check mapping assumptions. Tests never depend
on it. To explore it, put the organizer-supplied key in `.env` as
`DEMO_SIGNIN_API_KEY` and follow the sign-in steps in
[docs/ASSIGNMENT.md](docs/ASSIGNMENT.md#access-live-demo-data). Both `.env` and
`out/` are ignored by Git, so tokens and downloaded records stay local.
isolved payroll lives on legal company 5797; legal 5806, used for the other
data types, has no pay runs or checks
([entry 75](docs/DECISIONS.md#75-isolved-payroll-comes-from-legal-5797)).
