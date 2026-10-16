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

### 4. Normalization runs repeatedly, at least once per pay period

- **Context:** The assignment does not say how often normalization runs.
- **Decision:** Assume it runs again for each company at least once every pay
  period, so the same company's data is normalized many times. Normalizing the
  same input again must produce the same output.
- **Reason:** Payroll data is described as payroll runs and periods with
  paycheck records. A new payroll run happens every pay period, so the payroll
  data, and the employees it links to, has to be normalized again each time.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize), the
  **Payroll data** row ("Payroll runs/periods and employee paycheck records").
- **Status:** Decided.

## Findings in the reference material

### 5. PrismHR `getEmployee` does not return the owning client ID

- **Context:** `GET /employee/v1/getEmployee` takes `clientId` as a request
  parameter. The response schema `EmployeeAndEmployeeBySsnResponse` contains
  `client.clientEmployeeId` and `client.transferInfo.transferClientId`, but no
  field for the ID of the client the employee belongs to.
- **Decision:** The adapter reads the client ID from the capture bundle's
  `request.client_id` (entry 14) and uses it for the company key
  `prismhr:<client_id>` and every employee key.
- **Reason:** The request is the only place the ID exists.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee`. Confirmed live on 2026-10-15: the demo response
  for client `132` with all four options does not contain the client ID
  anywhere. `src/normalization/bundle.py` (`PROVIDER_SPECS["prismhr"]`);
  `tests/test_employee_prismhr.py::test_keys_and_company_link`.
- **Status:** Decided.

### 6. Some UKG Ready duration fields are in milliseconds

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

### 7. UKG Ready has no documented endpoint for company details

- **Context:** Every cached UKG Ready route sits under `/v2/companies/{cid}/...`.
  No page documents `GET /v2/companies/{cid}` or any other route that returns
  the company's name. The closest is `GET /v2/companies/{cid}/lookup/eins`,
  which returns EIN records (`id`, `ein_name`, `ein_tax_id`,
  `ein_currency_code`, `ein_country_id`). Employee records carry `ein_name`.
  The live demo tenant confirms this: `GET /rest/v2/companies/{cid}` returns
  404 "Unresolvable URL", and the EIN lookup returns one EIN named
  "Primary EIN", which is not a company name.
- **Decision:** Not decided yet. The likely approach is to build the company
  record from the sign-in `company_id` plus the EIN lookup, and leave the
  company name `null` with a reported issue. The employee task already does
  this for its company stub (entry 32); a full company record is a later task.
- **Evidence:** `contracts/ukg-ready/reference-docs/res/` has no company-detail
  page; `contracts/ukg-ready/reference-docs/res/__v2__companies__(cid)__lookup__eins.html`;
  live demo calls on 2026-10-15 for company `33704016`.
- **Status:** Open.

### 8. Live PrismHR `getEmployee` differs from its documentation

- **Context:** Live calls to the demo tenant on 2026-10-15 showed four
  differences from the spec:
  - With no `options`, the response holds only `id` and the name fields. The
    spec says the `Person` section is returned by default.
  - Several options must be comma-separated in one parameter
    (`options=Person,ContactInformation,Client,Compensation`). Repeating the
    `options` parameter silently returns only the first option.
  - `person.employerId` is returned, while the spec names the field
    `employerIds`. Likewise `person.autoPolicy` (spec `autoPolicies`) and
    `client.hawaiiMedWaiver` (spec `hawaiiMedWaivers`), and the live record
    carries `compensation.payPeriodsPerWeek`, which the spec does not list.
  - `compensation.ssn` is fully masked (`***-**-****`), but `person.birthDate`
    is returned unmasked, although the spec says both are masked by default.
- **Decision:** A PrismHR bundle holds `getEmployee` responses requested with
  the four options as one comma-separated value. The adapter does not map the
  renamed fields; it keeps them in `unmapped` under their live names and
  reports `spec_live_mismatch` once per bundle for each of the four
  differences. A masked SSN becomes `ssn_last4: null` plus a `masked_value`
  issue (entry 18).
- **Reason:** Renaming live fields to spec names would hide the discrepancy;
  reporting it once keeps the issue list readable.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee` (description and `Person` schema); live demo
  calls for client `132`, employee `A00576`;
  `src/normalization/adapters/prismhr.py` (`LIVE_SHAPE_DIFFERENCES`);
  `tests/test_employee_prismhr.py::test_live_spellings_reported_once_per_bundle`.
