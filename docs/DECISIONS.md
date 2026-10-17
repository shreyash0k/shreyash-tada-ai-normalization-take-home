# Assumptions and decisions

This file records every assumption and decision made while building the
project, along with the reason and the evidence behind it. Add an entry
whenever a mapping choice is made, a source is unclear, or data does not match
expectations. There is a lot to read here, so each entry is written to be
read quickly: it explains the problem in plain words before naming fields, and
keeps the exact spec paths and test names in **Evidence** for anyone who wants
to check.

Each entry uses this format:

- **Context:** what was found or what needed deciding.
- **Decision:** what the project does.
- **Reason:** why.
- **Evidence:** a spec path, lookup entry, or test that supports it.
- **Status:** `Decided` or `Open`.

## Principles

### 1. Never guess codes, units, or missing values

- **Context:** The lookup references that explain provider codes are
  intentionally partial. PrismHR's documents 43 codes across 8 code lists.
  isolved's 11 code lists and UKG Ready's 15 list code values with every
  meaning left `null`. Codes that each customer configures for themselves are
  not supplied at all.
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

### 3. Normalization runs repeatedly, at least once per pay period

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

### 4. PrismHR `getEmployee` does not return the owning client ID

- **Context:** In PrismHR a "client" is the company an employee works for. To
  fetch employees you have to say which client you want, but the employee
  records that come back never repeat that client ID. The response has
  similar-looking fields (`client.clientEmployeeId`, the employee's number
  inside the client, and `client.transferInfo.transferClientId`, used for
  transfers), but none of them is the owning company.
- **Decision:** The client ID is taken from the request that was sent, which
  is saved alongside the responses in the capture bundle (entry 12). It is
  used to build the company key (`prismhr:<client_id>`) and every employee
  key, so each employee can be linked back to its company.
- **Reason:** The request is the only place the ID exists.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee`. Confirmed against the live demo: the response
  for client `132` with all four options does not contain the client ID
  anywhere. `src/normalization/bundle.py` (`PROVIDER_SPECS["prismhr"]`);
  `tests/test_employee_prismhr.py::test_keys_and_company_link`.
- **Status:** Decided.

### 5. Some UKG Ready duration fields are in milliseconds

- **Context:** UKG Ready stores some lengths of time as whole numbers of
  milliseconds rather than hours. Its documentation says so for certain
  fields, for example `total` on time entries and `standard_work_day` (the
  length of a normal working day) on pay info.
- **Decision:** A field is converted from milliseconds to hours only when its
  own documentation says it is in milliseconds. Any other time field with no
  documented unit is kept as received and reported as an issue.

  One exception was approved for payroll: UKG Ready pay statement
  earnings `hours` has no documented unit but is converted from
  milliseconds (entry 84).
- **Reason:** The reference audit warns that the evidence covers only those
  specific fields, not every UKG time field.
- **Evidence:** [docs/REFERENCE_AUDIT.md](REFERENCE_AUDIT.md#field-specific-ukg-duration-evidence); entry 84.
- **Status:** Decided.

### 6. Live PrismHR `getEmployee` differs from its documentation

- **Context:** PrismHR's employee call returns the record in sections
  (personal details, contact information, client details, pay), and the
  caller picks which sections it wants with an `options` parameter. Calling
  the live demo showed four ways the real behaviour differs from the spec:
  - Asking for no sections returns only the ID and name. The spec says the
    personal section comes back by default.
  - Several sections must be listed in one comma-separated value
    (`options=Person,ContactInformation,Client,Compensation`). Repeating the
    parameter once per section silently returns only the first one.
  - A few fields are spelled differently from the spec: `employerId` instead
    of `employerIds`, `autoPolicy` instead of `autoPolicies`, and
    `hawaiiMedWaiver` instead of `hawaiiMedWaivers`. The live record also has
    `payPeriodsPerWeek`, which the spec does not list at all.
  - The Social Security number is fully masked (`***-**-****`), but the birth
    date comes back in full, although the spec says both are masked by
    default.
- **Decision:** PrismHR data is always requested with all four sections in
  one comma-separated value. The differently spelled fields are not treated as
  the spec's fields; they are kept in `unmapped` under the names PrismHR
  actually sent. Each of the four differences is reported once per company as
  a `spec_live_mismatch` issue. A masked Social Security number gives an empty
  last-four value and a `masked_value` issue (entry 16).
- **Reason:** Quietly renaming live fields to match the spec would hide the
  fact that the two disagree. Reporting each difference once per company,
  rather than once per employee, keeps the issue list readable.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee` (description and `Person` schema); live demo
  calls for client `132`, employee `A00576`;
  `src/normalization/adapters/prismhr.py` (`LIVE_SHAPE_DIFFERENCES`);
  `tests/test_employee_prismhr.py::test_live_spellings_reported_once_per_bundle`.
- **Status:** Decided.

### 7. Live isolved employee records carry fewer fields than the spec

- **Context:** isolved's spec describes an employee record with 95 fields.
  A real employee from the live demo (client `4046`, legal entity `5806`) came
  back with only 62. The 33 missing ones include the manager and supervisor,
  direct deposits, rehire date, team, workers' compensation code, and custom
  fields (`assignedManager`, `assignedSupervisor`, `directDeposits`,
  `rehireDate`, `team`, `workersCompCode`, `miscFields`). Asking the
  employee-list call to include organizations, alternate rates, and taxes
  gave the same record apart from pay rates and some links. The list is
  wrapped in pages under `results`, as the spec says.
- **Decision:** A field missing from a record is left empty (`null`) and no
  issue is raised. The one exception is the name-and-address block
  (`nameAddress`): if it is missing, a `missing_section` issue is reported,
  because that is where the employee's name and home address live.
- **Reason:** The spec marks none of these fields as required, so a record
  without them is normal, not broken. Flagging every absent field would bury
  the issues that matter.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  definition `AOS.PayrollOffice.RestAPI.Models.EmployeeModel`; live demo
  calls; `src/normalization/adapters/isolved.py` (`_IsolvedEmployeeMapper`).
- **Status:** Decided.

### 8. Live UKG Ready employee data needs several calls and lookups

- **Context:** In UKG Ready no single call returns a whole employee. For the
  live demo company (`33704016`) the pieces were spread out like this:
  - The employee record itself has no gender, ethnicity or citizenship;
    those come from a separate demographics call.
  - Employee type and pay type come from a pay-info call, but only as numeric
    IDs. Two company-wide lookups turn them into names, for example
    `35330176` is "FT Non-Exempt".
  - Pay amounts exist only in the compensation history. The sampled employee
    has two rows: a zero-amount placeholder dated `1900-12-31` (the earliest
    date the schema allows) and the real one, 95000.0 per year effective
    2026-01-01. Nothing marks which row is current.
  - Working time in that history is documented as milliseconds: the live
    value 7488000000 is 2080 hours a year.
  Two smaller findings: the sign-in response's `base_url` ends at `/ta`, so
  every path needs `/rest` in front (`/rest/v2/companies/{cid}/employees`),
  and the record carries `ein_name`, which the spec does not list. Phones,
  emails, managers and cost centres were absent for the sampled employee.
- **Decision:** A UKG capture bundle (entry 12) holds the employee list, four
  responses per employee (detail, demographics, pay info, compensation
  history), and the three company lookups (employee types, pay types, EINs).
  If one of an employee's four responses is missing, a `missing_section`
  issue is reported and the fields it would have supplied are left empty.
  Job titles and the contractor flag come from two optional additions, the
  jobs lookup and per-employee tax-info (entries 38 and 39). Pay frequency
  comes from two more, per-employee profiles and the pay-period profiles
  lookup (entry 35).
  The current pay row is chosen as described in entry 29. `time` and
  `standard_work_day` are converted from milliseconds to hours under entry 5,
  because their own documentation states the unit. The undocumented
  `ein_name` field is reported once per company as `spec_live_mismatch`.
- **Reason:** Since UKG splits an employee across several calls, keeping all
  of them together in one file makes the joining step visible and lets tests
  check it.
- **Evidence:** `contracts/ukg-ready/reference-docs/res/__v2__companies__(cid)__employees__(aid).html`,
  `__v2__companies__(cid)__employees__(aid)__compensation__history.html`, and
  `__v2__companies__(cid)__employees__(aid)__pay-info.html`;
  `contracts/ukg-ready/reference-schemas.json`, the GET schema for the
  compensation history page (`effective_from` and `time` descriptions); live
  demo calls; `tests/test_employee_ukg_ready.py`.
- **Status:** Decided.

## Starter code issues

These are problems in the supplied starter code that need fixing before or
during implementation.

### 9. The readiness check blocks isolved and UKG Ready

- **Context:** Before normalizing anything, the starter code checks that each
  provider's reference pack (spec plus lookup file) is allowed to be used and
  is complete. That check failed for isolved, because it only accepted packs
  marked "verified" for distribution, and these are marked as approved by the
  organizer for a private upload. UKG Ready failed the same way, and also
  because it has no OpenAPI file at all. Since `normalize` runs the same check
  and stops with exit code 2, neither provider could be processed.
- **Decision:** The check now accepts the packs as they were supplied:
  - A pack may be marked either "verified" or "approved by the user for a
    private upload", and in both cases must still say where the approval is
    recorded.
  - A provider with no OpenAPI file (UKG Ready) is checked against the
    reference file it ships instead: that file must be a `.json` file inside
    the provider's own `contracts/` folder, with a checksum recorded.
  Packs that do have a verified OpenAPI file are checked exactly as before.
  The check still only reads the pack's description of itself; the files'
  checksums are compared in a separate test.
- **Reason:** The assignment says the organizer approved sharing the reference
  pack. It also states that UKG Ready has no OpenAPI contract, so it could
  never pass a check that requires one.
