# Payroll data normalization: PrismHR, isolved, and UKG Ready

This project reads company, employee, direct deposit, deduction, and payroll data
from three payroll providers (PrismHR, isolved, and UKG Ready) and converts it
into one canonical model. A record looks the same in that model no matter which
provider it came from, and records stay linked: employees to companies,
paychecks to employees.

The assignment is in [docs/ASSIGNMENT.md](docs/ASSIGNMENT.md).
Every assumption and decision is recorded in [docs/DECISIONS.md](docs/DECISIONS.md).

## Status

Work in progress. The repository still contains the original starter: a
command-line entry point, a reference-pack readiness check, and one adapter stub
per provider. No provider mappings are implemented yet. Known problems with the
starter are listed in [docs/DECISIONS.md](docs/DECISIONS.md#starter-code-issues).

## Approach

- **One adapter per provider.** Each adapter turns that provider's API responses
  into canonical records. Everything provider-specific stays inside its adapter.
- **A canonical model designed for this project.** It covers companies,
  employees, direct deposits, deductions, payroll runs, and paychecks, with
  canonical enums and stable keys made from provider, company, and source ID.
- **Report problems instead of guessing.** Undocumented codes, invalid values,
  missing data, and unclear units are kept as they arrived. They are stored as
  `unknown` or `null` in the canonical record and reported as structured issues.
- **Every mapping has evidence.** Each field and code mapping cites the provider
  specification or lookup reference it is based on.
- **Deterministic, offline tests.** Tests run on synthetic fixtures generated
  from a fixed seed. They need no network access or credentials.

The optional write path described in the assignment, which maps canonical
employees back into a provider's format, comes after the core normalization.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/normalization/` | Command-line entry point, reference checks, provider adapters |
| `tests/` | Unit tests |
| `scripts/` | Fixture generation (not implemented yet) |
| `contracts/` | Provider API specifications and lookup references, as supplied |
| `docs/` | Assignment, decisions, and the reference audit |

## Setup

Developed and tested with Python 3.14. No third-party packages are needed yet.

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

# Normalize one provider response into a new output file
PYTHONPATH=src python3 -m normalization normalize \
  --provider prismhr --entity employee \
  --input path/to/response.json --output out/result.json
```

`normalize` will not overwrite an existing output file. Exit codes: 0 means
success, 1 means the input could not be read or normalized, and 2 means the
reference pack or the command-line arguments are not usable.

## Live demo data (optional)

Live provider data is used only to check mapping assumptions. Tests never depend
on it. To explore it, put the organizer-supplied key in `.env` as
`DEMO_SIGNIN_API_KEY` and follow the sign-in steps in
[docs/ASSIGNMENT.md](docs/ASSIGNMENT.md#access-live-demo-data). Both `.env` and
`out/` are ignored by Git, so tokens and downloaded records stay local.