- **Status:** Decided.

### 9. Live isolved employee records carry fewer fields than the spec

- **Context:** The spec's `EmployeeModel` lists 95 properties. The live
  single-employee response for client `4046`, legal `5806` returned 62. It is
  missing 33 fields, including `assignedManager`, `assignedSupervisor`,
  `directDeposits`, `rehireDate`, `team`, `workersCompCode`, and `miscFields`.
  The list endpoint with `includeOrganizations`, `includeAlternateRates`, and
  `includeTaxes` returned the same record, except for `payRates` and some link
  URLs. The paging wrapper uses `results`, as the spec says.
- **Decision:** A field absent from a record maps to `null` with no issue.
  Only a missing `nameAddress` object is reported (`missing_section`), because
  it carries the name and home address.
- **Reason:** The spec marks none of these fields as required; absence is the
  normal shape of a live record, not a defect.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  definition `AOS.PayrollOffice.RestAPI.Models.EmployeeModel`; live demo calls
  on 2026-10-15; `tests/test_employee_isolved.py::test_sparse_record_has_nulls_and_no_extra_issues`.
- **Status:** Decided.

### 10. Live UKG Ready employee data needs several calls and lookups

- **Context:** Live calls to company `33704016` on 2026-10-15 showed:
  - The sign-in `base_url` ends at `/ta`, so every path needs a `/rest`
    prefix, as in `/rest/v2/companies/{cid}/employees`.
  - The employee record has no gender, ethnicity, or citizenship. Those come
    from `/demographics`. Employee type and pay type come from `/pay-info` as
    numeric IDs only. They are decoded by `/lookup/employee-types` and
    `/lookup/pay-types`, for example `35330176` is "FT Non-Exempt".
  - Pay amounts exist only in `/compensation/history`. The sampled employee
    has two entries: a zero-amount entry dated `1900-12-31` and a current
    entry (95000.0 per `YEAR`, effective 2026-01-01). Nothing marks which
    entry is current. The schema limits `effective_from` to 1900-12-31
    through 2079-06-05, so the first entry uses the earliest allowed date.
  - The compensation `time` field is documented as "Time is represented in
    milliseconds". The live value 7488000000 equals 2080 hours per
    `time_period` `YEAR`.
  - The record has `ein_name`, which the spec doesn't list. Phones, emails,
    managers, and cost centers were absent for the sampled employee.
- **Decision:** A UKG bundle carries the employee list plus, per account ID,
  the detail, demographics, pay-info and compensation-history responses, and
  the three company lookups (entry 14). A missing per-employee response is
  reported as `missing_section` and its fields are `null`. The current pay
  entry is chosen as described in entry 31. `time` and `standard_work_day`
  are converted from milliseconds to hours under entry 6, because their own
  documentation states the unit. `ein_name` on the detail response is
  reported once per bundle as `spec_live_mismatch`.
- **Reason:** No single UKG endpoint returns an employee; the bundle makes the
  joins explicit and testable.
- **Evidence:** `contracts/ukg-ready/reference-docs/res/__v2__companies__(cid)__employees__(aid).html`,
  `__v2__companies__(cid)__employees__(aid)__compensation__history.html`, and
  `__v2__companies__(cid)__employees__(aid)__pay-info.html`;
  `contracts/ukg-ready/reference-schemas.json`, the GET schema for the
  compensation history page (`effective_from` and `time` descriptions); live
  demo calls on 2026-10-15; `tests/test_employee_ukg_ready.py`.
- **Status:** Decided.

## Starter code issues

These are problems in the supplied starter code that need fixing before or
during implementation.

### 11. The readiness check blocks isolved and UKG Ready

- **Context:** `check-inputs` reports issues for isolved ("Candidate-distribution
  permission has not been verified") and for UKG Ready (the same, plus three
  issues about a missing OpenAPI file). `normalize` runs the same check and
  exits with code 2, so neither adapter can run.