- **Evidence:** `src/normalization/references.py` (`readiness_issues`:
  `distribution.status` `verified` or `user_approved_private_upload` with an
  `evidence_reference`; `openapi.status` `not_available` falls back to
  `reference_artifact.relative_path` and `sha256`);
  `tests/test_reference_integrity.py` (checksums);
  `contracts/isolved/lookup-reference.json` and
  `contracts/ukg-ready/lookup-reference.json` (`distribution.status`,
  `openapi.status`, `reference_artifact`);
  [docs/ASSIGNMENT.md](ASSIGNMENT.md#reference-materials);
  `tests/test_starter.py` (`test_reference_readiness_matches_distributed_materials`,
  `test_readiness_command_exits_zero_for_supplied_packs`, and the
  `ReadinessIssueChecks` negative-path tests).
  `PYTHONPATH=src python3 -m normalization check-inputs` now exits 0.
- **Status:** Decided.

### 10. Direct deposits and deductions are missing from the starter

- **Context:** The assignment asks for direct deposits and deductions, but the
  starter code only knows about three data types: company, employee, and
  payroll.
- **Decision:** Direct deposits are their own data type. `normalize
  --entity direct-deposit` writes one record per bank line in a top-level
  `direct_deposits` list, next to the (empty) `employees` list. Each record
  carries the key of the employee it belongs to and the company key, so it
  links to the employee output. Deductions follow the same pattern:
  `--entity deduction` writes one record per deduction rule in a
  top-level `deductions` list (entry 59). Payroll follows the same
  pattern: `--entity payroll` writes a `pay_runs` list and a `paychecks`
  list (entry 71).
- **Reason:** The employee output stays the same whichever data types are
  added later, and `--entity` keeps meaning "which records this run
  produces". The employee key is enough to join the two outputs.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize);
  `ENTITIES` in `src/normalization/adapters/__init__.py`;
  `src/normalization/canonical/direct_deposit.py`;
  `src/normalization/canonical/deduction.py`;
  `src/normalization/canonical/payroll.py`;
  `tests/test_direct_deposit_*.py::test_lines_link_to_employees_and_company`;
  `tests/test_deduction_*.py::test_lines_link_to_employees_and_company`;
  `tests/test_payroll_*.py::test_records_link_to_runs_employees_and_company`.
- **Status:** Decided.

### 11. A starter test requires every transformation to stay unimplemented

- **Context:** One starter test checks that every provider-and-data-type
  combination is still unimplemented, so it fails the moment any adapter
  starts working.
- **Decision:** The test has been removed, and each adapter gets tests of
  what it actually does instead, in one test file per data type and
  provider (`tests/test_employee_*.py`, `tests/test_payroll_*.py` and so
  on).
- **Reason:** A test that asserts the absence of a feature blocks building it.
- **Evidence:** `tests/test_starter.py` no longer contains
  `test_all_nine_transformations_are_explicitly_unimplemented`.
- **Status:** Decided.

### 12. An adapter receives only one response, with no request context

- **Context:** The starter code passes each adapter a single API response.
  That is not enough: one employee's data is spread across several calls
  (entry 8), and some identifiers exist only in the request that was sent,
  not in any response (entry 4).
- **Decision:** Every adapter reads a **capture bundle**: one JSON file for
  one provider and one company, holding the details of the request and every
  response needed. It has five parts: a format version (`bundle_version`),
  the provider name, the date the data was captured (`captured_at`), the
  request parameters (`request`), and the responses grouped by call
  (`responses`). Each provider has its own list of calls that must be present
  and calls that may be present. A bundle that is missing a required part, or
  has one in the wrong shape, is rejected with a message naming exactly which
  part is wrong. Every `normalize --entity` value reads a bundle. Which
  calls are required depends on the data type being normalized; a bundle
  may hold the calls for several, so one capture can feed several runs.
- **Reason:** Keeping the request and every response together means made-up
  test data and real downloads saved by hand go through exactly the same
  code.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS` lists the
  required and optional responses per provider and data type;
  `parse_bundle` raises `ValueError` naming the offending path);
  `tests/test_bundle.py` (`test_required_keys_depend_on_the_entity`,
  `test_one_bundle_can_feed_every_entity`);
  `tests/fixtures/*/*-bundle.json`.
- **Status:** Decided.

## Employee normalization

### 13. The canonical model uses plain Python classes, not a validation library

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
  `docs/canonical/normalized-output.schema.json`, and a small built-in checker
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

### 14. Every coded field is a `CodedValue`

- **Context:** Providers describe things like employment status in different
  ways: some send a short code (`A`, `35330176`), some a readable label
  (`Active`, `FT Non-Exempt`), some both. Many of the codes have no documented
  meaning.
- **Decision:** Every such field has the same three parts in the output:
  - `raw`: exactly what the provider sent, for example `A`;
  - `label`: the provider's own description, when it gives one, for example
    `Active`;
  - `value`: our shared meaning, for example `active`.
  When the meaning cannot be established, `value` is `unknown`. Fields where
  there is no shared list of meanings at all (job code, department, location,
  division, termination reason, ethnicity) have `value` empty (`null`) and
  carry just the raw value and label. Every shared list ends with `unknown`.
- **Reason:** Nothing is lost. Even when we cannot say what a code means, the
  original code and label are still there for whoever uses the output.
- **Evidence:** `src/normalization/canonical/common.py` (`CodedValue`);
  `tests/test_canonical_model.py::test_every_canonical_enum_ends_with_unknown`.
- **Status:** Decided.

### 15. When a raw value may map to a canonical enum

- **Context:** Entry 1 forbids guessing what a code means, but some values
  are plainly clear, such as a label that just says `Active`. A rule was
  needed for when a provider value may be given a shared meaning.
- **Decision:** A value is given a meaning in only three cases:
  - (a) the provider's spec says what the code means (PrismHR does this in
    many field descriptions);
  - (b) the spec gives a fixed list of allowed values whose names explain
    themselves (UKG's `gender`, `citizenship`, `amount_period`,
    `time_period`);
  - (c) the label is on a short list of labels actually seen in the live
    data, matched exactly, including capital letters. Each such list has its
    own entry below (entries 21-24).
  Partial matches and case-insensitive matches never count. Anything else
  stays `unknown`, keeps its raw value and label, and is reported: as
  `undocumented_code` for a code, or `unmapped_label` for a label.
- **Reason:** It makes the line between "documented" and "inferred" explicit,
  so anyone can check why a value got the meaning it did.
- **Evidence:** `src/normalization/adapters/_common.py` (`CodeTable`,
  `Collector.code`); the `CodeTable` constants in each adapter cite their
  spec path.
- **Status:** Decided.

### 16. Only the last four SSN digits are emitted

- **Context:** The three providers handle Social Security numbers
  differently. PrismHR sends it masked (`***-**-****`), isolved sends it
  empty, and UKG sends it in full, both as `social_security` and inside its
  list of national ID numbers.
- **Decision:** The output keeps only the last four digits
  (`person.ssn_last4`). If the provider sent a masked number, there are no
  digits to keep, so the value is empty and a `masked_value` issue says why.
  Anywhere else the output repeats provider data (the `unmapped` leftovers in
  entry 17, and the raw value quoted in an issue), any field whose name looks
  like an identifier or a secret is replaced with `[redacted]`. That covers
  names containing `ssn`, `social_security`, `social_insurance`,
  `national_insurance`, `national_id`, `bsn`, `password`, `secret`, `token`,
  `ticket`, `photo_href`, `bank_account`, or a bank account, routing or
  transit number (`accountNum`, `account_number`, `routingNumber`,
  `transitNum` and similar spellings). Inside any other text value, a
  `token`, `ticket`, `sessionId` or `access_token` parameter of a link is
  replaced with `[redacted]` and the rest of the link is kept. Tests check
  that no full Social Security or bank account number from the input
  appears anywhere in the output.
- **Reason:** The assignment requires that live records and secrets stay out
  of Git, and output files are the most likely thing to be committed or
  shared. UKG's `photo_href` is on the list because the link carries a
  sign-in ticket, and its direct deposit `notes` links carry a `token`
  parameter.
- **Evidence:** `src/normalization/adapters/_common.py` (`redact`,
  `Collector.last4`); `tests/test_employee_prismhr.py::test_only_last_four_ssn_digits_are_emitted`;
  `tests/test_employee_ukg_ready.py::test_identifiers_and_tokens_are_redacted_in_unmapped`;
  `tests/test_direct_deposit_ukg_ready.py::test_secrets_are_not_emitted`.
- **Status:** Decided.

### 17. Unconsumed provider fields pass through in `unmapped`

- **Context:** The assignment asks to cover all available employee fields.
  PrismHR alone sends over 200 fields per employee, and most of them are
  specific to PrismHR and have no place in a shared model (for example
  `ohioFormC112` or `fedW5Filed`).
- **Decision:** Nothing is dropped. The adapter keeps track of every field it
  used; whatever is left over appears in the employee's `unmapped` section,
  under the field's path in the provider's data. Items in a list are numbered,
  as in `organizations[1].organizationId`. Identifiers and secrets are
  redacted as described in entry 16.
- **Reason:** It covers every field without inventing places in the shared
  model for fields only one provider has.
- **Evidence:** `src/normalization/adapters/_common.py` (`Reader.unmapped`);
  `tests/test_employee_prismhr.py::test_unmapped_keeps_unconsumed_fields_and_redacts_identifiers`.
- **Status:** Decided.

### 18. Issue codes and severities

- **Context:** Entry 1 says every problem is reported as a structured issue
  rather than hidden. Those issues needed a fixed vocabulary so they can be
  counted, filtered and compared across providers.
- **Decision:** Each issue says what kind of problem it is (`code`), how
  serious it is (`severity`), where in the provider's data it was found
  (`source_path`), what the pipeline did about it (`action`), which record
  it concerns (`record_key`), the value involved (`raw_value`, redacted as in
  entry 16), and a sentence explaining it (`message`). There are three levels
  of seriousness:
  - `error`: a value was unusable and was dropped. Codes: `invalid_date`,
    `invalid_number`.
  - `warning`: a value is kept but could not be interpreted, or something
    expected is missing. Codes: `undocumented_code`, `unmapped_label`,
    `missing_section`, `missing_lookup`, `out_of_schema_value`,
    `multiple_current_rates`, `inconsistent_allocation` (a deposit line's
    amount and percentage do not fit its method; entry 48), `broken_link`
    (a record points at a record missing from the company document;
    entry 99).
  - `info`: a note about the provider's behaviour, with nothing lost. Codes:
    `spec_live_mismatch`, `masked_value`, and `missing_section` when the
    absent part is optional.

  Two codes are a `warning` in one place each. A masked federal ID
  (`masked_value`, entry 89) leaves the company with no EIN. A bank
  account number under four digits (`invalid_number`, entry 47) is
  readable but too short to show only its last four digits.
- **Reason:** A small fixed set of codes lets someone see at a glance how many
  records lost data and how many only need a person to confirm a meaning,
  and makes issues from different providers directly comparable.
- **Evidence:** `src/normalization/canonical/issues.py`;
  `src/normalization/adapters/_common.py` (`Collector.last4`);
  `src/normalization/adapters/prismhr.py` (`federalIdNumber`); the fixture
  outputs under `tests/fixtures/expected/`.
- **Status:** Decided.

### 19. Test data is made up, generated from a fixed seed

- **Context:** Tests have to run offline and give the same result every time,
  and no real employee record may ever be committed to Git.
- **Decision:** A script, `scripts/generate_fixtures.py`, invents a small
  company of six to seven employees for each provider. Names, addresses, dates
  and pay amounts come from fixed lists and a random generator seeded with
  the number `20261015`, so running the script again produces exactly the same
  files. The field names and layout copy what the live APIs actually return.
  For each provider and each of the five data types the script writes two
  files: the input bundle (for example
  `tests/fixtures/<provider>/employee-bundle.json`) and the output the
  adapter is expected to produce from it (for example
  `tests/fixtures/expected/<provider>-employees.json`). Every bundle
  reuses the same employees.
  Routing numbers start with `99`, which no real US routing number does.
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

### 20. PrismHR employment type and status come from the "class" fields

- **Context:** PrismHR gives two fields each for an employee's type and
  status. The first (`employeeType`, `employeeStatus`) is a code that each
  PrismHR service provider sets up for itself, such as `FT`, so it can mean
  anything. The second (`typeClass`, `statusClass`) is a fixed PrismHR
  category behind that code, and the spec says what its letters mean.
- **Decision:** The shared meaning comes from the fixed category: for type,
  `F` is full time and `P` is part time; for status, `A` is active, `L` is on
  leave and `T` is terminated. The provider's own code is kept next to it as
  the label, so the output shows both, for example `F` / `FT` / `full_time`.
- **Reason:** The spec documents the category letters, but says the type and
  status codes are defined by the service provider.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`,
  `#/paths/~1employee~1v1~1getEmployeeList/get/parameters` (`typeClass`:
  "(F)ull-time or (P)art-time"; `statusClass`: "(A)ctive, (L)eave, or
  (T)erminated"); `#/components/schemas/Client/properties/statusClass`,
  `employeeStatus` ("defined by the service provider"), `employeeType`.
- **Status:** Decided.

### 21. isolved employment status: `Active` and `Terminated` are recognised

- **Context:** isolved sends employment status as a text label
  (`employmentStatus`). The spec calls it "the current employment status
  description" and gives no list of possible values.
- **Decision:** Two labels are recognised, spelled exactly as isolved sends
  them: `Active` becomes `active` and `Terminated` becomes `terminated`. Any
  other label is kept as received, with the shared value `unknown` and an
  `unmapped_label` issue. Live customers may well set up more statuses than
  these.
- **Reason:** These were the only two labels in the live demo company, and
  their meaning is plain English. Anything else would be a guess (entry 15).
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeModel/properties/employmentStatus`;
  live `GET /api/clients/4046/legals/5806/employees` returned exactly these
  two labels across 20 employees;
  `tests/test_employee_isolved.py::test_allowlisted_labels_map`.
- **Status:** Decided.

### 22. isolved gender: `Male` and `Female` are recognised

- **Context:** isolved sends gender as a text label (`gender`). The spec calls
  it "Gender description" and gives no list of possible values.
- **Decision:** Two labels are recognised, spelled exactly as isolved sends
  them: `Male` becomes `male` and `Female` becomes `female`. Any other label
  is kept as received, with the shared value `unknown` and an
  `unmapped_label` issue. Non-binary and "declined to state" are not on the
  list, because we have not seen how isolved spells them.
- **Reason:** Only these two labels appeared in the live demo company.
  Guessing the spelling of other options could wrongly match, or miss, real
  values (entry 15).
- **Evidence:** same definition, `properties/gender`; the live sample;
  `src/normalization/adapters/isolved.py` (`GENDER`).
- **Status:** Decided.

### 23. isolved pay type: `Salary`, `Hourly` and `1099` are recognised

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
  live `GET /api/clients/4046/legals/5806/employees` (labels `Salary`,
  `Hourly`, `1099` across 20 employees);
  `tests/test_employee_isolved.py::test_allowlisted_labels_map`.
- **Status:** Decided.

### 24. UKG Ready employee status: `Active` and `Terminated` are recognised

- **Context:** UKG sends employee status (`status`) as plain text. The schema
  notes it is "only used for GET" and gives no list of possible values.
- **Decision:** Two values are recognised, spelled exactly as UKG sends them:
  `Active` becomes `active` and `Terminated` becomes `terminated`. Any other
  value is kept as received, with the shared value `unknown` and an
  `unmapped_label` issue.
- **Reason:** These were the only two values across all 103 employees in the
  live demo company, and their meaning is plain English. Anything else would
  be a guess (entry 15).
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/106/schema/properties/status`;
  live `GET /rest/v2/companies/33704016/employees` returned only these two
  values across 103 employees;
  `tests/test_employee_ukg_ready.py::test_status_allowlist`.
- **Status:** Decided.

### 25. isolved pay frequency and employment category are left as "unknown"

- **Context:** Two isolved fields look obvious but are not documented.
  `payFrequency` is a number; the live company shows `12`, which looks like
  "12 times a year", so monthly, though five employees in the same
  "Monthly" pay group show `26`. `employmentCategoryCode` is a short code; the
  live company shows `FT` and `PT`, which look like full time and part time.
  The spec describes both fields in one line each and never says what the
  values mean.
- **Decision:** Both values are kept exactly as received, with the canonical
  value set to `unknown`. The issue for a given value is reported once in a
  company; later employees who send the same value stay `unknown` without
  another issue. The pay frequency also carries the employee's pay group name
  (for example `Monthly`) as a label, because that is the human-readable text
  isolved provides next to it. `12` is not turned into "monthly" and `FT` is
  not turned into "full time". The citizenship text "Citizen of the United
  States" is reported the same way: once per company, then later employees
  stay `unknown` without another issue.
- **Reason:** A number that happens to fit, or an abbreviation that looks
  familiar, is not documentation. Employment categories in particular are set
  up by each client, so `FT` could mean something different elsewhere. The raw
  values and the label are still in the output for anyone who needs them.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`, the
  `EmployeeModel` properties `payFrequency` and `employmentCategoryCode`;
  `tests/test_employee_isolved.py::test_client_codes_and_integer_frequency_are_undocumented`.
- **Status:** Decided.

### 26. UKG employee type and pay type: the name is shown, but not interpreted

- **Context:** UKG stores an employee's type and pay type as numeric IDs only
  (for example `35330176`). Two lookup endpoints translate those IDs into
  names such as `FT Non-Exempt` or `Salaried`. The names are not fixed by UKG;
  each customer defines their own list.
- **Decision:** The output shows the ID as the raw value and the looked-up
  name as the label, so a reader sees "35330176 = FT Non-Exempt". The canonical
  value stays `unknown`. The issue for a given ID is reported once in a
  company; later employees with the same ID stay `unknown` without another
  issue. If an ID is not in the lookup at all, the label is empty and a
  different issue (`missing_lookup`) says so.
- **Reason:** Because customers write these names themselves, `FT Exempt` on
  one UKG company may not mean the same thing on another, and a name could be
  anything at all. Showing the name without claiming to understand it keeps
  the output honest while still being useful to a person reading it.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/159`
  (`employee_type` and `pay_type` carry only an `id`); live
  `/lookup/employee-types` and `/lookup/pay-types`;
  `tests/test_employee_ukg_ready.py::test_tenant_lookups_resolve_to_labels_but_stay_unknown`;
  `src/normalization/adapters/ukg_ready.py` (`_lookup`).
- **Status:** Decided.

### 27. PrismHR employee pay frequency uses the pay group's schedule codes

- **Context:** An employee's pay frequency in PrismHR comes from the
  `payPeriod` field in the pay section (`Compensation`). Its description says
  only "pay period associated with the payGroup", with no list of codes. The
  pay group's payroll schedule has a `payPeriod` too, and its codes are
  listed on the field next to it, `payPeriodDesc` (entry 90). On the live
  demo, every employee's `payPeriod` equalled the code on their pay group's
  schedule.
- **Decision:** Pay frequency is read with the schedule's code list: `W` is
  weekly, `B` biweekly, `S` semi-monthly, and `M` and every `MD*` code
  monthly. Daily (`D`) stays `unknown`, as there is no shared daily value. A
  code not on the list stays `unknown` with an `undocumented_code` issue (a
  code with no documented meaning). The neighbouring `hourlyPayPeriod`,
  which lists its own letters (H, W, B, S, M, Y), gives the period of the
  pay rate.
- **Reason:** The description points to the pay group, and the live data
  shows the field carries the pay group's code. A meaning is taken from
  another record only when the field points to it, as here, or uses exactly
  the same codes (entry 34). `PayRate.payPeriod` qualifies for neither: it
  is on an unrelated record and its letters differ.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/payPeriod`
  and `#/components/schemas/ClientPayrollSchedule/properties/payPeriodDesc`;
  `src/normalization/adapters/prismhr.py` (`PAY_PERIOD`);
  `tests/test_employee_prismhr.py::test_pay_period_uses_the_pay_group_schedule_codes`,
  `::test_pay_period_off_the_schedule_list_is_undocumented`.
- **Status:** Decided.

### 28. PrismHR `payMethod` `D` is "driver", not "daily"

- **Context:** The shared list of pay types (salary, hourly, commission, and so
  on) was planned with a fifth type, `daily`, to match PrismHR's pay method
  code `D`. The PrismHR spec actually says `D` means driver.
- **Decision:** The fifth pay type is `driver`. No other provider documents a
  comparable code.
- **Reason:** The spec is explicit, and "daily" was an assumption from the
  letter alone (entry 1).
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/payMethod`
  ("'S' (salary), 'H' (hourly), 'C' (commission), or 'D' (driver)");
  `tests/test_employee_prismhr.py::test_documented_codes_map_to_canonical_values`.
- **Status:** Decided.

### 29. UKG pay: which row in the pay history counts as "current"

- **Context:** UKG does not have a single "current salary" field. Instead it
  returns the employee's whole pay history as a list of rows, each with a
  start date, an amount, and the period that amount covers (per year, per
  hour, per pay period, and so on). Nothing in the data says which row is in
  force today (entry 8). The live company also has a placeholder row dated
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
  milliseconds to hours (entry 5), with the period UKG gives for it.
  The field `num_pp_in_year` ("number of pay periods in a year") is a count,
  not a pay-frequency code, so it is not used to fill `pay_frequency`,
  which comes from the employee's pay-period profile (entry 35). It
  stays in `unmapped`, and a value of `0` (which the schema says is not
  allowed) is reported as an issue. All the other history rows are also kept
  in `unmapped`.
- **Reason:** "Most recent row that has already started" is what a payroll
  clerk would pick by hand. Copying each figure from the field UKG labels for
  it, rather than deriving one from another, means the output never claims
  more than the source does.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/122`;
  `tests/test_employee_ukg_ready.py::test_current_compensation_skips_placeholder_and_future_rows`;
  `src/normalization/adapters/ukg_ready.py` (`_current_compensation`).
- **Status:** Decided.

### 30. Each output has a minimal company record with no name

- **Context:** Employees must be linkable to their company, but none of the
  employee, deposit, deduction or payroll calls returns the company's
  name. The company's own record comes from separate calls.
- **Decision:** Each output has a minimal company record (a "stub"): just a
  key that identifies the company, the provider it came from, and the EIN
  where it is known. The keys look like this:
  - PrismHR: `prismhr:<client_id>`.
  - isolved: `isolved:<client_id>-<legal_id>`, because an isolved client can
    have several legal entities. The legal entity's code (`legalCode`) is
    added as a second identifier when every employee record agrees on it.
  - UKG Ready: `ukg-ready:<company_id>`. The EIN is filled in from the EIN
    lookup when it returns exactly one row; if it returns several, a
    `missing_lookup` issue (a needed lookup entry is absent) says the EIN
    could not be chosen and that the company output lists each one.
  The company name is empty, and the minimal record raises no issue for
  it. The full company record is its own data type (`--entity company`,
  entries 86 to 95). Only that data type reads the company calls and
  reports what they lack, such as UKG Ready having no company endpoint
  (entry 94). Every other output keeps this minimal record, with the full
  record's other fields empty.
- **Reason:** Every employee needs a company key to link to, and the key can
  be built from identifiers the bundle already has. Filling in more than that
  would mean guessing (entry 1). An employee or payroll capture should not
  have to fetch company details to be normalized. An empty name here is by
  design, so a warning in each of the four outputs repeated one note four
  times and filled the issue tracker with nothing to fix.
- **Evidence:** `src/normalization/canonical/company.py`;
  `src/normalization/adapters/` (`_company` in each adapter);
  `tests/test_employee_ukg_ready.py::test_company_stub_takes_ein_from_single_lookup_row`;
  `tests/test_company_links.py::test_every_output_shares_the_company_key`;
  `tests/test_company_ukg_ready.py::test_profile_is_empty_with_an_issue`.
- **Status:** Decided.

### 31. Standard hours are "per pay period" for PrismHR and isolved

- **Context:** Both PrismHR and isolved send an employee's standard working
  hours as a bare number with no unit next to it. The period is only in the
  field's description: PrismHR `standardHours` is "standard hours per pay
  period", and isolved `normalHours` is "Normal work hours for the employee
  per pay period". The live values do not fit that reading. Monthly-paid
  PrismHR employees had `40.00` or `86.67`. Every isolved employee had
  `173.33`, which is a month of full-time hours, including those paid every
  two weeks.
- **Decision:** Whenever standard hours are present, the number is copied
  and its period is set to "per pay period". Since the provider sent no code
  for it, the raw value is empty and the label reads `per pay period`. The
  period is never worked out from the size of the number, and the live
  mismatch raises no issue.
- **Reason:** The descriptions are the only stated unit. Picking a period
  because a number looks monthly would be a guess (entry 1). A reader
  should not turn these hours into annual hours without checking the
  tenant's setup.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/standardHours`;
  `contracts/isolved/openapi/isolved-v6.swagger.json`, `EmployeeModel/properties/normalHours`;
  `tests/test_employee_prismhr.py::test_compensation_fields_are_not_derived`.
- **Status:** Decided.

### 32. Email and address kinds follow the field's description

- **Context:** Each email address and postal address in the output is tagged
  with a kind (work, personal, home, mailing, and so on). The providers often
  have several of each, and the field name or description is usually the
  only hint about which is which. Some descriptions give no hint: PrismHR's
  `contactInformation.emailAddress` is just "the employee's email address",
  isolved's `emailAddress` is "Employee E-Mail Address", and UKG's
  `primary_email` says nothing either. The main postal addresses have no
  description at all, but each provider sends a separate mailing or override
  address beside them.
- **Decision:** A kind is assigned when the field's name or description says
  it. The one exception is the main postal address. It is `home` when the
  provider sends a separate mailing or override address beside it.
  - Emails: the three above get kind `unknown`. Fields named as work,
    personal or secondary emails (`workEmail`, `personalEmailAddress`,
    `secondary_email`) get `work`, `personal` and `other`. PrismHR's
    `benefitEmail`, the address "to use when communicating with employee
    during online benefits enrollment", is also `other`.
  - Phones: home, mobile and work numbers keep those kinds. isolved's
    `faxNumber` ("Employee FAX number") is an `other` phone. Neither the
    benefit email nor a fax number appeared live.
  - PrismHR addresses: the contact-information address is `home`, beside
    the client section's address, which is `mailing` because its description
    says "alternate mailing address". The W-2 address fields are `w2`, and
    the separate address call (`getAddressInfo.altAddress`) adds a `mailing`
    address when the record has none.
  - isolved addresses: `nameAddress` is `home`, since `overrideAddress`
    describes itself as differing from the employee's "personal address".
    `overrideAddress` is `w2`.
  - UKG addresses: `address` is `home`, and `mailing_address` is `mailing`
    unless UKG says no separate mailing address is used
    (`use_separate_mailing_address` is `false`).
- **Reason:** Calling an email "personal" or "work" without the provider
  saying so would be a guess that downstream systems might act on, for
  example by sending payslips to the wrong inbox. A main address that sits
  next to an explicit alternate is the residence in all three providers, and
  tagging it `home` carries little risk.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Client/properties/addressLine1`
  ("address line 1 from alternate mailing address"), `ContactInformation/properties/addressLine1`,
  `Person/properties/w2AddressLine1`, `Client/properties/benefitEmail`;
  `contracts/isolved/openapi/isolved-v6.swagger.json`, `EmployeeModel/properties/overrideAddress`
  and `EmployeePersonalModel/properties/faxNumber`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/106/schema/properties/mailing_address`;
  `tests/test_employee_prismhr.py::test_addresses_phones_and_manager`;
  `tests/test_employee_isolved.py::test_personal_and_name_address_overrides`.
- **Status:** Decided.

### 33. isolved location comes from `workLocation`

- **Context:** isolved can describe where an employee works in two places.
  When asked to include organizations, the employee detail has a list of
  labelled rows (`organizations[]`), such as one titled `Location` and one
  titled `Department`, each with a code (`value`) and a description
  (`valueDescription`). Separately, every record has a `workLocation` code
  with a description (`workLocationDashDescription`). Live, the `Location`
  row held "BJ Scrap Metal", a business name, while `workLocation` held
  "UT1 - SALT LAKE CITY, UT".
- **Decision:** The department comes from the `Department` row. The
  location always comes from `workLocation`, with its description as the
  label. The `Location` row and any other organization rows are kept in
  `unmapped` (entry 17). isolved has no division field, and no row is read
  as one, so the coverage page shows division as "not offered". Live rows
  were only `Location` and `Department`.
- **Reason:** Each client titles and fills its own organization rows, so a
  row called "Location" need not hold a place, nor a row called "Division"
  a division. `workLocation` is on every record and is the code the
  company's work locations use, so every employee's location matches a
  work location on the company record (entry 87).
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeOrganizationModel`
  and `EmployeeModel/properties/workLocation`;
  `src/normalization/field_map.py` (`ISOLVED`, `job.division`);
  `tests/test_employee_isolved.py::test_detail_overlay_supplies_organizations_and_taxes`;
  `tests/test_company_links.py::test_isolved_employee_locations_and_pay_groups_resolve`.
- **Status:** Decided.

### 34. PrismHR gender codes are explained on a different record

- **Context:** The meanings of PrismHR's gender letters live on a different
  record from the one we read. The employee record's `gender` field says only
  "the employee's gender: M, F, X or D". The new-hire record
  (`NewHireEmployee.gender`) spells them out: "'M' (male), 'F' (female),
  'X' (non-binary), 'D' (declined) or 'U' (unknown)".
- **Decision:** `M`, `F`, `X` and `D` become `male`, `female`, `nonbinary`
  and `declined`, using the new-hire description as the documentation for
  the same set of letters. Any other value, including `U`, stays `unknown`
  with an `undocumented_code` issue.
- **Reason:** Both schemas describe the same employee attribute with the same
  four letters; the hire request is where PrismHR spells out the meanings.
  A meaning is taken from another record only when the field uses exactly
  the same codes, as here, or points to that record (entry 27).
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Person/properties/gender`
  and `#/components/schemas/NewHireEmployee/properties/gender`;
  `src/normalization/adapters/prismhr.py` (`GENDER`).
- **Status:** Decided.

### 35. UKG Ready pay frequency comes from the employee's pay-period profile

- **Context:** UKG Ready has no pay-frequency field on the employee.
  Instead each employee is assigned profiles, one of them a pay-period
  profile, and the employee's profiles call names it by ID
  (`pay_period`). The company's list of pay-period profiles says how
  often each one pays (entry 93). Live, 89 of the 103 demo employees
  named a pay-period profile, and every one was in the list: 87 on
  two-week profiles and 2 on the weekly one. The other 14 had none.
- **Decision:** Pay frequency shows the profile ID as the raw value, the
  profile name as the label, and that profile's frequency, read the same
  way as for pay groups (entry 93). An employee with no pay-period
  profile has no pay frequency. A profile ID missing from the list keeps
  its ID with an `unknown` value and a `missing_lookup` warning (a needed
  lookup entry is absent). Both calls are optional parts of the employee
  bundle; when one was not captured, a single `missing_section` issue (an
  expected part of the data is absent) at `info` severity says so.
- **Reason:** The profile is UKG's own record of how often the employee
  is paid, so the frequency is read, not inferred. This is the same
  pattern as PrismHR, where the employee's pay period points to its pay
  group's schedule (entry 27).
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/161/schema/properties/pay_period`
  and `#/schemas/273`; `src/normalization/adapters/ukg_ready.py`
  (`_UkgEmployeeMapper._pay_frequency`);
  `tests/test_employee_ukg_ready.py::test_pay_frequency_comes_from_the_pay_period_profile`,
  `::test_pay_period_profile_missing_from_lookup_stays_unknown`,
  `::test_profiles_and_pay_period_lookup_are_optional`.
- **Status:** Decided.

## Field coverage

### 36. What the coverage statuses mean

- **Context:** The field coverage pages show, for every canonical employee,
  direct deposit, deduction, payroll and company field, whether each provider
  supplies it. A provider can have the data and the adapter use it, have the
  data and the adapter not use it, or have no such field at all. A field the
  adapter uses can still be empty for every synthetic employee.
- **Decision:** The page shows three states: "mapped", "not mapped yet"
  and "not offered". A mapped cell shows the provider field it comes
  from. Every state cites a spec path, and "not offered" cites the schema
  that lacks the field and says why it is missing. A mapped field that no
  fixture employee fills still needs a generator note in the field map,
  and the tests enforce that. The page does not show it.
- **Reason:** The page shows the mapping into the canonical model, not
  how complete the synthetic sample is. "Not offered" is a claim about
  the provider, so it needs the same evidence as a mapping.
- **Evidence:** `src/normalization/field_map.py`;
  `src/normalization/deposit_field_map.py`;
  `src/normalization/deduction_field_map.py`;
  `src/normalization/payroll_field_map.py`;
  `src/normalization/company_field_map.py`;
  `tests/test_field_map.py::test_mapped_rows_are_filled_or_explain_the_gap`;
  `web/src/lib/status.ts`.
- **Status:** Decided.

### 37. UKG Ready termination and rehire details are write-only

- **Context:** UKG Ready describes an employee's termination reason and
  rehire eligibility only in the schema for updating an employee (schema
  107, the PUT body), both inside `termination_details` (`termination_reason`
  and `rehireable`). The schema for reading an employee (schema 106) has
  termination and rehire dates but no reason and no eligibility, and the
  live employee records matched it. The termination-reason lookup does say
  whether each reason allows rehire, but the read call never says which
  reason applies.
- **Decision:** The output has no termination reason or rehire
  eligibility for UKG Ready, and the coverage page shows both as "not
  offered".
- **Reason:** A field documented only for writing is not one the read
  call can be relied on to return.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/107/schema/properties/termination_details/properties/termination_reason`
  and `.../rehireable`;
  `#/schemas/106/schema/properties/dates`;
  `#/schemas/317` (termination-reason lookup);
  `src/normalization/field_map.py` (`UKG_READY`).
- **Status:** Decided.

### 38. Job titles come from each provider's job list; UKG Ready organization is not mapped yet

- **Context:** PrismHR and UKG Ready put only a job code on the employee
  record; the title lives in a separate list of jobs. For PrismHR that list
  is the job code table (`getClientCodes` with the `Job` option), where
  each entry's `jobTitle` is the "position/job title". For UKG Ready it is
  the jobs lookup (`lookup/jobs`), and the employee's default job is an ID
  (`pay_info.default_job`). Live, every PrismHR job code and every UKG
  default job ID was in its list. UKG Ready also gives organization as up
  to nine cost-centre levels (`cost_centers_info`, levels 0 to 8), and
  each company names what each level means.
- **Decision:** The title is the name the job list gives the employee's
  code. Both lists are optional parts of the employee bundle. When a list
  was not captured, titles are empty and one `missing_section` issue (an
  expected part of the data is absent) at `info` severity says so. A code
  missing from a captured list leaves the title empty with a
  `missing_lookup` warning (a needed lookup entry is absent). UKG Ready
  department, location and division stay "not mapped yet".
- **Reason:** The list is the provider's own name for its code, so the
  title is copied, not inferred. UKG's jobs configuration
  (`config/cost-center-jobs`) holds the same names, but live it sends them
  under `costCenterJobs`, not the documented `cost_center_jobs`. Choosing
  a cost-centre level for department or location would trust a title
  each company picks, which entry 33 rejected for isolved.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/JobCode/properties/jobTitle`
  and `#/paths/~1clientMaster~1v1~1getClientCodes`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/262` (jobs lookup),
  `#/schemas/41` (jobs configuration), `#/schemas/159/schema/properties/default_job`
  and `#/schemas/106/schema/properties/cost_centers_info`;
  `tests/test_employee_prismhr.py::test_job_titles_come_from_the_job_table`,
  `::test_job_table_is_optional`;
  `tests/test_employee_ukg_ready.py::test_job_titles_come_from_the_jobs_lookup`,
  `::test_jobs_lookup_and_tax_info_are_optional`.
- **Status:** Decided.

### 39. UKG Ready contractor flag comes from tax-info

- **Context:** UKG Ready records whether an employee is paid as a W-2
  employee, a 1099 contractor or on a draw in the employee's tax
  information. The read schema for that call (schema 166, tax-info) has
  `employee-tax-type` with three yes/no flags: `W2`, `_1099` and `DRAW`.
  Live, all 103 demo employees were W-2 only, and the response left out
  `fein` and `dba-company-name`, which the schema lists.
- **Decision:** The contractor flag copies `_1099`. Tax-info is an
  optional part of the employee bundle, one response per employee. The
  other flags and fields stay in `unmapped`. An employee with no tax-info
  response has an empty flag and a `missing_section` issue (an expected
  part of the data is absent) at `info` severity. A bundle with no
  tax-info at all gets one such issue.
- **Reason:** `_1099` is the flag UKG names for contractors, so it is
  copied rather than worked out from `W2` or the pay type. The two missing
  fields are optional and change nothing else (entry 58).
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/166/schema/properties/employee-tax-type/properties/_1099`;
  `src/normalization/bundle.py` (`PROVIDER_SPECS`, UKG Ready keys);
  `tests/test_employee_ukg_ready.py::test_contractor_flag_comes_from_tax_info`,
  `::test_jobs_lookup_and_tax_info_are_optional`.
- **Status:** Decided.

### 40. Employee coverage: which fields are not offered or not mapped yet

- **Context:** The employee coverage page lists every canonical employee
  field against each provider. Some cells pointed at a provider field
  whose meaning is unclear, or at data that is not what the canonical
  field means. isolved's `payRates[]` holds "alternate pay rates", each
  a name and a value with no period, and was null for every live
  employee. UKG Ready's `pay_info.job_last_changed` was set for 89 of
  103 live employees: it matched the hire, rehire or start date for 61
  and was later for 24, but fell before the hire date for 4.
- **Decision:**
  - isolved: the rate and its period are "not offered", since hourly
    and annual pay are separate fields that are mapped; `payRates[]`
    stays in `unmapped`. Division is "not offered" (entry 33).
  - UKG Ready: job start date stays "not mapped yet", as do department,
    location and division (entry 38). Pay frequency is mapped from the
    pay-period profile (entry 35).
  - PrismHR's benefit email and isolved's fax number are mapped
    (entry 32).
- **Reason:** Alternate rates are not the employee's rate. A date that
  sometimes comes before the hire date, with no documented meaning, is
  not safe to call the start of the current job.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeModel/properties/payRates`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/159/schema/properties/job_last_changed`;
  `src/normalization/field_map.py`;
  `tests/test_field_map.py::test_mapped_rows_are_filled_or_explain_the_gap`.
- **Status:** Decided.

### 41. Direct deposit coverage: six fields are not offered

- **Context:** The direct deposit coverage page lists the 11 value fields
  of a deposit line against each provider. Most exist in all three specs.
  Three gaps needed a call. UKG Ready lines carry a routing number but
  nothing labelled as the bank name. PrismHR lines have no sequence
  number. Neither PrismHR nor isolved lines have start or end dates. UKG
  lines do have a `name` field, which is a string with no description in
  the JSON schema and an integer in the XML schema.
- **Decision:** The page shows six cells as "not offered", each with its
  reason: UKG Ready bank name, PrismHR priority, and PrismHR and isolved
  effective start and end. UKG's `name` is not read as the bank name.
  Every other cell is "mapped"; none is "not mapped yet".
- **Reason:** `name` could as well be a label for the account, and its
  type is not even consistent, so calling it the bank name would be a
  guess (entry 1). PrismHR does not document its list order as the
  payment order (entry 53).
- **Evidence:** `src/normalization/deposit_field_map.py`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/137/schema/properties/deposits/items/properties/name`;
  `contracts/ukg-ready/reference-docs/res/__v2__companies__(cid)__employees__(aid)__direct-deposits.html`
  (XML schema);
  `tests/test_deposit_field_map.py::test_unmapped_rows_are_empty_in_golden_output`.
- **Status:** Decided.

### 42. Deduction coverage: which fields are not offered or not mapped yet

- **Context:** The deduction coverage page lists the 20 value fields of a
  deduction rule against each provider. isolved pay items carry only a
  code, figures and dates, and isolved's deductions call (which answered
  401) has the same fields. PrismHR names a payee only by ID; the name is
  on its payee setup record (`getPayee`, `payeeName`). UKG Ready caps a
  deduction per pay and per year only, and gives the employer side an
  annual maximum but no calculation.
- **Decision:** One PrismHR cell is "not mapped yet": frequency, because
  `period` needs the pay schedule (entry 63). Payee name is mapped from
  the payee setup (entry 70). Every gap in the fixtures is "not offered"
  with its reason:
  - PrismHR: employer match annual maximum and priority;
  - isolved: everything except code, amount, percent and dates (15
    cells), with the undescribed `scheduleOverride` not read as a
    frequency;
  - UKG Ready: category, monthly, quarterly and lifetime limits, and
    employer match method, amount and percent.
- **Reason:** "Not mapped yet" is kept for data the provider documents
  but the bundle or adapter does not use. Reading `scheduleOverride` as a
  frequency would be a guess (entry 1).
- **Evidence:** `src/normalization/deduction_field_map.py`;
  `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/PayeeDetails/properties/payeeName`;
  `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.Corestream.EmployeeDeductionModel`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/133` and
  `#/schemas/244` (deduction code lookup);
  `tests/test_deduction_field_map.py::test_unmapped_rows_are_empty_in_golden_output`.
- **Status:** Decided.

### 43. Payroll coverage: which fields are not offered or not mapped yet

- **Context:** The payroll coverage page lists the 34 value fields of a
  pay run, a paycheck and its lines against each provider. PrismHR sends
  something for every one of them. An isolved check has no status, no
  void date, no rate on an earning line and no type on a deduction line.
  A UKG Ready pay statement has no check number, no gross or net total,
  no void date, no category on an earning or deduction line, and no
  account number on a payment.
- **Decision:** Eleven cells are "not offered", each with its reason:
  - isolved: paycheck status, void date, earning rate and deduction
    category. The reissue date is not read as a void date;
  - UKG Ready: check number, gross pay, net pay, void date, earning
    category, deduction category and payment account last 4. `type_name`
    on an earning or deduction line names the line, not a category, so
    it is not read as one. Gross and net stay empty (entry 73).

  Every other cell is "mapped". None is "not mapped yet".
- **Reason:** "Not offered" is for a field the provider's payroll records
  do not have. Reading isolved's reissue date as a void date, or UKG
  Ready's `type_name` as a category, would be a guess (entry 1).
- **Evidence:** `src/normalization/payroll_field_map.py`;
  `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.CheckModel/properties/reissueCheckDate`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/364`;
  `tests/test_payroll_field_map.py::test_unmapped_rows_are_empty_in_golden_output`.
- **Status:** Decided.

### 44. Company coverage: which fields are not offered

- **Context:** The company coverage page lists the 27 value fields of a
  company, its contact details, and its tax ids, work locations and pay
  groups. PrismHR's client record has no general parent, one federal ID
  with no name or country, and pay groups with only a code and a
  description. An isolved legal has no status date, entity type, SIC
  code, email or website, and its `services` list is products rather
  than one service type. Its tax id has no name or country, its work
  locations have no end date, and its pay groups have no effective
  dates. The live legal also never sends a doing-business-as name or a
  NAICS code (entries 91 and 95). UKG Ready has no company profile and
  no work locations.
- **Decision:** Thirty-five cells are "not offered", each with its
  reason:
  - PrismHR: parent, tax id name, tax id country, and a pay group's
    active flag, effective start and effective end.
    `benefitParentClient` and `controlGroupCompany` are parents for one
    purpose, so neither is the company's parent;
  - isolved: status date, entity type, service type, SIC code, email,
    website, tax id name, tax id country, work location end date, and
    pay group effective start and end. `services` is not read as a
    service type;
  - UKG Ready: every profile and contact field except the EIN, and
    every work location field. Cost centres are not read as work
    locations.

  isolved's name and NAICS code are "mapped". The sample leaves them
  empty. Every other cell is "mapped". None is "not mapped yet".
- **Reason:** "Not offered" is for a field the provider's company
  records do not have. Reading a benefits parent as the company parent,
  or a product list as a service type, would be a guess (entry 1).
- **Evidence:** `src/normalization/company_field_map.py`;
  `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/ClientMaster/properties/benefitParentClient`;
  `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.LegalModel/properties/services`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/249`;
  `tests/test_company_field_map.py::test_unmapped_rows_are_empty_in_golden_output`.
- **Status:** Decided.

## Direct deposit normalization

### 45. A direct deposit record holds the core of one bank line

- **Context:** All three providers describe each split of an employee's
  pay into a bank account, but each wraps it in its own extras: prenote
  progress, what to do when pay falls short, how often the split applies,
  running totals, and links to related actions.
- **Decision:** Each bank line becomes one record with the bank name,
  routing number, last four digits of the account number, account type,
  how the amount is allocated, the order it is paid in (`priority`), its
  status, and the dates it applies (`effective`). Everything else,
  including prenote details, the shortfall rule, frequency, the PrismHR
  header status and `limit`, and UKG totals and links, stays in the
  record's `unmapped` section.
- **Reason:** These are the fields needed to say where the money goes and
  how much. The extras are named and shaped differently by each provider
  and are still available in `unmapped`.
- **Evidence:** `src/normalization/canonical/direct_deposit.py`;
  `docs/canonical/normalized-output.schema.json#/$defs/DirectDeposit`;
  `tests/test_direct_deposit_ukg_ready.py::test_prenote_and_frequency_stay_unmapped`.
- **Status:** Decided.

### 46. What a capture bundle holds for direct deposits

- **Context:** Each provider serves deposits from a different call.
  PrismHR returns them on the same employee call when asked for the
  `DirectDeposit` option; isolved and UKG Ready have one call per
  employee. isolved answers an employee with no deposits with a 404 and
  an empty body rather than an empty list.
- **Decision:** A direct-deposit bundle holds, per provider:
  - PrismHR: the `getEmployee` responses requested with
    `options=DirectDeposit` (`get_employee_direct_deposit`);
  - isolved: the employee list pages plus a map from employee ID to that
    employee's deposit array (`direct_deposits`), where a 404 is saved as
    an empty array;
  - UKG Ready: the employee list plus a map from account ID to the
    deposit response (`direct_deposits`).
  An employee missing from the map is reported as `missing_section`
  (an expected part of the data is absent) and gets no deposit records.
- **Reason:** Saving the 404 as an empty array keeps "has no deposits"
  apart from "was not captured", which is what the missing map entry
  means.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS`);
  `src/normalization/adapters/isolved.py` (`_IsolvedDepositMapper`);
  `src/normalization/adapters/ukg_ready.py` (`_UkgDepositMapper`).
- **Status:** Decided.

### 47. Only the last four digits of a bank account number are emitted

- **Context:** isolved and UKG Ready send bank account numbers in full.
  PrismHR masks them completely (`*****`) but sends the routing number in
  full. Some live UKG account numbers are only one to three digits long.
- **Decision:** The output keeps the last four digits
  (`account_number_last4`); the routing number and bank name are kept in
  full. A fully masked number gives an empty value and a `masked_value`
  issue (the provider hid the value). A number shorter than four digits
  also gives an empty value, with an `invalid_number` issue, since its
  last four digits would be the whole number. Account and routing numbers
  are redacted wherever provider data is repeated (entry 16).
- **Reason:** Four digits are enough to tell accounts apart without
  putting a usable account number in an output file. A routing number
  identifies a bank, not a person.
- **Evidence:** `src/normalization/adapters/_common.py` (`Collector.last4`);
  `tests/test_direct_deposit_prismhr.py::test_one_account_number_is_masked`;
  `tests/test_direct_deposit_isolved.py::test_account_numbers_are_reduced_to_last_four`.
- **Status:** Decided.

### 48. How each provider's allocation maps to one list of methods

- **Context:** A deposit line takes a fixed amount, a percentage, or
  whatever is left. PrismHR (`method`) and UKG Ready (`calc_method`) say
  which with a code; their specs define every code. PrismHR also puts
  both amounts and percentages in one `amount` field.
- **Decision:** `allocation.method` takes one of `fixed_amount`,
  `percent` (percentage of an unstated base), `percent_of_gross`,
  `percent_of_net`, `percent_of_remainder` or `remainder`:
  - PrismHR: `F` and `FS` are fixed amounts, `P` is percent, `PN` is
    percent of net, `B` is the remainder;
  - UKG Ready: `FLAT_AMOUNT`, `GROSS_EARNING`, `NET_PAY`,
    `DIRECT_DEPOSIT_PER_OF_REMAINDER` and `FULL` map in that order.
  The figure goes into `allocation.amount` or `allocation.percent` as the
  method says. When the figure does not fit the method, such as an amount
  on a remainder line or no amount on a fixed line, an
  `inconsistent_allocation` warning (amount and percentage do not fit the
  method) is raised and the figure is left in `unmapped`, or set empty if
  it is missing.
- **Reason:** One list lets a reader compare splits across providers. A
  figure that contradicts its method is not moved to a field that would
  give it a meaning the provider did not.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/AchVoucher/properties/method`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/137/schema/properties/deposits/items/properties/calc_method/properties/type/enum`;
  `src/normalization/adapters/prismhr.py` (`DEPOSIT_METHOD`);
  `src/normalization/adapters/ukg_ready.py` (`DEPOSIT_CALC_METHOD`).
- **Status:** Decided.

### 49. isolved allocation comes from which field is set

- **Context:** isolved has no method code. A line has either an `amount`
  or a `percent`, and the spec says `sequenceNumber` 0 is "Net Pay", the
  line that receives the rest.
- **Decision:** A line with sequence 0 is `remainder`, with the label
  "Net Pay (sequence 0)". Otherwise a line with only an amount is
  `fixed_amount` and one with only a percent is `percent`. A line with
  both, or with neither, gets `unknown` and an `inconsistent_allocation`
  warning. The method's raw value is empty because isolved sent no code.
- **Reason:** The spec states the two fields exclude each other and
  defines sequence 0, so the method follows from the data without a
  guess. isolved does not say what the percentage is of, so it stays the
  plain `percent`.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeDirectDepositModel/properties/sequenceNumber`;
  `src/normalization/adapters/isolved.py` (`_IsolvedDepositMapper._allocation`);
  `tests/test_direct_deposit_isolved.py::test_amount_and_percent_follow_the_field_that_is_set`.
- **Status:** Decided.

### 50. isolved account type and status labels allowed so far

- **Context:** isolved's spec describes `accountType` and `status` only
  as free-text descriptions, with no list of values. The live demo
  company returned `Checking` as the only account type and `Active` and
  `Inactive` as statuses. Frequency was always `Every Pay`.
- **Decision:** Under entry 15's rule (c), `Checking` maps to `checking`,
  and `Active` and `Inactive` map to `active` and `inactive`, matched
  exactly. Any other label stays `unknown` with an `unmapped_label` issue
  (a label with no shared meaning yet). Frequency is not mapped and stays
  in `unmapped`.
- **Reason:** These are the only labels seen, and each says plainly what
  it means. No savings label was seen live, so none is recognised.
- **Evidence:** `src/normalization/adapters/isolved.py`
  (`DEPOSIT_ACCOUNT_TYPE`, `DEPOSIT_STATUS`);
  `tests/test_direct_deposit_isolved.py::test_pending_status_stays_raw`.
- **Status:** Decided.

### 51. PrismHR account type `IP` is instant pay, not a pay card

- **Context:** PrismHR's spec lists the account types it returns as `C`
  "(checking account or pay card)", `S` "(savings account)" and `IP`
  "(instant pay)". Instant pay is easy to mistake for a pay card, which
  is a different thing.
- **Decision:** `C` maps to `checking`, `S` to `savings` and `IP` to
  `instant_pay`. There is no pay card value, because PrismHR files pay
  cards under `C`.
- **Reason:** The spec text says `IP` is instant pay; calling it a pay
  card would change what the code means.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/AchVoucher/properties/accountType`;
  `src/normalization/adapters/prismhr.py` (`ACCOUNT_TYPE`);
  `tests/test_direct_deposit_prismhr.py::test_code_tables_quote_the_spec_descriptions`.
- **Status:** Decided.

### 52. PrismHR `FS` and `PN` lose a detail when mapped

- **Context:** PrismHR's `FS` is "fixed, skip if can't take full amount",
  and `PN` is "percentage of net after fixed", meaning the percentage is
  taken after the fixed-amount lines are paid.
- **Decision:** `FS` maps to `fixed_amount` and `PN` to `percent_of_net`.
  The extra detail is kept only in the method's raw code.
- **Reason:** The shared list has no value for a skip rule or for the
  order in which lines are paid, and adding one for a single provider
  code would make the list harder to compare.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/AchVoucher/properties/method`;
  `src/normalization/adapters/prismhr.py` (`DEPOSIT_METHOD`).
- **Status:** Decided.

### 53. PrismHR deposit lines are identified by their position

- **Context:** PrismHR deposit lines (`achVoucher`) have no ID or
  sequence number. Each line can also be limited to certain kinds of pay
  run (`voucherTypeOverride`, any mix of R regular, V vacation and S
  supplemental). One live employee had two remainder lines, one for
  regular pay and one for supplemental pay.
- **Decision:** A line's ID is its position in the list, starting at 0,
  so the record key ends in `:dd:0`, `:dd:1` and so on. `priority` is
  empty. The pay-run limit stays in the line's `unmapped` section, as
  entry 45 says for frequency, so two remainder lines for one employee
  can appear; the limit there tells them apart.
- **Reason:** The position is the only stable handle in the response. It
  changes if PrismHR reorders or removes a line, so it should not be
  used to match records across captures. PrismHR does not say the list
  order is the payment order.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/AchVoucher/properties/voucherTypeOverride`
  (a subset of `DirectDeposit/properties/voucherType`, which defines R,
  S and V); `src/normalization/adapters/prismhr.py` (`_PrismDepositMapper.map`).
- **Status:** Decided.

### 54. PrismHR header status is not applied to each line

- **Context:** PrismHR sends a header for the whole direct deposit setup,
  with its own status (`achStatus`), next to a status on each line. In
  the live demo company every line was `D` (active) under an `A` header,
  employees with no setup had an empty `achStatus`, and the one `I`
  (inactive) header had no lines.
- **Decision:** A record's status comes from its line only. The header
  fields are copied into every line's `unmapped` section.
- **Reason:** The spec does not say how the header status combines with
  a line status, so combining them would be a guess.
- **Evidence:** `src/normalization/adapters/prismhr.py`
  (`_PrismDepositMapper.map`);
  `tests/test_direct_deposit_prismhr.py::test_header_fields_ride_along_in_unmapped`.
- **Status:** Decided.

### 55. UKG Ready "reserve live check" lines are emitted without a bank

- **Context:** UKG Ready deposit lines have a `type` of either
  `DIRECT_DEPOSIT` or `RESERVE_LIVE_CHECK`. The second keeps part of the
  pay as a paper check and has no bank account.
- **Decision:** Both kinds become records. A reserve line has empty bank
  fields, and its `type` stays in `unmapped`.
- **Reason:** It is still a split of the employee's pay with an amount
  and an order, and dropping it would make the other lines look like the
  whole of the pay.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/137/schema/properties/deposits/items/properties/type`;
  `src/normalization/adapters/ukg_ready.py` (`_UkgDepositMapper._line`).
- **Status:** Decided.

### 56. UKG Ready's employee deposit call is past its end of support

- **Context:** UKG's table of deprecated operations lists
  `GET v2/companies/{cid}/employees/{account_id}/direct-deposits` with
  no replacement and an end of support of January 29, 2026. The live
  demo company still answers the call after that date, without needing
  the `X-End-of-Support-Timeline` header.
- **Decision:** The bundle uses this call, since it is the only one that
  lists an employee's deposits.
- **Reason:** No replacement is documented. If UKG turns the call off,
  the bundle cannot be captured, but saved bundles still normalize.
- **Evidence:** `contracts/ukg-ready/reference-docs/Version 2 resources and operations.html`
  (the `employees/{account_id}/direct-deposits` row);
  `src/normalization/bundle.py` (`PROVIDER_SPECS`, UKG Ready keys).
- **Status:** Decided.

### 57. UKG Ready open-ended dates are kept as sent

- **Context:** Live UKG lines carry `active_from` 1900-12-31 and
  `active_to` 2099-12-31, which look like stand-ins for "no start" and
  "no end". One inactive line had a real end date.
- **Decision:** `effective` holds both dates exactly as sent.
- **Reason:** UKG does not document these as placeholders, so treating
  them as empty would be a guess. A reader can still filter them out.
- **Evidence:** `src/normalization/adapters/ukg_ready.py`
  (`_UkgDepositMapper._line`).
- **Status:** Decided.

### 58. Where live deposit data differs from the specs

- **Context:** The live demo companies did not return everything the
  specs describe:
  - UKG Ready omits `amount`, `percentage` and `name` when unset, and
    never returned `description`, `currency`, the prenote dates or the
    running totals. Its label for `FLAT_AMOUNT` is "Flat $ Amount", not
    the documented "Flat Amount".
  - isolved's inactive lines had no `sequenceNumber`, though the spec
    marks it required, and one also had no amount or percent. No line
    had `links`.
  - PrismHR sent `transitNum` in full and every `accountNum` masked.
- **Decision:** A missing field is read as empty and raises no issue of
  its own. The isolved line with neither amount nor percent gets the
  `inconsistent_allocation` warning from entry 49. The UKG label is kept
  as sent, and the amount currency defaults to USD.
- **Reason:** These gaps do not change what the remaining fields mean,
  and reporting every absent optional field would bury the issues that
  do.
- **Evidence:** `src/normalization/adapters/isolved.py` (`_IsolvedDepositMapper._allocation`);
  `src/normalization/adapters/ukg_ready.py` (`_UkgDepositMapper._allocation`).
- **Status:** Decided.

## Deduction normalization

### 59. A deduction record holds one recurring rule

- **Context:** Each provider stores the deductions set up for an
  employee: what is taken, how it is worked out, how often, up to what
  limit, and sometimes an employer match and a third party who receives
  the money. None of them sends a status for the rule, only start and
  stop dates.
- **Decision:** Each rule becomes one record with its code and name, a
  category (such as `section_125` or `garnishment`), how it is
  calculated (method plus an amount or a percent), frequency, limits per
  pay and per month, quarter, year or lifetime, employer match, payee,
  `priority` and the dates it applies (`effective`). There is no status
  field and no amount actually taken; those amounts are deduction lines
  on each paycheck (entry 71). Anything else stays in `unmapped`.
- **Reason:** These fields say what will come out of the next paycheck
  and who receives it. A status would have to be worked out from dates,
  which a reader can do as easily. An amount taken needs its pay run as
  context, which a rule does not have.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize);
  `src/normalization/canonical/deduction.py`;
  `docs/canonical/normalized-output.schema.json#/$defs/Deduction`;
  `tests/test_canonical_model.py::test_deduction_fields_are_checked`.
- **Status:** Decided.

### 60. What a capture bundle holds for deductions

- **Context:** PrismHR returns deductions from `getDeductions`, one call
  per employee. isolved and UKG Ready also need one call per employee,
  and UKG Ready needs a second call per deduction for its amounts.
- **Decision:** A deduction bundle holds, per provider:
  - PrismHR: a map from employee ID to its `getDeductions` response
    (`get_deductions`), plus the employee list and a map from payee ID
    to its `getPayee` response (`get_payee`, entry 70) if captured;
  - isolved: the employee list pages plus a map from employee ID to its
    pay item array (`pay_items`, entry 65);
  - UKG Ready: the employee list, a map from account ID to the list
    response (`deductions`) and a map from deduction ID to the detail
    response (`deduction_detail`).

  An employee missing from the map is reported as `missing_section` (an
  expected part of the data is absent) at `info` severity and gets no
  records. UKG Ready's deduction code lookup is not part of the bundle,
  because the schema requires every list line to carry the code's name.
  The lookup answers for the live demo company (43 codes), but the list
  calls do not (entry 67), so whether the two agree cannot be checked.
- **Reason:** This matches the deposit bundles (entry 46), so one capture
  run can serve both. The lookup would only repeat names the list sends.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS`);
  `contracts/ukg-ready/reference-schemas.json#/schemas/132` (`deduction`
  requires `code` and `name`) and `#/schemas/244` (the lookup);
  `tests/test_bundle.py::test_deduction_keys_per_provider`;
  `src/normalization/adapters/ukg_ready.py` (`_UkgDeductionMapper`).
- **Status:** Decided.

### 61. PrismHR deduction codes are explained on a different record

- **Context:** On PrismHR's per-employee deduction, `deductionType` (the
  kind of deduction) is described only as "defined by the service
  provider" and `deductionMethod` (how it is calculated) as "calculation
  method". The codes are listed on the deduction code setup record,
  `DeductionCodeDetail`, as entry 34 found for gender.
- **Decision:** Category and method are mapped using the code lists on
  `DeductionCodeDetail`, and the label shown is the one given there. A
  code not on the list stays `unknown` with an `undocumented_code` issue
  (a code with no documented meaning).
- **Reason:** It is the same code set on the same deduction, and the
  lists are explicit.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/DeductionCodeDetail/properties/deductionType/description`
  and `.../calculationMethod/description`;
  `src/normalization/adapters/prismhr.py` (`DEDUCTION_TYPE`,
  `DEDUCTION_METHOD`);
  `tests/test_deduction_prismhr.py::test_code_tables_quote_the_spec_descriptions`.
- **Status:** Decided.

### 62. PrismHR's 29 calculation methods are grouped into eight

- **Context:** PrismHR lists 29 calculation methods, many of them
  variants (percentage of gross, of straight pay, of retirement
  earnings; rate times hours worked, paid or certified).
- **Decision:** `F` is `fixed_amount` and `PG` is `percent_of_gross`.
  The other percentage-of-earnings codes are `percent_of_earnings`, the
  rate-times-hours codes are `rate_per_hour`, `G` and `K` are the
  garnishment and retirement plan rules, and `U` and `RT` are
  `table_lookup`. The rest, such as percentage of pay rate or Ohio JEDD
  tax, are `other`: documented, but none of the shared methods. The
  exact code and its label stay on the method.
- **Reason:** A reader can compare providers on the broad method and
  still see PrismHR's exact variant in the raw code.
- **Evidence:** `src/normalization/adapters/prismhr.py`
  (`_METHOD_GROUPS`, `DEDUCTION_METHOD`).
- **Status:** Decided.

### 63. PrismHR frequency and order are not mapped

- **Context:** PrismHR's `period` lists the pay periods of the month
  when a deduction is taken (for example `12345`). It is not one of the
  shared frequencies. PrismHR sends no order for its deductions.
- **Decision:** `frequency` and `priority` are empty for PrismHR, and
  `period` stays in `unmapped`. A line's ID is its position, as for
  deposits (entry 53).
- **Reason:** Turning a list of period numbers into "every pay" or
  "monthly" depends on the pay schedule, which the deduction call does
  not return.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/EmployeeDeductions-Deduction/properties/period`;
  `src/normalization/adapters/prismhr.py` (`_PrismDeductionMapper._line`).
- **Status:** Decided.

### 64. PrismHR amount, maximum and match follow their switch fields

- **Context:** PrismHR uses one `amount` for both amounts and
  percentages, chosen by `usePercent`. `maximum` caps the deduction over
  the period named in `basis`. `matchAmount` is a flat amount or a
  percent, chosen by `matchMethod`.
- **Decision:** The figure goes to the amount or the percent as the
  switch says. `limit` is the per-pay limit and `maximum` fills the
  monthly, quarterly, annual or lifetime slot. A `usePercent` that is
  neither a boolean nor `T` or `F` gives an `out_of_schema_value` issue
  (a value outside the documented set). A `maximum` with an empty
  `basis` gives an `inconsistent_allocation` warning   (the figures do not
  fit together). In both cases the figure stays in `unmapped`. An amount
  is read together with the method: for the rate-times-hours and
  per-ten-thousand methods it is a rate, not the sum taken from each
  paycheck.
- **Reason:** A figure is only placed where its switch says it belongs;
  without the switch, its meaning would be a guess. PrismHR has one
  `amount` for every method, and the method code beside it says how it
  is applied.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/EmployeeDeductions-Deduction/properties/basis`
  and `.../amount` ("deduction amount");
  `src/normalization/adapters/prismhr.py` (`_PrismDeductionMapper._line`);
  `tests/test_deduction_prismhr.py::test_use_percent_accepts_booleans_and_spec_letters`.
- **Status:** Decided.

### 65. isolved deductions come from pay items

- **Context:** isolved's spec has a deductions call for each employee,
  but it answered 401 (not authorized) for every employee of the demo
  company. The pay items call worked and lists earnings, memo
  calculations and deductions together, marked by `payItemType`.
- **Decision:** isolved deductions are read from pay items. Only items
  of type `Deduction` become records; `Earning` and `Memo Calc` items
  are skipped without an issue. Any other type is skipped with an
  `unmapped_label` issue (a label with no shared meaning yet). isolved
  gives no category, method or frequency, so those are empty.
- **Reason:** It is the only call that returned deduction setup. The
  deductions call can replace it once access is granted.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeePayItemModel`;
  `src/normalization/adapters/isolved.py` (`_IsolvedDeductionMapper`);
  `tests/test_deduction_isolved.py::test_medical_amount_and_retirement_percent`.
- **Status:** Decided.

### 66. isolved calculation parameters: `Amount` and `Percent` are recognised

- **Context:** An isolved pay item carries its figures as a list of
  parameters, each with a label (`paramType`) and a value. The spec does
  not list the labels. Live deductions used `Amount`, `Percent` and
  `Amount2`, all set to 0, and some items carried both `Amount` and
  `Percent`.
- **Decision:** The first `Amount` fills the amount and the first
  `Percent` fills the percent; an item with both shows both, with no
  issue. Any other label, such as `Amount2`, stays in `unmapped` and is
  reported once per bundle as `unmapped_label`.
- **Reason:** These two labels say plainly what they hold. isolved sends
  no method that would say which of the two applies, so both are copied
  rather than one being dropped. `Amount2` has no stated meaning.
- **Evidence:** `src/normalization/adapters/isolved.py`
  (`CALC_PARAM_SLOTS`);
  `tests/test_deduction_isolved.py::test_medical_amount_and_retirement_percent`.
- **Status:** Decided.

### 67. UKG Ready deductions join a list call and a detail call, built from the docs

- **Context:** UKG Ready's employee deduction list gives only the code,
  name, dates and order. The amount, frequency and limits are on a
  second call for each deduction. Both calls answered "Unresolvable URL"
  (404) for every employee of the demo company; the reference pages tag
  them `dev`, not `v2`.
- **Decision:** Each list line is joined with its detail by deduction
  ID. A line with no detail is still emitted with the list fields and a
  `missing_section` warning. The calculation method type has no
  documented values, so it stays `unknown` with its label, reported once
  per distinct type. Open-ended dates such as 9999-12-31 are kept as
  sent (entry 57). The mapping and the test data follow the reference
  pages only.
- **Reason:** The detail is where the rule is. Building from the docs
  means a bundle captured once the calls are enabled will normalize,
  though its shape has not been checked against live data.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/132`
  and `#/schemas/133`;
  `src/normalization/adapters/ukg_ready.py` (`_UkgDeductionMapper`);
  `tests/test_deduction_ukg_ready.py::test_amount_percent_and_limits_join_from_detail`.
- **Status:** Decided.

### 68. UKG Ready frequencies with no shared counterpart are `other`

- **Context:** UKG Ready's `ee_frequency` (how often the employee
  deduction is taken) has eleven documented values. Most have a shared
  counterpart, but "every scheduled month odd pay", "even pay" and
  "holiday table" do not.
- **Decision:** Every pay and every scheduled pay are `every_pay`, every
  other scheduled pay is `every_other_pay`, and monthly, quarterly,
  annual, manual and benefit plan map to their namesakes. The three
  without a counterpart are `other`. A value outside the documented
  list stays `unknown` with an `out_of_schema_value` issue. The raw code
  keeps the difference between every pay and every scheduled pay.
- **Reason:** `other` says the value is documented but not comparable,
  which `unknown` would not. UKG does not say how every pay and every
  scheduled pay differ, so they share the closest value, as PrismHR's
  `FS` does with fixed amounts (entry 52).
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/133/schema/properties/ee_frequency/properties/type/enum`;
  `src/normalization/adapters/ukg_ready.py` (`DEDUCTION_FREQUENCY`);
  `tests/test_deduction_ukg_ready.py::test_frequency_table_covers_the_schema_enum_exactly`,
  `test_frequencies_without_a_counterpart_map_to_other`.
- **Status:** Decided.

### 69. Where live deduction data differs from the specs

- **Context:** The live demo companies did not match the specs:
  - PrismHR sends `usePercent` as a JSON boolean, not `T` or `F`.
    Benefit plan lines carry only ten fields, no dates and mostly a zero
    amount; `limit`, `maximum` and `stopDate` never appeared.
  - isolved pay items were the same 41 items for every employee, with
    negative IDs, zero values and no dates, which looks like a template.
    Some had no `payItemCode`, and `balance` is not in the spec.
  - UKG Ready's deduction calls could not be reached (entry 67), and
    isolved's deductions call was not authorized (entry 65). Trying both
    again gave the same answers.
- **Decision:** Both forms of `usePercent` are accepted. Benefit plan
  lines are emitted like any other. An isolved item with no code keeps
  its name, and `balance` stays in `unmapped` with one
  `spec_live_mismatch` issue (live data differs from the spec).
- **Reason:** These differences do not change what the other fields
  mean. Whether isolved's items are real assignments can only be
  checked with access to the deductions call.
- **Evidence:** `tests/test_deduction_prismhr.py::test_use_percent_accepts_booleans_and_spec_letters`;
  `src/normalization/adapters/isolved.py` (`_IsolvedDeductionMapper._line`).
- **Status:** Decided.

### 70. PrismHR payee names come from the payee setup

- **Context:** A PrismHR deduction rule names the third party that
  receives the money only by an ID (`cutbackPayeeCode`). The name is on
  a separate payee setup call (`getPayee`), whose `payeeName` is the
  "name of the payee". On the demo, every payee ID was empty, and
  `getPayee` answered 403 "not authorized for the method specified",
  which the spec says happens when the call is not enabled for the user.
- **Decision:** The payee shows the ID and the name `getPayee` gives for
  it. The payee setup is an optional part of the deduction bundle, one
  response per payee ID. If it was not captured, names are empty and one
  `missing_section` issue (an expected part of the data is absent) at
  `info` severity says so. A payee ID with no matching payee, including
  an error response, keeps its ID with an empty name and a
  `missing_lookup` warning (a needed lookup entry is absent) that quotes
  the provider's error.
- **Reason:** The name is copied from PrismHR's own payee record, so
  nothing is inferred. Live data could not confirm it, so the mapping
  rests on the spec and the synthetic fixture.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/PayeeDetails/properties/payeeName`
  and `#/paths/~1system~1v1~1getPayee`;
  `src/normalization/adapters/prismhr.py` (`_PrismDeductionMapper._payee`);
  `tests/test_deduction_prismhr.py::test_payee_name_comes_from_the_payee_setup`,
  `::test_payee_missing_from_payee_setup_keeps_the_id`,
  `::test_payee_setup_is_optional`.
- **Status:** Decided.

## Payroll normalization

### 71. A pay run and a paycheck are separate records

- **Context:** Every provider sends a list of pay runs (PrismHR
  batches, isolved run history, UKG Ready payrolls) and, for each run,
  one paycheck per employee with its earnings, taxes, deductions and
  payments. A paycheck can be captured without its run.
- **Decision:** `--entity payroll` writes two lists. `pay_runs` holds
  one record per run: type, status, pay date, period, description and
  pay group. `paychecks` holds one record per employee paycheck, with
  the keys of its employee, company and run, the copied totals, and
  five lists of lines: earnings, taxes, deductions, employer
  contributions and payments. A tax line holds both the employee and
  the employer side.
- **Reason:** Flat lists match the other data types and keep a
  paycheck readable when its run is missing. A paycheck links to its
  run by key, as a deposit links to its employee.
- **Evidence:** `src/normalization/canonical/payroll.py`;
  `docs/canonical/normalized-output.schema.json#/$defs/PayRun` and
  `#/$defs/Paycheck`;
  `tests/test_canonical_model.py::test_payroll_fields_are_checked`;
  `tests/test_payroll_*.py::test_records_link_to_runs_employees_and_company`.
- **Status:** Decided.

### 72. What a capture bundle holds for payroll

- **Context:** Each provider needs a run list plus one or more calls per
  run or per employee to get the paychecks, and some need a detail call
  per paycheck for the lines.
- **Decision:** A payroll bundle holds, per provider:
  - PrismHR: the `getBatchListByDate` response, a map from batch ID to
    the pages of `getPayrollVoucherForBatch`, and optionally a map from
    batch ID to `getBatchInfo`;
  - isolved: the employee list pages, a map from pay group ID to its
    run history, a map from employee ID to its check pages, and
    optionally a map from check ID to the check detail;
  - UKG Ready: the payroll list, a map from payroll ID to its pay
    statement list, a map from statement ID to the statement detail,
    and optionally the EIN lookup.

  A missing entry is reported as `missing_section` (an expected part of
  the data is absent) and the records that need it are emitted with
  what is left.
- **Reason:** This follows the deposit and deduction bundles (entries
  46 and 60), so one capture run can serve every data type.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS`);
  `tests/test_bundle.py::test_payroll_keys_per_provider`,
  `test_one_bundle_can_feed_every_entity`.
- **Status:** Decided.

### 73. Gross and net pay are copied, never summed

- **Context:** PrismHR and isolved send a gross and a net total on
  each paycheck. UKG Ready pay statements have neither: only lines.
- **Decision:** `gross_pay` and `net_pay` are copied from the provider
  totals. For UKG Ready they are empty, and one `missing_section` issue
  at `info` severity per bundle says so.
- **Reason:** A sum of lines can differ from what was paid (memo
  earnings, discarded lines, rounding), so a computed total could
  mislead. One issue per bundle is enough because every statement
  lacks the totals.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/364`;
  `tests/test_payroll_ukg_ready.py::test_no_totals_and_live_only_fields`.
- **Status:** Decided.

### 74. Year-to-date figures are not modelled

- **Context:** isolved repeats month-, quarter- and year-to-date figures
  on every check line and benefit. PrismHR and UKG Ready lines carry
  only the paycheck's own figures.
- **Decision:** Only the figures for the paycheck itself are mapped.
  The running totals stay in each line's `unmapped`.
- **Reason:** They describe the employee's year, not the paycheck, and
  can be rebuilt from the paychecks.
- **Evidence:** `src/normalization/adapters/isolved.py` (`_paycheck`)
  (the `ytd*` fields stay in `unmapped`).
- **Status:** Decided.

### 75. PrismHR batch statuses are grouped into four

- **Context:** PrismHR documents 20 batch status codes, only in the
  description of its `getBatchStatus` call, as a table of code and
  meaning. Live batches used five of them.
- **Decision:** Time sheet and calculation steps are `open`,
  finalization, wire transfer and printing are `submitted`, `COMP` is
  `completed`, and the four codes that end "with errors" or "rejected"
  are `failed`. Two of those, `POST.FAIL` and `PRINTFAIL`, say the
  finalization or printing step finished but with errors. The label
  shown is the table's description. A code not in the table stays
  `unknown` with an `undocumented_code` issue (a code with no
  documented meaning).
- **Reason:** Four groups let a reader compare runs across providers;
  the exact step stays in the raw code and label. A run that finished
  with errors needs attention, which `failed` says and `submitted`
  would hide.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/paths/~1payroll~1v1~1getBatchStatus/get/description`;
  `src/normalization/adapters/prismhr.py` (`BATCH_STATUS`);
  `tests/test_payroll_prismhr.py::test_code_tables_quote_the_spec_descriptions`.
- **Status:** Decided.

### 76. PrismHR voucher status, benefits and payments

- **Context:** A PrismHR voucher's `status` is described only as
  "voucher status, such as printed", and every live voucher sent
  `PRNT`. Its `benefit[]` list repeats amounts already in `deduction[]`
  and `employerContributions[]`: in every live voucher with benefits,
  each benefit row has one employer contribution row equal to its
  premium less the employee share. The check amount is a field, while
  direct deposits are a list.
- **Decision:** Voucher status stays `unknown` with one
  `undocumented_code` issue per distinct code. `benefit[]` stays in
  `unmapped`. A check payment line is added when the voucher has a check
  number or a nonzero check amount, and each direct deposit entry
  becomes its own payment line with the last four account digits.
- **Reason:** No status code is documented. Mapping `benefit[]` would
  count the same money twice. A zero check amount with no check number
  is not a payment.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/PayrollVoucher/properties/status`;
  `src/normalization/adapters/prismhr.py` (`VOUCHER_STATUS`);
  `tests/test_payroll_prismhr.py::test_printed_status_is_reported_once`.
- **Status:** Decided.

### 77. isolved payroll comes from legal 5797

- **Context:** The isolved demo client has two legal companies. Legal
  5806, used for the other data types, has one pay group whose run
  history answers 404 and no employee checks. Legal 5797 has 231 runs
  and 21 employees with checks.
- **Decision:** Live payroll captures use legal 5797. The test fixture
  keeps the 5806 company key so it joins the synthetic employees.
- **Reason:** 5806 has no payroll data to normalize.
- **Evidence:** `tests/fixtures/isolved/payroll-bundle.json`
  (`request.legal_id`); README "Live demo data".
- **Status:** Decided.

### 78. isolved checks join runs on pay date and run number

- **Context:** An isolved check does not carry the ID of its run. It
  has a check date and `payrollRunNumber`; a run has a pay date and
  `runNumber`. Live, every check matched exactly one run this way.
- **Decision:** A check gets the key of the run with the same pay date
  and run number. When no captured run matches, or two do, the run key
  is empty and a `missing_section` warning says which.
- **Reason:** It is the only link the data offers. Guessing between two
  matching runs could attach a check to the wrong one.
- **Evidence:** `src/normalization/adapters/isolved.py` (`_run_for`);
  `tests/test_payroll_isolved.py::test_records_link_to_runs_employees_and_company`.
- **Status:** Decided.

### 79. isolved run type, run status and check type labels allowed so far

- **Context:** isolved sends English labels, not codes, for a run's
  type and status and a check's type, and the spec lists no values.
  Live runs were "Regular Payroll" or "Data Conversion", "Completed
  Payroll Run" or "Payroll Not Processed"; live checks were all
  "Adjustment". Every live check came from a "Data Conversion" run;
  the "Regular Payroll" runs were all "Payroll Not Processed" and had
  no checks.
- **Decision:** "Regular Payroll" is `regular`; "Completed Payroll
  Run" is `completed` and "Payroll Not Processed" is `open`;
  "Adjustment" is `adjustment`. Any other label stays `unknown` with
  one `unmapped_label` issue (a label with no shared meaning yet) per
  distinct label. "Data Conversion" is left off because it describes
  how the data was loaded, not the kind of run, and "Regular" for checks
  because it never appeared live. So every live run with checks has an
  `unknown` type.
- **Reason:** Only labels seen live are allowed, as for employee status
  and deposit labels (entries 21 and 50). The issue on "Data
  Conversion" keeps it visible that these runs are not ordinary pay
  runs.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.PayrollRunHistoryModel/properties/payrollRunType`;
  `src/normalization/adapters/isolved.py` (`RUN_TYPE`, `RUN_STATUS`,
  `CHECK_TYPE`);
  `tests/test_payroll_isolved.py::test_allowlists_cite_the_spec_fields`.
- **Status:** Decided.

### 80. isolved payments come from per-account deposits when listed

- **Context:** An isolved check has a check amount, a direct deposit
  total and, on some checks, a list of deposit accounts with their
  amounts. The total and the list describe the same money. Live checks
  had a zero deposit total and no deposit list, so only the check
  amount was seen; the deposit rules follow the spec.
- **Decision:** A nonzero check amount becomes a check payment line.
  When the check lists deposit accounts, each becomes a payment line
  with the last four account digits; otherwise a nonzero deposit total
  becomes one line. A zero amount stays in `unmapped`.
- **Reason:** Using both the total and the list would count a deposit
  twice. The list says more, so it wins when present.
- **Evidence:** `src/normalization/adapters/isolved.py` (`_payments`);
  `tests/test_payroll_isolved.py::test_one_check_has_no_detail`.
- **Status:** Decided.

### 81. isolved memo earnings stay earnings

- **Context:** Live isolved checks list the employer's 401(k) match and
  medical, dental and HSA payments among the earnings, flagged
  `isMemoEarning`. They are not paid to the employee.
- **Decision:** They stay earning lines with the category `memo`. The
  employer contribution on the check detail's benefits becomes a
  separate employer contribution line, so the employer's medical and
  dental share can appear in both (live, "ER Dental" 10.00 beside
  "Dental Pre-Tax 125" 10.00). The 401(k) match is not among the live
  benefits, so it appears only as a memo earning.
- **Reason:** Moving memo earnings would hide that isolved lists them
  as earnings; the `memo` category lets a reader leave them out of pay.
- **Evidence:** `src/normalization/adapters/isolved.py` (`_paycheck`).
- **Status:** Decided.

### 82. UKG Ready payroll and statement statuses

- **Context:** UKG Ready's schemas list nine payroll statuses and five
  pay statement statuses. Live, every payroll and statement was `OPEN`.
- **Decision:** For payrolls, `NEW` and `OPEN` are `open`, `CLOSED` and
  `SUBMITTED` are `submitted`, `FINALIZED` is `completed`, and the four
  `*_FAILED` values are `failed`. Statement statuses map to their
  namesakes, with `NEW` as `open`. A value outside the lists stays
  `unknown` with an `out_of_schema_value` issue (a value outside the
  documented set).
- **Reason:** The payroll groups match PrismHR's (entry 75); the
  statement statuses are already the shared ones.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/358/schema/properties/payrolls/items/properties/status/enum`
  and `#/schemas/364/schema/properties/status/enum`;
  `tests/test_payroll_ukg_ready.py::test_status_tables_cover_the_schema_enums_exactly`.
- **Status:** Decided.

### 83. UKG Ready deduction lines are split by side

- **Context:** A UKG Ready statement deduction line carries both an
  employee amount and an employer amount, either of which may be zero.
- **Decision:** A nonzero employee amount becomes a deduction line and
  a nonzero employer amount an employer contribution line, with the
  same code; a zero side stays in `unmapped`. A line with both sides
  zero is still a deduction line, with an empty amount; nine live lines
  were like this. A discarded line ("Deduction (Discarded)") is still
  emitted, with its type left in `unmapped`.
- **Reason:** The other providers keep the two sides apart, so the
  split makes the lists comparable. Dropping discarded or all-zero
  lines would hide what the provider sent.
- **Evidence:** `src/normalization/adapters/ukg_ready.py` (`_deductions`).
- **Status:** Decided.

### 84. UKG Ready earnings hours are milliseconds

- **Context:** UKG Ready's statement earnings `hours` is an integer
  with no documented unit. Live, overtime hours times 1.5 times the base
  rate gave the line amount only when hours were read as milliseconds.
- **Decision:** `hours` is converted from milliseconds to hours, as an
  approved exception to entry 5. A value that is not a number stays
  empty with an `invalid_number` issue.
- **Reason:** The live check is exact, and every other UKG duration is
  in milliseconds.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/364/schema/properties/earnings/items/properties/hours`;
  `src/normalization/adapters/ukg_ready.py` (`_ms_to_hours`).
- **Status:** Decided.

### 85. Where live payroll data differs from the specs

- **Context:** The live demo companies did not match the specs:
  - PrismHR lists vouchers under `payrollVoucher`, not
    `payrollVouchers`, and sends `hsaPeoMatch` and `isManualCheck`,
    which the spec does not list. Earning `payAmount` is described as
    "pay per hour or unit", but it equals hours times `unitRate`.
  - UKG Ready pay statements send `calcUpto` and `emptyEarning`, which
    the schema does not list.
- **Decision:** Both voucher list keys are read. `payAmount` is the
  line amount. Each difference gets one `spec_live_mismatch` issue
  (live data differs from the spec) per bundle, and live-only fields
  stay in `unmapped`.
- **Reason:** These differences do not change what the other fields
  mean.
- **Evidence:** `src/normalization/adapters/prismhr.py` (`_PrismPayrollMapper`);
  `tests/test_payroll_ukg_ready.py::test_no_totals_and_live_only_fields`.
- **Status:** Decided.

## Company normalization

### 86. A company record holds the profile, tax ids, work locations and pay groups

- **Context:** Each provider describes a company with a profile (name,
  status, address, contact details) and several lists that other data
  types point at: the places people work, the groups they are paid in,
  and the tax registrations the company files under.
- **Decision:** `--entity company` writes one company record. Besides
  the profile, it holds three lists: `tax_ids` (EINs), `work_locations`
  and `pay_groups`. Status is grouped into active, pending, inactive,
  terminating and terminated. Codes with no shared meaning, such as
  PrismHR's corporation type, keep the raw code and the provider's label.
- **Reason:** These are the company facts that employee and payroll
  records refer to, so a reader can resolve those references.
- **Evidence:** `src/normalization/canonical/company.py`;
  `docs/canonical/normalized-output.schema.json#/$defs/Company`;
  `tests/test_canonical_model.py::test_company_fields_are_checked`.
- **Status:** Decided.

### 87. Tax ids, work locations and pay groups are nested lists with their own keys

- **Context:** Employees and pay runs refer to locations, pay groups
  and EINs by a raw code. These lists are small and belong to one
  company.
- **Decision:** The three lists sit inside the company record. Each
  entry has its own key (`<company key>:loc:<id>`, `:pg:<id>`,
  `:ein:<id>`) and keeps the provider's code. Records link by raw code:
  a PrismHR employee's location code is a work location's code, an
  isolved pay run's pay group is a pay group's ID, and a UKG Ready pay
  run's pay group is an EIN ID.
- **Reason:** Nesting keeps the company in one document. The raw codes
  are what the other records carry, so no new identifier is invented.
- **Evidence:** `tests/test_company_links.py` (one test per provider).
- **Status:** Decided.

### 88. What a capture bundle holds for companies

- **Context:** Each provider spreads the company across different calls,
  and some calls only return details when asked.
- **Decision:** A company bundle holds, per provider:
  - PrismHR: `getClientMaster`, and optionally `getClientCodes` (with
    `options=Location,PGroups`) and `getPayrollSchedule`;
  - isolved: the legal record fetched with `includeDetails=true`;
  - UKG Ready: the EIN lookup, and optionally the pay-period profiles.

  A missing optional call leaves its lists empty. Missing PrismHR client
  codes raise one `missing_section` issue (an expected part of the data
  is absent).
- **Reason:** These are the smallest sets of calls that fill the record
  on the live demos.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS`);
  `tests/test_bundle.py::test_company_keys_per_provider`;
  `tests/test_company_prismhr.py::test_missing_client_codes_leaves_lists_empty`.
- **Status:** Decided.

### 89. PrismHR's federal ID is masked live

- **Context:** PrismHR's client record has `federalIdNumber`, the EIN.
  The live demo sends it fully masked (`**********`).
- **Decision:** A masked value leaves the EIN empty, adds no tax id, and
  raises a `masked_value` warning (the provider hid the value). An
  unmasked value becomes the EIN and one tax id.
- **Reason:** A masked string is not an EIN (entry 1).
- **Evidence:** `tests/test_company_prismhr.py::test_masked_federal_id_leaves_ein_null`,
  `test_unmasked_federal_id_becomes_the_ein_and_one_tax_id`.
- **Status:** Decided.

### 90. Pay-group frequency: PrismHR from its schedule codes, isolved stays unknown

- **Context:** A PrismHR pay group's frequency is the `payPeriod` code
  on its payroll schedule. The field itself is described only as "pay
  period number", but the neighbouring `payPeriodDesc` lists the codes:
  `D` (Daily), `W` (Weekly), `B` (Biweekly), `S` (Semi-monthly), `M`
  (Monthly), and five `MD*` monthly variants. An isolved pay group's
  `payFrequency` is a bare integer described only as "Pay Frequency".
  Live, the three pay groups fit "pay periods per year": 12 is named
  "Monthly" with 173.33 normal hours, 26 "Biweekly" with 80 and runs
  14 days apart, and 24 "Salary" with 86.67. Employees break the
  pattern: all 20 are in the "Monthly" group, but five have 26.
- **Decision:** PrismHR codes map from that list. Every `MD*` code is
  monthly; Daily stays `unknown`, as there is no shared daily value. A
  pay group with no schedule row has no frequency. isolved stays
  `unknown` with an `undocumented_code` issue (a code with no documented
  meaning), as for employees (entry 25).
- **Reason:** The PrismHR spec documents the codes, just on the other
  field. isolved documents nothing, and a pattern that the employee
  values contradict is not enough to read the number as a frequency
  (entry 1).
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/ClientPayrollSchedule/properties/payPeriodDesc/description`;
  `contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models.PayGroupModel/properties/payFrequency`;
  `tests/test_company_prismhr.py::test_pay_groups_take_frequency_from_the_schedule`;
  `tests/test_company_isolved.py::test_pay_groups`.
- **Status:** Decided.

### 91. isolved company name stays empty without `dbaName`

- **Context:** isolved's legal record has `dbaName` (the trading name)
  and `legalName`. The live demo never sends `dbaName`.
- **Decision:** `name` is empty and `legal_name` holds `legalName`. One
  `missing_section` issue at `info` severity says so.
- **Reason:** A legal name is not necessarily the name a company trades
  under, so copying it would blur the two fields.
- **Evidence:** `tests/test_company_isolved.py::test_name_is_null_without_a_dba_name`.
- **Status:** Decided.

### 92. isolved company status labels allowed so far

- **Context:** isolved sends the legal company's status as English text,
  and the spec lists no values. Both live legals were "Active".
- **Decision:** "Active" is `active`. Any other label stays `unknown`
  with an `unmapped_label` issue (a label with no shared meaning yet).
- **Reason:** Only labels seen live are allowed, as for employee status
  (entry 21).
- **Evidence:** `src/normalization/adapters/isolved.py` (`COMPANY_STATUS`);
  `tests/test_company_isolved.py::test_unlisted_status_label`.
- **Status:** Decided.

### 93. UKG Ready pay-period profiles stand in for pay groups

- **Context:** UKG Ready has no pay group records. Its pay-period
  profiles define how often a group of employees is paid, with a
  `period_type` from a closed list and, for `every_n_weeks`, a week count.
- **Decision:** Each profile becomes a pay group. `weekly`,
  `semi_monthly` and `monthly` map to their namesakes, `monthly_weekday`
  (a set weekday each month) is monthly, and `every_n_weeks` is weekly
  for one week and biweekly for two. `quarterly`, `every_n_days`,
  `user_defined` and other week counts stay `unknown`. A value outside
  the list raises an `out_of_schema_value` issue (a value outside the
  documented set).
- **Reason:** Profiles are what UKG Ready uses to group pay schedules.
  A monthly weekday profile still pays once a month. Quarterly has no
  shared value, and the remaining types have no fixed frequency.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/273`
  (`period_type.type` enum and `params.num_weeks`);
  `src/normalization/adapters/ukg_ready.py` (`PERIOD_TYPE`);
  `tests/test_company_ukg_ready.py::test_frequency_mapping`,
  `test_out_of_enum_period_type`.
- **Status:** Decided.

### 94. UKG Ready EINs come from the lookup only

- **Context:** UKG Ready documents many routes inside a company
  (`/v2/companies/{cid}/...`) but none that returns the company itself,
  so there is no documented name, address or status. Live,
  `/rest/v2/companies/{cid}` answers 404 "Unresolvable URL". The closest
  call is the EIN lookup, which lists the company's tax registrations.
  Live it lists one EIN, named "Primary EIN", which is not a company
  name. Payrolls also use a second EIN ("2nd EIN") that the lookup leaves
  out.
- **Decision:** Tax ids come from the EIN lookup, one per row. With one
  row it is also the company EIN; with several the EIN is empty and a
  `missing_lookup` warning (a needed lookup entry is absent) says so.
  Name, address and status are empty, with one `missing_section`
  warning. An EIN that only payrolls mention is not added.
- **Reason:** A company name UKG does not provide cannot be filled in
  without guessing (entry 1). The lookup is the documented list of EINs.
  The second EIN is a finding about the demo, not something to patch from
  payroll data.
- **Evidence:** `contracts/ukg-ready/reference-docs/res/` has no
  company-detail page;
  `contracts/ukg-ready/reference-docs/res/__v2__companies__(cid)__lookup__eins.html`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/249`;
  `tests/test_company_ukg_ready.py::test_single_ein`,
  `test_two_eins_list_both_and_leave_ein_null`,
  `test_profile_is_empty_with_an_issue`.
- **Status:** Decided.

### 95. Where live company data differs from the specs

- **Context:** The live demo companies did not match the specs:
  - PrismHR's client record sends six fields the spec does not list,
    plus `eVerify`, which the spec spells `everify`.
  - PrismHR's `getPayrollSchedule` lists schedules under
    `clientPayrollSchedule`, not `clientPayrollSchedules`.
  - isolved's legal record never sends `dbaName`, `naicsCode` or
    `logoData`, and its work locations call answers 401.
- **Decision:** Both schedule keys are read. Each PrismHR difference
  gets one `spec_live_mismatch` issue (live data differs from the spec)
  per bundle, and live-only fields stay in `unmapped`. The isolved gaps
  are covered by entries 88 and 91.
- **Reason:** These differences do not change what the other fields
  mean.
- **Evidence:** `tests/test_company_prismhr.py::test_live_only_fields_are_reported_once`,
  `test_singular_schedule_key_is_reported`,
  `test_plural_schedule_key_reads_without_an_issue`.
- **Status:** Decided.

## Issue tracker

### 96. Issue badges count everything under a tile

- **Context:** The issue tracker shows providers, clients and employees as
  tiles with a badge. Some issues sit above the employee: a client can
  have pay-run, pay-group and company-detail issues, and an issue can
  name an employee who is not in the employee list. The badge had to say
  whether it counts these.
- **Decision:** A badge counts every issue under its tile, these included,
  so isolved shows 10. Provider-wide findings are not shown at all
  (entry 97), so no badge counts them. The badge is the number only, and a tile with no
  issues shows no badge. Only the tiles a reader can open carry a badge:
  the large provider or client tile heading its own page has none.
  Provider
  tiles stay in the field-mapping order: PrismHR, isolved, UKG Ready.
  Client and employee tiles are ordered by that count, then by name.
- **Reason:** A provider or client badge should match what a reader finds
  by opening everything under it. The number says where the issues are;
  severity colour did not say which field was wrong. A zero badge was
  noise next to the tiles that need attention, and a badge on the heading
  tile only repeated the number the reader clicked to get there.
- **Evidence:** `web/src/components/issues/issue-badge.tsx`;
  `web/src/lib/issues.ts` (`providerIssues`, `companyIssues`, `byConcern`);
  `web/src/lib/issues.test.ts`.
- **Status:** Decided.

### 97. Provider-wide findings stay out of the issue tracker

- **Context:** Many issues in the fixtures (19 of 35) have no employee
  tile to sit on. 13 are provider-wide findings with no record key,
  mostly `spec_live_mismatch` issues (live data differs from the spec)
  that describe the provider's API rather than anyone's data. The other
  6 are pay-group and company-detail issues of one client. An issue can
  also concern a pay run, or an employee missing from the employee list.
- **Decision:** The issue tracker leaves provider-wide findings out; they
  remain in the normalized output files and the command line output.
  Client issues stay one link away: under its tiles, the client page
  shows a link such as "3 issues tied to the client", only when its count
  is above zero. It opens the same popup as an employee, grouped by
  record, and these issues are counted in the badges.
- **Reason:** The tracker is for checking employee data. A spec mismatch
  is for whoever maintains the adapter, and they read the output files.
  The client link names the level its issues belong to, so a reader knows
  what to look at before opening it.
- **Evidence:** `src/normalization/issue_tree.py` (`build_provider`);
  `tests/test_issue_tree.py::BuildProvider::test_issues_attach_to_their_node`,
  `GoldenTrees::test_every_keyed_golden_issue_lands_once`;
  `web/src/app/issues/[provider]/[company]/page.tsx`.
- **Status:** Decided.

### 98. The issue export holds names and redacted values

- **Context:** The coverage file the web app reads holds no provider
  values. The issue tracker needs employee and company names to label tiles,
  and each issue's raw value to say what the provider sent.
- **Decision:** The issue tracker reads its own file,
  `web/src/data/issues.json`. It holds employee and company names from the
  golden outputs and each issue's raw value as the adapter recorded it,
  already redacted. The issue message and spec citation stay out. Each
  issue also carries a short expected constraint taken from that message,
  with the spec path removed. The popup shows the field, what was sent,
  that constraint, and the short result of the action. Severity stays on
  the issue and is not shown.
- **Reason:** The fixtures are synthetic and adapters redact raw values
  before they reach an issue, so the file holds nothing sensitive, and a
  separate file keeps the coverage file free of provider values. A file
  built from live data would need this revisited.
- **Evidence:** `scripts/export_web_data.py` (`render_issues`);
  `tests/test_web_export.py::WebExportChecks::test_export_holds_no_provider_values`;
  `tests/test_issue_tree.py::IssueExport::test_committed_issue_export_is_current`.
- **Status:** Decided.

## Company document

### 99. One command writes one linked document per company

- **Context:** Each data type is normalized on its own, so one company
  takes five runs and gives five files. Their records point at each other
  by key: a deduction names its employee, a paycheck its employee and pay
  run. Those keys lead into other files, and nothing checked that they
  resolve. The assignment asks for records that can be linked.
- **Decision:** `normalize-company` reads the five bundle files of one
  company from a folder and writes one document: the full company record
  and every employee, direct deposit, deduction, pay run and paycheck.
  All five files must be present and name the same provider and company,
  or nothing is written. The company records the other four data types
  carry are dropped, and an issue reported word for word by several data
  types appears once. Every key is then checked against the document. A
  key that names no record in it adds a `broken_link` warning (a record
  points at a record missing from the document), and the record is kept.
- **Reason:** One file lets a reader follow an employee from profile to
  paycheck, and the check shows the keys actually join. Requiring all five
  files keeps the rule simple, since the fixtures always have them. Live
  isolved payroll comes from a different legal (entry 77), so a live
  isolved folder would be rejected as two companies.
- **Evidence:** `src/normalization/company_document.py`;
  `tests/test_company_document.py::CompanyDocumentChecks::test_document_merges_the_five_golden_outputs`,
  `::test_broken_links_are_reported_and_records_kept`,
  `CompanyBundleLoading::test_missing_bundle_file_is_named`,
  `::test_bundles_for_another_company_are_rejected`.
- **Status:** Decided.
