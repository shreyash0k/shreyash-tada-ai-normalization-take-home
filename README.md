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
minimal company stub so employee-to-company links resolve. Each provider has
seeded synthetic fixtures, a golden expected output, and edge-case tests.

Not implemented yet: company detail, direct deposits, deductions, payroll, the
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
  per provider; the fixtures under `tests/fixtures/` are complete examples.
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
  through in `employee.unmapped`, keyed by their source JSON path. Identifiers
  such as SSNs are reduced to `ssn_last4` and redacted everywhere else.
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
| `src/normalization/canonical/` | Canonical model (dataclasses, enums, issues) and the schema validator |
| `src/normalization/adapters/` | One adapter per provider plus shared helpers (`_common.py`) |
| `src/normalization/references.py` | Reference-pack readiness checks |
| `scripts/generate_fixtures.py` | Seeded fixture generator |
| `tests/` | Unit tests; `tests/fixtures/` holds the bundles and expected outputs |
| `docs/canonical/` | JSON Schema for the normalized output |
| `contracts/` | Provider API specifications and lookup references, as supplied |
| `docs/` | Assignment, decisions, and the reference audit |

## Setup

Developed and tested with Python 3.14. No third-party packages are needed.

```sh
git clone https://github.com/shreyash0k/shreyash-tada-ai-normalization-take-home.git
cd shreyash-tada-ai-normalization-take-home
```

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
```

For `--entity employee` the input must be a capture bundle whose `provider`
matches `--provider`. On success a summary such as `7 employees, 16 issues` is
printed to stderr. The output is a `NormalizedOutput` document
(`provider`, `company`, `employees[]`, `issues[]`, `schema_version`) described
by [docs/canonical/employee.schema.json](docs/canonical/employee.schema.json).

`normalize` will not overwrite an existing output file. Exit codes: 0 means
success, 1 means the input could not be read or normalized (including an
invalid bundle or an entity that is not implemented), and 2 means the
reference pack or the command-line arguments are not usable.

Regenerate or verify the synthetic fixtures:

```sh
python3 scripts/generate_fixtures.py          # rewrite tests/fixtures/**
python3 scripts/generate_fixtures.py --check  # exit 1 if the committed files differ
```

## Live demo data (optional)

Live provider data is used only to check mapping assumptions. Tests never depend
on it. To explore it, put the organizer-supplied key in `.env` as
`DEMO_SIGNIN_API_KEY` and follow the sign-in steps in
[docs/ASSIGNMENT.md](docs/ASSIGNMENT.md#access-live-demo-data). Both `.env` and
`out/` are ignored by Git, so tokens and downloaded records stay local.