- **Decision:** `readiness_issues` in `src/normalization/references.py` now
  matches the pack as supplied. It accepts a `distribution.status` of either
  `verified` or `user_approved_private_upload`, and still requires an
  `evidence_reference`. When `openapi.status` is `not_available`, it checks the
  pack's `reference_artifact` instead: `relative_path` must name a `.json` file
  inside `contracts/<provider>/` and `sha256` must be present. The `verified`
  OpenAPI checks are unchanged. The check stays metadata-only; file checksums
  are verified in `tests/test_reference_integrity.py`.
- **Reason:** The assignment says the organizer approved sharing the reference
  pack. It also states that UKG Ready has no OpenAPI contract, so it can never
  pass an OpenAPI check.
- **Evidence:** `contracts/isolved/lookup-reference.json` and
  `contracts/ukg-ready/lookup-reference.json` (`distribution.status`,
  `openapi.status`, `reference_artifact`);
  [docs/ASSIGNMENT.md](ASSIGNMENT.md#reference-materials);
  `tests/test_starter.py` (`test_reference_readiness_matches_distributed_materials`,
  `test_readiness_command_exits_zero_for_supplied_packs`, and the
  `ReadinessIssueChecks` negative-path tests).
  `PYTHONPATH=src python3 -m normalization check-inputs` now exits 0.
- **Status:** Decided.

### 12. Direct deposits and deductions are missing from the starter

- **Context:** `ENTITIES` in `src/normalization/adapters/__init__.py` lists only
  `company`, `employee`, and `payroll`.
- **Decision:** Not decided yet. Direct deposits and deductions need to be
  added, either as their own data types or as part of the employee record.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize).
- **Status:** Open.

### 13. A starter test requires every transformation to stay unimplemented

- **Context:** `test_all_nine_transformations_are_explicitly_unimplemented` in
  `tests/test_starter.py` fails as soon as any adapter works.
- **Decision:** Replace it with tests of real behavior as adapters are built.
  The test has been removed. The employee adapters now carry their own
  behavior tests (`tests/test_employee_*.py`).
- **Reason:** A test that asserts the absence of a feature blocks building it.
- **Evidence:** `tests/test_starter.py` no longer contains the test.
- **Status:** Decided.

### 14. An adapter receives only one response, with no request context

- **Context:** `normalize(entity, response, reference)` and the `--input` option
  accept one API response. One employee's data spans several endpoints, and
  some identifiers exist only in the request (see entry 5).
- **Decision:** Every adapter reads a **capture bundle**: one JSON document per
  provider and company with `bundle_version`, `provider`, `captured_at`,
  `request` (the request parameters) and `responses` (one raw response, or map
  of responses, per endpoint). `src/normalization/bundle.py` validates the
  envelope and the per-provider required and optional response keys and
  raises `ValueError` naming the offending path. `normalize --entity employee`
  loads the bundle; the `normalize(entity, response, reference)` entry point
  stays as the dispatch wrapper.
