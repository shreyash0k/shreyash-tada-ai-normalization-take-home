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
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize) (the
  four required data types) and
  [the optional extension](ASSIGNMENT.md#optional-extension-write-canonical-data-to-a-provider)
  (the write path is marked optional).
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

- **Context:** In PrismHR a "client" is the company an employee works for. To
  fetch employees you have to say which client you want, but the employee
  records that come back never repeat that client ID. The response has
  similar-looking fields (`client.clientEmployeeId`, the employee's number
  inside the client, and `client.transferInfo.transferClientId`, used for
  transfers), but none of them is the owning company.
- **Decision:** The client ID is taken from the request that was sent, which
  is saved alongside the responses in the capture bundle (entry 14). It is
  used to build the company key (`prismhr:<client_id>`) and every employee
  key, so each employee can be linked back to its company.
- **Reason:** The request is the only place the ID exists.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee`. Confirmed against the live demo: the response
  for client `132` with all four options does not contain the client ID
  anywhere. `src/normalization/bundle.py` (`PROVIDER_SPECS["prismhr"]`);
  `tests/test_employee_prismhr.py::test_keys_and_company_link`.
- **Status:** Decided.

### 6. Some UKG Ready duration fields are in milliseconds

- **Context:** UKG Ready stores some lengths of time as whole numbers of
  milliseconds rather than hours. Its documentation says so for certain
  fields, for example `total` on time entries and `standard_work_day` (the
  length of a normal working day) on pay info.
- **Decision:** A field is converted from milliseconds to hours only when its
  own documentation says it is in milliseconds. Any other time field with no
  documented unit is kept as received and reported as an issue.
- **Reason:** The reference audit warns that the evidence covers only those
  specific fields, not every UKG time field.
- **Evidence:** [docs/REFERENCE_AUDIT.md](REFERENCE_AUDIT.md#field-specific-ukg-duration-evidence).
- **Status:** Decided.

### 7. UKG Ready has no documented endpoint for company details

- **Context:** UKG Ready's documentation has many routes for things inside a
  company (`/v2/companies/{cid}/...`) but none that returns the company
  itself, so there is no documented way to get the company's name. The
  closest is the EIN lookup (`/v2/companies/{cid}/lookup/eins`), which lists
  the company's tax registrations (`id`, `ein_name`, `ein_tax_id`,
  `ein_currency_code`, `ein_country_id`). Employee records also carry
  `ein_name`. The live demo confirms the gap: asking for
  `/rest/v2/companies/{cid}` returns 404 "Unresolvable URL", and the EIN
  lookup returns one EIN named "Primary EIN", which is not a company name.
- **Decision:** Not decided yet. The likely approach is to build the company
  record from the company ID used at sign-in plus the EIN lookup, and leave
  the company name empty with a reported issue. The employee task already does
  this for its company stub (entry 32); a full company record is a later task.
- **Reason:** A company name that UKG does not provide cannot be filled in
  without guessing (entry 1).
- **Evidence:** `contracts/ukg-ready/reference-docs/res/` has no company-detail
  page; `contracts/ukg-ready/reference-docs/res/__v2__companies__(cid)__lookup__eins.html`;
  live demo calls for company `33704016`.
- **Status:** Open.

### 8. Live PrismHR `getEmployee` differs from its documentation

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
  last-four value and a `masked_value` issue (entry 18).
- **Reason:** Quietly renaming live fields to match the spec would hide the
  fact that the two disagree. Reporting each difference once per company,
  rather than once per employee, keeps the issue list readable.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json`, path
  `/employee/v1/getEmployee` (description and `Person` schema); live demo
  calls for client `132`, employee `A00576`;
  `src/normalization/adapters/prismhr.py` (`LIVE_SHAPE_DIFFERENCES`);
  `tests/test_employee_prismhr.py::test_live_spellings_reported_once_per_bundle`.
- **Status:** Decided.

### 9. Live isolved employee records carry fewer fields than the spec

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
  calls; `tests/test_employee_isolved.py::test_sparse_record_has_nulls_and_no_extra_issues`.
- **Status:** Decided.

### 10. Live UKG Ready employee data needs several calls and lookups

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
- **Decision:** A UKG capture bundle (entry 14) holds the employee list, four
  responses per employee (detail, demographics, pay info, compensation
  history), and the three company lookups (employee types, pay types, EINs).
  If one of an employee's four responses is missing, a `missing_section`
  issue is reported and the fields it would have supplied are left empty.
  The current pay row is chosen as described in entry 31. `time` and
  `standard_work_day` are converted from milliseconds to hours under entry 6,
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

### 11. The readiness check blocks isolved and UKG Ready

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

### 12. Direct deposits and deductions are missing from the starter

- **Context:** The assignment asks for direct deposits and deductions, but the
  starter code only knows about three data types: company, employee, and
  payroll.
- **Decision:** Not decided yet. Direct deposits and deductions need to be
  added, either as their own data types or as part of the employee record.
- **Reason:** They are required data types, so they need a home in the model
  either way.
- **Evidence:** [docs/ASSIGNMENT.md](ASSIGNMENT.md#data-to-normalize);
  `ENTITIES` in `src/normalization/adapters/__init__.py`.
- **Status:** Open.

### 13. A starter test requires every transformation to stay unimplemented

- **Context:** One starter test checks that every provider-and-data-type
  combination is still unimplemented, so it fails the moment any adapter
  starts working.
- **Decision:** The test has been removed, and each adapter gets tests of
  what it actually does instead. The employee adapters have theirs in
  `tests/test_employee_*.py`.
- **Reason:** A test that asserts the absence of a feature blocks building it.
- **Evidence:** `tests/test_starter.py` no longer contains
  `test_all_nine_transformations_are_explicitly_unimplemented`.
- **Status:** Decided.

### 14. An adapter receives only one response, with no request context

- **Context:** The starter code passes each adapter a single API response.
  That is not enough: one employee's data is spread across several calls
  (entry 10), and some identifiers exist only in the request that was sent,
  not in any response (entry 5).
- **Decision:** Every adapter reads a **capture bundle**: one JSON file for
  one provider and one company, holding the details of the request and every
  response needed. It has five parts: a format version (`bundle_version`),
  the provider name, the date the data was captured (`captured_at`), the
  request parameters (`request`), and the responses grouped by call
  (`responses`). Each provider has its own list of calls that must be present
  and calls that may be present. A bundle that is missing a required part, or
  has one in the wrong shape, is rejected with a message naming exactly which
  part is wrong. `normalize --entity employee` reads a bundle.
- **Reason:** Keeping the request and every response together means made-up
  test data and real downloads saved by hand go through exactly the same
  code.
- **Evidence:** `src/normalization/bundle.py` (`PROVIDER_SPECS` lists the
  required and optional responses per provider; `parse_bundle` raises
  `ValueError` naming the offending path); `tests/test_bundle.py`;
  `tests/fixtures/*/employee-bundle.json`.
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

### 17. When a raw value may map to a canonical enum

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
    own entry below (entries 23-26).
  Partial matches and case-insensitive matches never count. Anything else
  stays `unknown`, keeps its raw value and label, and is reported: as
  `undocumented_code` for a code, or `unmapped_label` for a label.
- **Reason:** It makes the line between "documented" and "inferred" explicit,
  so anyone can check why a value got the meaning it did.
- **Evidence:** `src/normalization/adapters/_common.py` (`CodeTable`,
  `Collector.code`); the `CodeTable` constants in each adapter cite their
  spec path.
- **Status:** Decided.

### 18. Only the last four SSN digits are emitted

- **Context:** The three providers handle Social Security numbers
  differently. PrismHR sends it masked (`***-**-****`), isolved sends it
  empty, and UKG sends it in full, both as `social_security` and inside its
  list of national ID numbers.
- **Decision:** The output keeps only the last four digits
  (`person.ssn_last4`). If the provider sent a masked number, there are no
  digits to keep, so the value is empty and a `masked_value` issue says why.
  Anywhere else the output repeats provider data (the `unmapped` leftovers in
  entry 19, and the raw value quoted in an issue), any field whose name looks
  like an identifier or a secret is replaced with `[redacted]`. That covers
  names containing `ssn`, `social_security`, `social_insurance`,
  `national_insurance`, `national_id`, `bsn`, `password`, `secret`, `token`,
  `ticket`, `photo_href` or `bank_account`. Tests check that no full Social
  Security number from the input appears anywhere in the output.
- **Reason:** The assignment requires that live records and secrets stay out
  of Git, and output files are the most likely thing to be committed or
  shared. UKG's `photo_href` is on the list because the link carries a
  sign-in ticket.
- **Evidence:** `src/normalization/adapters/_common.py` (`redact`,
  `Collector.ssn_last4`); `tests/test_employee_prismhr.py::test_only_last_four_ssn_digits_are_emitted`;
  `tests/test_employee_ukg_ready.py::test_identifiers_and_tokens_are_redacted_in_unmapped`.
- **Status:** Decided.

### 19. Unconsumed provider fields pass through in `unmapped`

- **Context:** The assignment asks to cover all available employee fields.
  PrismHR alone sends over 200 fields per employee, and most of them are
  specific to PrismHR and have no place in a shared model (for example
  `ohioFormC112` or `fedW5Filed`).
- **Decision:** Nothing is dropped. The adapter keeps track of every field it
  used; whatever is left over appears in the employee's `unmapped` section,
  under the field's path in the provider's data. Items in a list are numbered,
  as in `organizations[1].organizationId`. Identifiers and secrets are
  redacted as described in entry 18.
- **Reason:** It covers every field without inventing places in the shared
  model for fields only one provider has.
- **Evidence:** `src/normalization/adapters/_common.py` (`Reader.unmapped`);
  `tests/test_employee_prismhr.py::test_unmapped_keeps_unconsumed_fields_and_redacts_identifiers`.
- **Status:** Decided.

### 20. Issue codes and severities for the employee task

- **Context:** Entry 1 says every problem is reported as a structured issue
  rather than hidden. Those issues needed a fixed vocabulary so they can be
  counted, filtered and compared across providers.
- **Decision:** Each issue says what kind of problem it is (`code`), how
  serious it is (`severity`), where in the provider's data it was found
  (`source_path`), what the pipeline did about it (`action`), which record
  it concerns (`record_key`), the value involved (`raw_value`, redacted as in
  entry 18), and a sentence explaining it (`message`). There are three levels
  of seriousness:
  - `error`: a value was unusable and was dropped. Codes: `invalid_date`,
    `invalid_number`.
  - `warning`: a value is kept but could not be interpreted, or something
    expected is missing. Codes: `undocumented_code`, `unmapped_label`,
    `missing_section`, `missing_lookup`, `out_of_schema_value`,
    `multiple_current_rates`.
  - `info`: a note about the provider's behaviour, with nothing lost. Codes:
    `spec_live_mismatch`, `masked_value`.
- **Reason:** A small fixed set of codes lets someone see at a glance how many
  records lost data and how many only need a person to confirm a meaning,
  and makes issues from different providers directly comparable.
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

### 22. PrismHR employment type and status come from the "class" fields

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

### 23. isolved employment status: `Active` and `Terminated` are recognised

- **Context:** isolved sends employment status as a text label
  (`employmentStatus`). The spec calls it "the current employment status
  description" and gives no list of possible values.
- **Decision:** Two labels are recognised, spelled exactly as isolved sends
  them: `Active` becomes `active` and `Terminated` becomes `terminated`. Any
  other label is kept as received, with the shared value `unknown` and an
  `unmapped_label` issue. Live customers may well set up more statuses than
  these.
- **Reason:** These were the only two labels in the live demo company, and
  their meaning is plain English. Anything else would be a guess (entry 17).
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeModel/properties/employmentStatus`;
  live `GET /api/clients/4046/legals/5806/employees` returned exactly these
  two labels across 20 employees;
  `tests/test_employee_isolved.py::test_allowlisted_labels_map`.
- **Status:** Decided.

### 24. isolved gender: `Male` and `Female` are recognised

- **Context:** isolved sends gender as a text label (`gender`). The spec calls
  it "Gender description" and gives no list of possible values.
- **Decision:** Two labels are recognised, spelled exactly as isolved sends
  them: `Male` becomes `male` and `Female` becomes `female`. Any other label
  is kept as received, with the shared value `unknown` and an
  `unmapped_label` issue. Non-binary and "declined to state" are not on the
  list, because we have not seen how isolved spells them.
- **Reason:** Only these two labels appeared in the live demo company.
  Guessing the spelling of other options could wrongly match, or miss, real
  values (entry 17).
- **Evidence:** same definition, `properties/gender`; the live sample;
  `tests/test_employee_isolved.py::test_off_allowlist_labels_stay_raw_with_issue`.
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
  live `GET /api/clients/4046/legals/5806/employees` (labels `Salary`,
  `Hourly`, `1099` across 20 employees);
  `tests/test_employee_isolved.py::test_allowlisted_labels_map`.
- **Status:** Decided.

### 26. UKG Ready employee status: `Active` and `Terminated` are recognised

- **Context:** UKG sends employee status (`status`) as plain text. The schema
  notes it is "only used for GET" and gives no list of possible values.
- **Decision:** Two values are recognised, spelled exactly as UKG sends them:
  `Active` becomes `active` and `Terminated` becomes `terminated`. Any other
  value is kept as received, with the shared value `unknown` and an
  `unmapped_label` issue.
- **Reason:** These were the only two values across all 103 employees in the
  live demo company, and their meaning is plain English. Anything else would
  be a guess (entry 17).
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/106/schema/properties/status`;
  live `GET /rest/v2/companies/33704016/employees` returned only these two
  values across 103 employees;
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
  `/lookup/employee-types` and `/lookup/pay-types`;
  `tests/test_employee_ukg_ready.py::test_tenant_lookups_resolve_to_labels_but_stay_unknown`,
  `::test_lookup_miss_is_reported`.
- **Status:** Decided.

### 29. PrismHR `payPeriod` on `Compensation` is undocumented

- **Context:** An employee's pay frequency in PrismHR comes from the
  `payPeriod` field in the pay section (`Compensation`). Its description says
  only "pay period associated with the payGroup", with no list of codes. A
  field with the same name elsewhere in the spec (`PayRate.payPeriod`) does
  list its letters (W, B, S, M, A, H), but that is a different field on a
  different record.
- **Decision:** Pay frequency keeps PrismHR's raw letter, with the shared
  value `unknown` and an `undocumented_code` issue. The neighbouring field
  `hourlyPayPeriod`, which does list its own letters (H, W, B, S, M, Y), is
  used for the period of the pay rate.
- **Reason:** Entry 17(a) requires the meaning to be documented on the field
  actually read. Borrowing it from a same-named field elsewhere would be
  assuming the two use the same codes.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/payPeriod`
  and `.../hourlyPayPeriod`;
  `tests/test_employee_prismhr.py::test_pay_period_codes_are_undocumented_on_compensation`.
- **Status:** Open.

### 30. PrismHR `payMethod` `D` is "driver", not "daily"

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

### 32. Each output has a minimal company record with no name

- **Context:** Employees must be linkable to their company, but none of the
  employee calls returns the company's name, and fetching full company
  details is a separate task.
- **Decision:** Each output has a minimal company record (a "stub"): just a
  key that identifies the company, the provider it came from, and the EIN
  where it is known. The keys look like this:
  - PrismHR: `prismhr:<client_id>`.
  - isolved: `isolved:<client_id>-<legal_id>`, because an isolved client can
    have several legal entities. The legal entity's code (`legalCode`) is
    added as a second identifier when every employee record agrees on it.
  - UKG Ready: `ukg-ready:<company_id>`. The EIN is filled in from the EIN
    lookup when it returns exactly one row; if it returns several, a
    `missing_lookup` issue says the EIN could not be chosen.
  The company name is empty, and a `missing_section` issue says that company
  details are a later task.
- **Reason:** Every employee needs a company key to link to, and the key can
  be built from identifiers the bundle already has. Filling in more than that
  would mean guessing (entry 1).
- **Evidence:** `src/normalization/canonical/company.py`;
  `tests/test_employee_ukg_ready.py::test_company_stub_takes_ein_from_single_lookup_row`.
- **Status:** Decided.

### 33. Standard hours are "per pay period" for PrismHR and isolved

- **Context:** Both PrismHR and isolved send an employee's standard working
  hours as a bare number with no unit next to it. The period is only in the
  field's description: PrismHR `standardHours` is "standard hours per pay
  period", and isolved `normalHours` is "Normal work hours for the employee
  per pay period".
- **Decision:** Whenever standard hours are present, their period is set to
  "per pay period". Since the provider sent no code for it, the raw value is
  empty and the label reads `per pay period`.
- **Reason:** Each field's own description states the period, so this
  follows the documentation rather than guessing.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Compensation/properties/standardHours`;
  `contracts/isolved/openapi/isolved-v6.swagger.json`, `EmployeeModel/properties/normalHours`.
- **Status:** Open.

### 34. Email and address kinds follow the field's description

- **Context:** Each email address and postal address in the output is tagged
  with a kind (work, personal, home, mailing, and so on). The providers often
  have several of each, and the field name or description is usually the
  only hint about which is which. Some descriptions give no hint: PrismHR's
  `contactInformation.emailAddress` is just "the employee's email address",
  isolved's `emailAddress` is "Employee E-Mail Address", and UKG's
  `primary_email` says nothing either.
- **Decision:** A kind is assigned only when the field's name or description
  says it.
  - Emails: the three above get kind `unknown`. Fields named as work,
    personal or secondary emails (`workEmail`, `personalEmailAddress`,
    `secondary_email`) get `work`, `personal` and `other`.
  - PrismHR addresses: the contact-information address is `home`; the
    address on the client section is `mailing`, as its description says
    "alternate mailing address"; the W-2 address fields are `w2`; and the
    separate address call (`getAddressInfo.altAddress`) adds a `mailing`
    address when the record has none.
  - isolved addresses: `nameAddress` is `home` and `overrideAddress` is
    `w2`.
  - UKG addresses: `address` is `home`, and `mailing_address` is `mailing`
    unless UKG says no separate mailing address is used
    (`use_separate_mailing_address` is `false`).
- **Reason:** Calling an email "personal" or "work" without the provider
  saying so would be a guess that downstream systems might act on, for
  example by sending payslips to the wrong inbox.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Client/properties/addressLine1`
  ("address line 1 from alternate mailing address"), `Person/properties/w2AddressLine1`;
  `contracts/isolved/openapi/isolved-v6.swagger.json`, `EmployeeModel/properties/overrideAddress`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/106/schema/properties/mailing_address`.
- **Status:** Open.

### 35. isolved location prefers `organizations[]`, then `workLocation`

- **Context:** isolved can describe where an employee works in two places.
  When asked to include organizations, the employee detail has a list of
  labelled rows (`organizations[]`), such as one titled `Location` and one
  titled `Department`, each with a code (`value`) and a description
  (`valueDescription`). Separately, every record has a `workLocation` code
  with a description (`workLocationDashDescription`).
- **Decision:** The department comes from the `Department` row. The
  location comes from the `Location` row when there is one, and otherwise
  from `workLocation`, with its description as the label. Any other
  organization rows are kept in `unmapped` (entry 19).
- **Reason:** When requested, the organization rows are where isolved lists
  department and location side by side, so both come from the same place.
  `workLocation` is on every record, so it covers employees whose detail has
  no `Location` row.
- **Evidence:** `contracts/isolved/openapi/isolved-v6.swagger.json`,
  `#/definitions/AOS.PayrollOffice.RestAPI.Models.EmployeeOrganizationModel`
  and `EmployeeModel/properties/workLocation`;
  `tests/test_employee_isolved.py::test_detail_overlay_supplies_organizations_and_taxes`.
- **Status:** Open.

### 36. PrismHR gender codes are explained on a different record

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
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/Person/properties/gender`
  and `#/components/schemas/NewHireEmployee/properties/gender`;
  `src/normalization/adapters/prismhr.py` (`GENDER`).
- **Status:** Open.

## Field coverage

### 37. What the coverage statuses mean

- **Context:** The field coverage page shows, for every canonical employee
  field, whether each provider supplies it. A provider can have the data
  and the adapter use it, have the data and the adapter not use it, or
  have no such field at all. A field the adapter uses can still be empty
  for every synthetic employee.
- **Decision:** Each field and provider pair is "mapped", "not mapped
  yet" or "not offered", and every one cites a spec path. "Not offered"
  cites the schema that lacks the field and says why it is missing. A
  mapped field that no fixture employee fills shows as "empty in
  sample", with a note when the cause is the fixture generator.
- **Reason:** "Not offered" is a claim about the provider, so it needs the
  same evidence as a mapping. Separating "empty in sample" stops gaps in
  the synthetic data from reading as gaps in the adapter.
- **Evidence:** `src/normalization/field_map.py`;
  `tests/test_field_map.py`; `tests/test_web_export.py::test_counts_agree_with_golden_output`.
- **Status:** Open.

### 38. UKG Ready termination and rehire details are write-only

- **Context:** UKG Ready describes an employee's termination reason and
  rehire eligibility only in the schema for updating an employee (schema
  107, the PUT body). The schema for reading an employee (schema 106)
  has termination and rehire dates but no reason and no eligibility.
- **Decision:** The output has no termination reason or rehire
  eligibility for UKG Ready, and the coverage page shows both as "not
  offered".
- **Reason:** A field documented only for writing is not one the read
  call can be relied on to return.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/107/schema/properties/termination_details`
  and `#/schemas/107/schema/properties/rehire_details`;
  `#/schemas/106/schema/properties/dates`;
  `src/normalization/field_map.py` (`UKG_READY`).
- **Status:** Open.

### 39. Job titles behind a lookup, and UKG Ready organization, are not mapped yet

- **Context:** PrismHR and UKG Ready put only a job code on the employee
  record; the title lives in a separate list of jobs. For PrismHR that list
  is the job code table (`getClientCodes` with the `Job` option), where
  each entry's `jobTitle` is the "position/job title". For UKG Ready it is
  the jobs configuration (`config/cost-center-jobs`), and the employee's
  default job is an ID (`pay_info.default_job`). The bundle fetches
  neither list. UKG Ready also gives organization as up to nine
  cost-centre levels (`cost_centers_info`, levels 0 to 8), and each
  company defines what each level means.
- **Decision:** The adapters map the job code but no job title for PrismHR
  or UKG Ready, and no department, location or division for UKG Ready.
  The coverage page shows these as "not mapped yet".
- **Reason:** A title needs the provider's job list, which the bundle
  would have to fetch first. Picking a cost-centre level for department
  or location would guess at a per-company setting.
- **Evidence:** `contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/JobCode/properties/jobTitle`
  and `#/paths/~1clientMaster~1v1~1getClientCodes`;
  `contracts/ukg-ready/reference-schemas.json#/schemas/159/schema/properties/default_job`
  and `#/schemas/106/schema/properties/cost_centers_info`;
  `src/normalization/bundle.py` (`PROVIDER_SPECS`);
  `src/normalization/field_map.py` (`PRISMHR`, `UKG_READY`).
- **Status:** Open.

### 40. UKG Ready contractor flag is in tax-info, which the bundle does not fetch

- **Context:** UKG Ready records whether an employee is paid as a W-2
  employee, a 1099 contractor or on a draw in the employee's tax
  information. The read schema for that call (schema 166, tax-info) has
  `employee-tax-type` with three yes/no flags: `W2`, `_1099` and `DRAW`.
  The capture bundle does not fetch tax-info.
- **Decision:** The output has no contractor flag for UKG Ready, and the
  coverage page shows it as "not mapped yet", not "not offered".
- **Reason:** UKG documents the flag, so the gap is in what the bundle
  collects, not in the provider. Adding tax-info to the bundle would let
  the adapter read `_1099`.
- **Evidence:** `contracts/ukg-ready/reference-schemas.json#/schemas/166/schema/properties/employee-tax-type/properties/_1099`;
  `src/normalization/bundle.py` (`PROVIDER_SPECS`, UKG Ready keys);
  `src/normalization/field_map.py` (`UKG_READY`).
- **Status:** Open.
