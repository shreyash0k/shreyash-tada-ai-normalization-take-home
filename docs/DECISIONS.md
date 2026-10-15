# Assumptions and decisions

This file records every assumption and decision made while building the
project, along with the reason and the evidence behind it. Add an entry
whenever a mapping choice is made, a source is unclear, or data does not match
expectations.

Each entry uses this format:

- **Context:** what was found or what needed deciding.
- **Decision:** what the project does.
- **Reason:** why.
- **Evidence:** a spec path, lookup entry, or test that supports it.
- **Status:** `Decided` or `Open`.

## Principles

### 1. Never guess codes, units, or missing values

- **Context:** The lookup references are intentionally partial. PrismHR's
  documents 43 codes across 8 domains. isolved's 11 domains and UKG Ready's 15
  domains list code values with every meaning left `null`. Tenant-configured
  codes are not supplied at all.
- **Decision:** Keep the raw source value. A code with no documented meaning
  becomes `unknown`, and an invalid or missing value becomes `null`. Each case is
  reported as a structured issue. No meaning, unit, or value is inferred from a
  field name, a value's magnitude, or another provider's convention.
- **Reason:** The assignment requires preserving the meaning of the source data.
  A wrong guess in payroll data is worse than an explicit unknown.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#reference-materials),
  [docs/REFERENCE_AUDIT.md](REFERENCE_AUDIT.md), and the `lookup-reference.json`
  file for each provider.
- **Status:** Decided.

### 2. Use only the primary isolved snapshot

- **Context:** isolved has two Swagger 2.0 snapshots of API version 6.
- **Decision:** All isolved mappings come from `isolved-v6.swagger.json`. The
  alternate snapshot is never used as a schema source.
- **Reason:** The assignment says to use the primary snapshot consistently and
  not to mix schemas between the two.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#reference-materials).
- **Status:** Decided.

### 3. Build the core first, then the extras

- **Context:** The assignment asks for four data types across three providers,
  plus an optional write path.
- **Decision:** Work in this order:
  1. A shared issue-reporting structure.
  2. Normalization of all data types with tests.
  3. The README and this file.
  4. The optional write path.
  5. Grouped issue reporting.
- **Reason:** Most of the evaluation is about normalization quality. Each step
  leaves the submission complete if time runs out.
- **Status:** Decided.

## Findings in the reference material

### 4. PrismHR `getEmployee` does not return the owning client ID

- **Context:** `GET /employee/v1/getEmployee` takes `clientId` as a request
  parameter. The response schema `EmployeeAndEmployeeBySsnResponse` contains
  `client.clientEmployeeId` and `client.transferInfo.transferClientId`, but no
  field for the ID of the client the employee belongs to.
- **Decision:** Not decided yet. The likely approach is to pass the request's
  `clientId` into the adapter so employees can be linked to their company.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee`.
- **Status:** Open.

### 5. Some UKG Ready duration fields are in milliseconds

- **Context:** The cached UKG Ready documentation describes certain fields as
  integers in milliseconds, for example `total` on time entries and
  `standard_work_day` on pay info.
- **Decision:** Convert a field from milliseconds only when its own
  documentation says it is in milliseconds. Any other duration field with no
  documented unit is kept as-is and reported as an issue.
- **Reason:** The reference audit warns that the evidence covers only those
  specific fields, not every UKG time field.
- **Evidence:** [docs/REFERENCE_AUDIT.md](REFERENCE_AUDIT.md#field-specific-ukg-duration-evidence).
- **Status:** Decided.

## Starter code issues

These are problems in the supplied starter code that need fixing before or
during implementation.

### 6. The readiness check blocks isolved and UKG Ready

- **Context:** `check-inputs` reports issues for isolved ("Candidate-distribution
  permission has not been verified") and for UKG Ready (the same, plus three
  issues about a missing OpenAPI file). `normalize` runs the same check and
  exits with code 2, so neither adapter can run.
- **Decision:** Not decided yet. The proposed fix updates `references.py` to
  accept the organizer's approval and to check UKG Ready's
  `reference-schemas.json` instead of an OpenAPI file, then updates the matching
  assertions in `tests/test_starter.py`.
- **Reason:** The assignment says the organizer approved sharing the reference
  pack. It also states that UKG Ready has no OpenAPI contract, so it can never
  pass an OpenAPI check.
- **Evidence:** `PYTHONPATH=src python3 -m normalization check-inputs` exits 2,
  and [docs/ASSIGNMENT.md](ASSIGNMENT.md#reference-materials).
- **Status:** Open.

### 7. Direct deposits and deductions are missing from the starter

- **Context:** `ENTITIES` in `src/normalization/adapters/__init__.py` lists only
  `company`, `employee`, and `payroll`.
- **Decision:** Not decided yet. Direct deposits and deductions need to be
  added, either as their own data types or as part of the employee record.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize).
- **Status:** Open.

### 8. A starter test requires every transformation to stay unimplemented

- **Context:** `test_all_nine_transformations_are_explicitly_unimplemented` in
  `tests/test_starter.py` fails as soon as any adapter works.
- **Decision:** Replace it with tests of real behavior as adapters are built.
- **Status:** Decided.

### 9. An adapter receives only one response, with no request context

- **Context:** `normalize(entity, response, reference)` and the `--input` option
  accept one API response. One employee's data spans several endpoints, and
  some identifiers exist only in the request (see entry 4).
- **Decision:** Not decided yet. The proposed fix is one input format for every
  adapter that holds the request parameters alongside a response for each
  endpoint.
- **Status:** Open.