- **Reason:** Keeping request context and every endpoint's response together
  lets synthetic fixtures and hand-saved live downloads run through the same
  adapter code.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS`);
  `tests/test_bundle.py`; `tests/fixtures/*/employee-bundle.json`.
- **Status:** Decided.

## Employee normalization

### 15. The canonical model uses plain Python classes, not a validation library

- **Context:** The canonical record needs a guarantee that each field holds
  the right kind of value (a date is a date, an amount is a decimal) and a
  written description of the output shape that other people can read.
  Pydantic was the obvious candidate. The problem is how it treats input: by
  default it converts values to fit the declared type. The text `"1"` becomes
  the number `1`, `"true"` becomes `True`, a number becomes a string. That
  conversion is silent, and once it has happened there is no way to tell from
  the output what the provider actually sent.
- **Decision:** The model is built from Python's own `dataclasses` and `Enum`
  classes. Each class checks its fields when it is created and refuses wrong
  types rather than converting them: the text `"40"` is rejected where a
  number is expected, and a `True`/`False` is not accepted as a number. A
  value reaches the record exactly as the adapter produced it, or not at all.
  Records are immutable once built. A `to_dict()` method turns a record into
  plain JSON: dates become `YYYY-MM-DD` strings, amounts become strings so no
  precision is lost, and enums become their lowercase names.
  The output shape is written down by hand in
  `docs/canonical/employee.schema.json`, and a small built-in checker
  validates the test outputs against it. A test also compares the Python
  classes with the schema field by field, so the two cannot drift apart
  unnoticed.
- **Reason:** Entry 1 says the pipeline never guesses. A model that quietly
  reshapes values is a guess made on our behalf, and one that leaves no trace
  in the output or the issues list. Pydantic has a strict mode that turns
  conversion off, but the default behaviour would have to be remembered and
  switched off on every model; with plain classes there is nothing to switch
  off. A side benefit is that the project still needs nothing installed
  beyond Python 3.14.
- **Evidence:** `src/normalization/canonical/common.py` (`check_types`,
  `to_jsonable`); `tests/test_canonical_model.py`
  (`test_each_model_field_set_matches_schema_properties`,
  `test_optional_fields_are_nullable_in_schema`,
  `test_golden_outputs_validate_against_schema`).
- **Status:** Decided.

### 16. Every coded field is a `CodedValue`

- **Context:** Providers return codes (`A`, `35330176`), labels (`Active`,
  `FT Non-Exempt`) or both, and many codes have no documented meaning.
- **Decision:** A coded field is `{"raw", "label", "value"}`: the provider's
  raw code, the provider-side description when one exists, and the canonical
  enum member. `value` is `unknown` when the code cannot be mapped and `null`
  for fields with no canonical domain (job code, department, location,
  division, termination reason, ethnicity). Every canonical enum ends with
  `unknown`.
- **Reason:** Nothing is lost: the raw value and label survive for downstream
  consumers even when no canonical meaning can be assigned.
- **Evidence:** `src/normalization/canonical/common.py` (`CodedValue`);
  `tests/test_canonical_model.py::test_every_canonical_enum_ends_with_unknown`.
- **Status:** Decided.

### 17. When a raw value may map to a canonical enum

- **Context:** Entry 1 forbids guessing, but some labels are unambiguous.
- **Decision:** A raw value maps to a canonical enum member only if
  (a) the provider spec documents the code's meaning (PrismHR field
  descriptions), (b) it is a member of a closed schema enum whose label is
  self-describing (UKG `gender`, `citizenship`, `amount_period`,
  `time_period`), or (c) it is an exact, case-sensitive match on a short
  per-provider allowlist of labels observed live, each recorded as its own
  entry below (entries 23-26). No substring or case-insensitive matching.
  Anything else stays `unknown` with the raw value and label kept and an
  `undocumented_code` issue (codes) or `unmapped_label` issue (labels).
- **Reason:** Makes the boundary between evidence and inference explicit and
  auditable.
- **Evidence:** `src/normalization/adapters/_common.py` (`CodeTable`,
  `Collector.code`); the `CodeTable` constants in each adapter cite their
  spec path.
- **Status:** Decided.

### 18. Only the last four SSN digits are emitted

- **Context:** PrismHR returns `compensation.ssn` masked; isolved returns `ssn`
  empty; UKG returns `social_security` and `national_id_numbers[].value` in
  full.
- **Decision:** The canonical record holds `person.ssn_last4` only. A masked
  value (`***-**-****`) becomes `null` with a `masked_value` issue. In
  `unmapped` and in issue `raw_value`, any path matching `ssn`,
  `social_security`, `social_insurance`, `national_insurance`, `national_id`,
  `bsn`, `password`, `secret`, `token`, `ticket`, `photo_href` or
  `bank_account` is replaced by `[redacted]`. Tests assert no full SSN from a
  bundle appears anywhere in the output.
- **Reason:** The assignment requires that live records and secrets stay out
  of Git; the output files are the most likely thing to be committed or
  shared. UKG `photo_href` carries a bearer ticket.
- **Evidence:** `src/normalization/adapters/_common.py` (`redact`,
  `Collector.ssn_last4`); `tests/test_employee_prismhr.py::test_only_last_four_ssn_digits_are_emitted`;
  `tests/test_employee_ukg_ready.py::test_identifiers_and_tokens_are_redacted_in_unmapped`.
- **Status:** Decided.

### 19. Unconsumed provider fields pass through in `unmapped`

- **Context:** The assignment asks to cover all available employee fields;
  PrismHR alone returns over 200 leaf fields per employee, most with no
  canonical home (`ohioFormC112`, `fedW5Filed`).
- **Decision:** Each adapter reads through a `Reader` that records every JSON
  path it consumed. Everything left over is emitted in `employee.unmapped`,
  keyed by its dotted source path (list items of objects are indexed, as in
  `organizations[1].organizationId`), with the redaction of entry 18. No
  provider field is silently dropped.
- **Reason:** Coverage without inventing canonical slots for provider-specific
  fields.
- **Evidence:** `src/normalization/adapters/_common.py` (`Reader.unmapped`);
  `tests/test_employee_prismhr.py::test_unmapped_keeps_unconsumed_fields_and_redacts_identifiers`.
- **Status:** Decided.

### 20. Issue codes and severities for the employee task

- **Context:** Entry 1 requires structured issues; their vocabulary needed
  fixing.
- **Decision:** `Issue` has `code`, `severity`, `source_path`, `action`,
  `record_key`, `raw_value` (redacted) and `message`. Codes and severities:
  `invalid_date`, `invalid_number` are `error`; `undocumented_code`,
  `unmapped_label`, `missing_section`, `missing_lookup`,
  `out_of_schema_value`, `multiple_current_rates` are `warning`;
  `spec_live_mismatch`, `masked_value` are `info`. An `error` means a value
  was dropped; a `warning` means a value is present but not interpreted; an
  `info` is a note about the provider.
- **Evidence:** `src/normalization/canonical/issues.py`; the fixture outputs
  under `tests/fixtures/expected/`.
- **Status:** Decided.

### 21. Test data is made up, generated from a fixed seed

- **Context:** Tests have to run offline and give the same result every time,
  and no real employee record may ever be committed to Git.
- **Decision:** A script, `scripts/generate_fixtures.py`, invents a small
  company of six to seven employees for each provider. Names, addresses, dates
  and pay amounts come from fixed lists and a random generator seeded with
  the number `20261015`, so running the script again produces exactly the same
  files. The field names and layout copy what the live APIs actually return.
  For each provider the script writes two files: the input bundle
  (`tests/fixtures/<provider>/employee-bundle.json`) and the output the
  adapter is expected to produce from it
  (`tests/fixtures/expected/<provider>-employees.json`).
  Each company deliberately includes awkward records so the tests can check
  that every kind of problem is caught and reported. Examples: an employee
  with an unknown status code, a masked Social Security number, a birth date
  of 30 February, a UKG employee with no demographics record, two pay rates
  that start on the same day, and a status label nobody documented.
  Running the script with `--check` compares its output with the committed
  files and fails if they differ, and a test does the same.
- **Reason:** Realistic but fake data lets anyone run the full test suite
  with no credentials and no network, and makes the expected output easy to
  read and review.
- **Evidence:** `scripts/generate_fixtures.py` (the comment above each
  `build_*` function lists that provider's injected cases);
  `tests/test_fixtures_deterministic.py`.
- **Status:** Decided.

### 22. PrismHR `typeClass` is the employment type

- **Context:** `client.employeeType` is a service-provider-defined code
  ("FT"); `client.typeClass` is the classification behind it.
- **Decision:** `employment.employment_type` maps `typeClass` `F` ->
  `full_time`, `P` -> `part_time`, with `employeeType` kept as the label.
  Likewise `employment.status` maps `statusClass` `A`/`L`/`T` ->
  `active`/`on_leave`/`terminated` with `employeeStatus` as the label.
- **Reason:** The spec documents the class codes but says the type and status
  codes are defined by the service provider.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`,
  `#/paths/~1employee~1v1~1getEmployeeList/get/parameters` (`typeClass`:
  "(F)ull-time or (P)art-time"; `statusClass`: "(A)ctive, (L)eave, or
  (T)erminated"); `#/components/schemas/Client/properties/statusClass`,
  `employeeStatus` ("defined by the service provider"), `employeeType`.
- **Status:** Decided.

### 23. isolved `employmentStatus` allowlist: `Active`, `Terminated`

- **Context:** The spec describes the field as "The current employment status
  description" with no enum.
- **Decision:** Exact labels `Active` -> `active` and `Terminated` ->
  `terminated`. Any other label (live tenants may configure more) stays
  `unknown` with `unmapped_label`.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeModel/properties/employmentStatus`;
  live `GET /api/clients/4046/legals/5806/employees` on 2026-10-15 returned
  exactly these two labels across 20 employees;
  `tests/test_employee_isolved.py::test_allowlisted_labels_map`.
- **Status:** Decided.

### 24. isolved `gender` allowlist: `Male`, `Female`

- **Context:** The spec describes the field as "Gender description" with no
  enum.
- **Decision:** Exact labels `Male` -> `male`, `Female` -> `female`; other
  labels stay `unknown` with `unmapped_label`. Nonbinary and declined are not
  on the allowlist because no live label for them was observed.
- **Evidence:** same definition, `properties/gender`; live sample on
  2026-10-15; `tests/test_employee_isolved.py::test_off_allowlist_labels_stay_raw_with_issue`.
- **Status:** Decided.

### 25. isolved pay type: `Salary`, `Hourly` and `1099` are recognised

- **Context:** isolved's `payType` field is a free-text label. The spec only
  says it is "the specified pay type for the employee" and gives no list of
  possible values.
- **Decision:** Three labels are recognised, spelled exactly as isolved sends
  them: `Salary` becomes `salary`, `Hourly` becomes `hourly`, and `1099`
  becomes `contractor_1099`. Any other label is kept as-is with the canonical
  value `unknown` and a reported issue.
  Separately, the yes/no field `contractor_1099` on the employment section is
  left empty for isolved. Seeing `payType = 1099` strongly suggests the person
  is a contractor, but the pay type and the contractor flag are two different
  facts, and isolved only tells us the first one.
- **Reason:** These three labels were the only ones seen in the live demo
  company, and their meaning is plain English. Anything beyond that would be a
  guess.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeModel/properties/payType`;
  live `GET /api/clients/4046/legals/5806/employees` on 2026-10-15 (labels
  `Salary`, `Hourly`, `1099` across 20 employees);
  `tests/test_employee_isolved.py::test_allowlisted_labels_map`.
- **Status:** Decided.

### 26. UKG Ready `status` allowlist: `Active`, `Terminated`

- **Context:** The detail schema types `status` as a plain string ("only used
  for GET") with no enum.
- **Decision:** `Active` -> `active`, `Terminated` -> `terminated`; other
  values stay `unknown` with `unmapped_label`.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/106/schema/properties/status`;
  live `GET /rest/v2/companies/33704016/employees` on 2026-10-15 returned
  only these two values across 103 employees;
  `tests/test_employee_ukg_ready.py::test_status_allowlist`.
- **Status:** Decided.

### 27. isolved pay frequency and employment category are left as "unknown"

- **Context:** Two isolved fields look obvious but are not documented.
  `payFrequency` is a number; the live company shows `12`, which looks like
  "12 times a year", so monthly. `employmentCategoryCode` is a short code; the
  live company shows `FT` and `PT`, which look like full time and part time.
  The spec describes both fields in one line each and never says what the
  values mean.
- **Decision:** Both values are kept exactly as received, with the canonical
  value set to `unknown` and an issue reported. The pay frequency also carries
  the employee's pay group name (for example `Monthly`) as a label, because
  that is the human-readable text isolved provides next to it. `12` is not
  turned into "monthly" and `FT` is not turned into "full time".
- **Reason:** A number that happens to fit, or an abbreviation that looks
  familiar, is not documentation. Employment categories in particular are set
  up by each client, so `FT` could mean something different elsewhere. The raw
  values and the label are still in the output for anyone who needs them.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`, the
  `EmployeeModel` properties `payFrequency` and `employmentCategoryCode`;
  `tests/test_employee_isolved.py::test_client_codes_and_integer_frequency_are_undocumented`.
- **Status:** Decided.

### 28. UKG employee type and pay type: the name is shown, but not interpreted

- **Context:** UKG stores an employee's type and pay type as numeric IDs only
  (for example `35330176`). Two lookup endpoints translate those IDs into
  names such as `FT Non-Exempt` or `Salaried`. The names are not fixed by UKG;
  each customer defines their own list.
- **Decision:** The output shows the ID as the raw value and the looked-up
  name as the label, so a reader sees "35330176 = FT Non-Exempt". The
  canonical value stays `unknown` and an issue is reported. If an ID is not
  in the lookup at all, the label is empty and a different issue
  (`missing_lookup`) says so.
- **Reason:** Because customers write these names themselves, `FT Exempt` on
  one UKG company may not mean the same thing on another, and a name could be
  anything at all. Showing the name without claiming to understand it keeps
  the output honest while still being useful to a person reading it.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/159`
  (`employee_type` and `pay_type` carry only an `id`); live
  `/lookup/employee-types` and `/lookup/pay-types` on 2026-10-15;
  `tests/test_employee_ukg_ready.py::test_tenant_lookups_resolve_to_labels_but_stay_unknown`,
  `::test_lookup_miss_is_reported`.
- **Status:** Decided.

### 29. PrismHR `payPeriod` on `Compensation` is undocumented

- **Context:** `Compensation.payPeriod` is described only as "pay period
  associated with the payGroup". Other schemas (`PayRate.payPeriod`) document
  W/B/S/M/A/H, but the description on this schema does not.
- **Decision:** `compensation.pay_frequency` keeps the raw code with `value:
  unknown` and an `undocumented_code` issue. `hourlyPayPeriod`, whose own
  description lists H/W/B/S/M/Y, maps to `rate_period`.
- **Reason:** Entry 17(a) requires the meaning on the field actually read.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/payPeriod`
  and `.../hourlyPayPeriod`;
  `tests/test_employee_prismhr.py::test_pay_period_codes_are_undocumented_on_compensation`.
- **Status:** Open.

### 30. PrismHR `payMethod` `D` is "driver", not "daily"

- **Context:** The planning notes named the fifth canonical pay type `daily`.
  The PrismHR spec says `D` means driver.
- **Decision:** The `PayType` member is `driver`. No other provider documents a
  comparable code.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/payMethod`
  ("'S' (salary), 'H' (hourly), 'C' (commission), or 'D' (driver)");
  `tests/test_employee_prismhr.py::test_documented_codes_map_to_canonical_values`.
- **Status:** Open.

### 31. UKG pay: which row in the pay history counts as "current"

- **Context:** UKG does not have a single "current salary" field. Instead it
  returns the employee's whole pay history as a list of rows, each with a
  start date, an amount, and the period that amount covers (per year, per
  hour, per pay period, and so on). Nothing in the data says which row is in
  force today (entry 10). The live company also has a placeholder row dated
  31 December 1900 with zero amounts, which is simply the oldest date UKG
  allows.
- **Decision:** The current pay is the row with the most recent start date
  that is not after the date the data was captured. Rows that start in the
  future are ignored. If two rows start on the same day, the first one in
  UKG's list is used and an issue (`multiple_current_rates`) flags the
  conflict so a person can check.
  From that row: the headline `rate` is the amount together with its period;
  the `annual_amount` is filled in only when the period is a year, and the
  `per_period_amount` only when the period is a pay period; the hourly rate is
  copied from UKG's own `hourly_pay`. Nothing is calculated from one figure to
  another. Standard hours come from the row's `time` value, converted from
  milliseconds to hours (entry 6), with the period UKG gives for it.
  The field `num_pp_in_year` ("number of pay periods in a year") is a count,
  not a pay-frequency code, so it is not used to fill `pay_frequency`. It
  stays in `unmapped`, and a value of `0` (which the schema says is not
  allowed) is reported as an issue. All the other history rows are also kept
  in `unmapped`.
- **Reason:** "Most recent row that has already started" is what a payroll
  clerk would pick by hand. Copying each figure from the field UKG labels for
  it, rather than deriving one from another, means the output never claims
  more than the source does.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/122`;
  `tests/test_employee_ukg_ready.py::test_current_compensation_skips_placeholder_and_future_rows`,
  `::test_tied_effective_dates_report_multiple_current_rates`,
  `::test_zero_pay_periods_is_out_of_schema`.
- **Status:** Decided.

### 32. Company stub with `null` name

- **Context:** None of the employee endpoints returns the company's name.
- **Decision:** Each output carries `company` with `key`, `source` and `ein`
  only: PrismHR `prismhr:<client_id>`; isolved `isolved:<client_id>-<legal_id>`
  with `legalCode` as a secondary id when every record agrees; UKG
  `ukg-ready:<company_id>` with `ein` from `/lookup/eins` when it returns
  exactly one row (several rows report `missing_lookup`). `name` is `null`
  and a `missing_section` issue says a company endpoint is a later task.
- **Evidence:** `src/normalization/canonical/company.py`;
  `tests/test_employee_ukg_ready.py::test_company_stub_takes_ein_from_single_lookup_row`.
- **Status:** Decided.

### 33. Standard hours are "per pay period" for PrismHR and isolved

- **Context:** PrismHR `standardHours` is "standard hours per pay period";
  isolved `normalHours` is "Normal work hours for the employee per pay
  period". Neither carries a period code.
- **Decision:** `compensation.standard_hours_period` is
  `{raw: null, label: "per pay period", value: pay_period}` whenever
  `standard_hours` is present.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/standardHours`;
  `contracts/isolved/openapi/isolved-v6.swagger.json`, `EmployeeModel/properties/normalHours`.
- **Status:** Open.

### 34. Email and address kinds follow the field's description

- **Context:** PrismHR `contactInformation.emailAddress` ("the employee's
  email address") and isolved `emailAddress` ("Employee E-Mail Address") do not
  say whether the address is personal or work; UKG `primary_email` likewise.
- **Decision:** Those emails get `kind: unknown`. `workEmail`,
  `personalEmailAddress` and `secondary_email` get `work`, `personal` and
  `other`. Addresses: PrismHR `contactInformation.*` is `home`, `client.*`
  address fields are `mailing` ("alternate mailing address"), `person.w2*`
  is `w2`, and `getAddressInfo.altAddress` adds a `mailing` address when the
  record has none; isolved `nameAddress` is `home` and `overrideAddress` is
  `w2`; UKG `address` is `home` and `mailing_address` is `mailing` when
  `use_separate_mailing_address` is not `false`.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Client/properties/addressLine1`
  ("address line 1 from alternate mailing address"), `Person/properties/w2AddressLine1`;
  `contracts/isolved/openapi/isolved-v6.swagger.json`, `EmployeeModel/properties/overrideAddress`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/106/schema/properties/mailing_address`.
- **Status:** Open.

### 35. isolved location prefers `organizations[]`, then `workLocation`

- **Context:** With `includeOrganizations`, the detail response carries
  `organizations[]` rows titled `Location` and `Department` with `value` and
  `valueDescription`. Every record also has `workLocation` plus
  `workLocationDashDescription`.
- **Decision:** `job.department` comes from the `Department` row.
  `job.location` comes from the `Location` row when present, otherwise from
  `workLocation` with `workLocationDashDescription` as the label. Other
  organization rows stay in `unmapped`.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeOrganizationModel`
  and `EmployeeModel/properties/workLocation`;
  `tests/test_employee_isolved.py::test_detail_overlay_supplies_organizations_and_taxes`.
- **Status:** Open.

### 36. PrismHR gender codes are documented on a different schema

- **Context:** `Person.gender` says only "the employee's gender: M, F, X or D".
  The meanings appear on `NewHireEmployee.gender`: "'M' (male), 'F' (female),
  'X' (non-binary), 'D' (declined) or 'U' (unknown)".
- **Decision:** `M`/`F`/`X`/`D` map to `male`/`female`/`nonbinary`/`declined`,
  taking the `NewHireEmployee` description as the documentation for the same
  code set. Any other value (including `U`) stays `unknown` with
  `undocumented_code`.
- **Reason:** Both schemas describe the same employee attribute with the same
  four letters; the hire request is where PrismHR spells out the meanings.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Person/properties/gender`
  and `#/components/schemas/NewHireEmployee/properties/gender`;
  `src/normalization/adapters/prismhr.py` (`GENDER`).
- **Status:** Open.
