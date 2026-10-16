"""isolved employee, direct deposit and deduction adapter.

Input: a capture bundle whose ``responses.employees`` is a list of paged
``GET /api/clients/{clientId}/legals/{legalId}/employees`` responses
(``PagedModelItemListOfEmployeeModel``: ``results[]``). Optional maps keyed
by the employee ``id`` (as a string) carry the single-employee detail,
``/personal`` and ``/nameAddress`` responses; when present they override the
list record field by field.

Direct deposits come from ``responses.direct_deposits``, keyed by employee
``id``: the array returned by ``.../employees/{employeeId}/directdeposits``.
The live API answers 404 with an empty body for an employee with no
deposits; a capture records that as an empty array.

Deductions come from ``responses.pay_items``, keyed by employee ``id``: the
array returned by ``.../employees/{employeeId}/payItems``. Only items whose
``payItemType`` is ``Deduction`` become deduction records; earnings and memo
calculations belong to other data types.

isolved returns English descriptions rather than codes for most coded fields
("Active", "Male", "Salary"). Only the short allowlists below map to canonical
values; everything else stays raw with an issue.
"""
from typing import Any, Dict, Iterator

from ..bundle import Bundle, parse_bundle
from ..canonical import (
    AccountType,
    Address,
    AddressKind,
    Allocation,
    AllocationMethod,
    Calculation,
    Citizenship,
    CodedValue,
    Company,
    CompanySource,
    Compensation,
    Contact,
    DateRange,
    Deduction,
    DeductionSource,
    DepositSource,
    DepositStatus,
    DirectDeposit,
    Email,
    EmailKind,
    Employee,
    Employment,
    EmploymentStatus,
    EmploymentType,
    Gender,
    IssueCode,
    Job,
    MaritalStatus,
    NormalizedOutput,
    PayPeriod,
    PayType,
    Person,
    Phone,
    PhoneKind,
    Severity,
    SourceRef,
)
from ._common import CodeTable, Collector, Reader, boolean, text

PROVIDER = "isolved"
SPEC = "contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models"
LIVE = "live GET /api/clients/{clientId}/legals/{legalId}/employees capture (docs/DECISIONS.md allowlist entries)"

EMPLOYMENT_STATUS = CodeTable(
    "employmentStatus", EmploymentStatus,
    {"Active": EmploymentStatus.ACTIVE, "Terminated": EmploymentStatus.TERMINATED},
    f"{SPEC}.EmployeeModel/properties/employmentStatus ('status description'); labels from {LIVE}",
    kind="label",
)
GENDER = CodeTable(
    "gender", Gender, {"Male": Gender.MALE, "Female": Gender.FEMALE},
    f"{SPEC}.EmployeeModel/properties/gender ('Gender description'); labels from {LIVE}",
    kind="label",
)
PAY_TYPE = CodeTable(
    "payType", PayType,
    {"Salary": PayType.SALARY, "Hourly": PayType.HOURLY, "1099": PayType.CONTRACTOR_1099},
    f"{SPEC}.EmployeeModel/properties/payType; labels from {LIVE}",
    kind="label",
)
# Descriptions with no allowlist: kept raw, canonical value unknown.
MARITAL_STATUS = CodeTable(
    "maritalStatus", MaritalStatus, {},
    f"{SPEC}.EmployeeModel/properties/maritalStatus ('Marital status code'; live returns descriptions)",
    kind="label",
)
CITIZENSHIP = CodeTable(
    "citizenship", Citizenship, {},
    f"{SPEC}.EmployeeModel/properties/citizenship ('Citizenship status description')",
    kind="label",
)
# Client-defined codes and an integer frequency with no documented meanings.
EMPLOYMENT_CATEGORY = CodeTable(
    "employmentCategoryCode", EmploymentType, {},
    f"{SPEC}.EmployeeModel/properties/employmentCategoryCode ('current employment category code')",
)
PAY_FREQUENCY = CodeTable(
    "payFrequency", PayPeriod, {},
    f"{SPEC}.EmployeeModel/properties/payFrequency (integer, 'payment frequency for the employee')",
)
# Spec: normalHours is "Normal work hours for the employee per pay period".
STANDARD_HOURS_PERIOD = CodedValue(raw=None, label="per pay period", value=PayPeriod.PAY_PERIOD)

DEPOSIT = f"{SPEC}.EmployeeDirectDepositModel/properties"
LIVE_DEPOSITS = ("live GET /api/clients/{clientId}/legals/{legalId}/employees/{employeeId}/directdeposits "
                 "capture (docs/DECISIONS.md direct deposit entries)")
DEPOSIT_ACCOUNT_TYPE = CodeTable(
    "directdeposits.accountType", AccountType, {"Checking": AccountType.CHECKING},
    f"{DEPOSIT}/accountType ('Bank Acount Type Description'); labels from {LIVE_DEPOSITS}",
    kind="label",
)
DEPOSIT_STATUS = CodeTable(
    "directdeposits.status", DepositStatus,
    {"Active": DepositStatus.ACTIVE, "Inactive": DepositStatus.INACTIVE},
    f"{DEPOSIT}/status ('Direct Deposit Status Description'); labels from {LIVE_DEPOSITS}",
    kind="label",
)
# isolved sends no method code: the method follows from which field is set
# (amount and percent are mutually exclusive) and from sequence 0, "Net Pay".
METHOD_FROM_AMOUNT = CodedValue(raw=None, label="amount", value=AllocationMethod.FIXED_AMOUNT)
METHOD_FROM_PERCENT = CodedValue(raw=None, label="percent", value=AllocationMethod.PERCENT)
METHOD_NET_PAY = CodedValue(raw=None, label="Net Pay (sequence 0)", value=AllocationMethod.REMAINDER)
METHOD_UNKNOWN = CodedValue(raw=None, label=None, value=AllocationMethod.UNKNOWN)

PAY_ITEM = f"{SPEC}.EmployeePayItemModel/properties"
LIVE_PAY_ITEMS = ("live GET /api/clients/{clientId}/legals/{legalId}/employees/{employeeId}/payItems "
                  "capture (docs/DECISIONS.md deduction entries)")
# payItemType is "The Pay Item Type" with no listed values; these three were seen live.
DEDUCTION_PAY_ITEM_TYPE = "Deduction"
OTHER_PAY_ITEM_TYPES = {"Earning", "Memo Calc"}
# calcParams[].paramType has no documented values. Only these self-describing
# labels are read; others (live: "Amount2", "Rate") stay in unmapped.
CALC_PARAM_SLOTS = {"Amount": "amount", "Percent": "percent"}
# Fields the live payItems response returns that EmployeePayItemModel does not list.
LIVE_ONLY_PAY_ITEM_FIELDS = ("balance",)


def _merge(base: Dict[str, Any], overlay: Any) -> Dict[str, Any]:
    if not isinstance(overlay, dict):
        return base
    merged = dict(base)
    merged.update(overlay)
    return merged


class _IsolvedEmployeeMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.bundle = bundle
        self.issues = issues
        self.company_id = f"{bundle.request['client_id']}-{bundle.request['legal_id']}"
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.legal_codes: set[str] = set()

    def _assemble(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Overlay detail, personal and nameAddress responses onto the list record."""
        employee_id = text(record.get("id"))
        merged = _merge(record, (self.bundle.response("employee_detail") or {}).get(employee_id))
        personal = (self.bundle.response("personal") or {}).get(employee_id)
        if isinstance(personal, dict):
            merged["personal"] = _merge(merged.get("personal") or {}, personal)
        name_address = (self.bundle.response("name_address") or {}).get(employee_id)
        if isinstance(name_address, dict):
            merged["nameAddress"] = _merge(merged.get("nameAddress") or {}, name_address)
        return merged

    def map(self, record: Dict[str, Any]) -> Employee:
        raw = self._assemble(record)
        r = Reader(raw)
        employee_id = text(r.get("id")) or ""
        key = f"{self.company_key}:{employee_id}"
        name, personal = r.sub("nameAddress"), r.sub("personal")
        if name.data is None:
            self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "nameAddress",
                            "name and home address set null", key)

        secondary = {}
        for field in ("employeeNumber", "uniqueId", "timeclockId"):
            value = text(r.get(field))
            if value is not None:
                secondary[field] = value
        legal_code = text(r.get("legalCode"))
        if legal_code:
            secondary["legalCode"] = legal_code
            self.legal_codes.add(legal_code)

        person = Person(
            first_name=text(name.get("firstName")),
            middle_name=text(name.get("middleName")),
            last_name=text(name.get("lastName")),
            preferred_name=text(name.get("preferredName")),
            birth_date=self.issues.date(r.get("birthDate"), "birthDate", key),
            gender=self.issues.code(GENDER, r.get("gender"), "gender", key),
            marital_status=self.issues.code(MARITAL_STATUS, r.get("maritalStatus"), "maritalStatus", key),
            citizenship=self.issues.code(CITIZENSHIP, r.get("citizenship"), "citizenship", key),
            ethnicity=Collector.raw_code(r.get("ethnicOrigin")),
            ssn_last4=self.issues.last4(r.get("ssn"), "ssn", key),
        )

        addresses = []
        home = {
            "line1": text(name.get("address1")), "line2": text(name.get("address2")),
            "city": text(name.get("city")), "region": text(name.get("state")),
            "postal_code": text(name.get("zipCode")),
        }
        if any(v is not None for v in home.values()):
            addresses.append(Address(kind=AddressKind.HOME, **home))
        override = r.sub("overrideAddress")
        if isinstance(override.data, dict):
            w2 = {
                "line1": text(override.get("address1")), "line2": text(override.get("address2")),
                "city": text(override.get("city")), "region": text(override.get("state")),
                "postal_code": text(override.get("zipCode")),
            }
            if any(v is not None for v in w2.values()):
                addresses.append(Address(kind=AddressKind.W2, **w2))
        phones = []
        for field, kind in (("homePhone", PhoneKind.HOME), ("mobilePhone", PhoneKind.MOBILE),
                            ("officePhone", PhoneKind.WORK)):
            number = text(personal.get(field))
            if number is not None:
                phones.append(Phone(kind=kind, number=number))
        emails = []
        work_email = text(r.get("emailAddress"))  # spec: "Employee E-Mail Address" (kind not stated)
        if work_email is not None:
            emails.append(Email(kind=EmailKind.UNKNOWN, address=work_email))
        personal_email = text(personal.get("personalEmailAddress"))
        if personal_email is not None:
            emails.append(Email(kind=EmailKind.PERSONAL, address=personal_email))

        employment = Employment(
            status=self.issues.code(EMPLOYMENT_STATUS, r.get("employmentStatus"), "employmentStatus", key),
            status_date=self.issues.date(r.get("statusDate"), "statusDate", key),
            employment_type=self.issues.code(EMPLOYMENT_CATEGORY, r.get("employmentCategoryCode"),
                                             "employmentCategoryCode", key),
            hire_date=self.issues.date(r.get("hireDate"), "hireDate", key),
            original_hire_date=self.issues.date(r.get("originalHireDate"), "originalHireDate", key),
            rehire_date=self.issues.date(r.get("rehireDate"), "rehireDate", key),
            termination_date=self.issues.date(r.get("terminationDate"), "terminationDate", key),
            termination_reason=Collector.raw_code(r.get("terminationReason")),
            rehire_eligible=boolean(r.get("eligibleForRehire")),
            flsa_exempt=boolean(r.get("jobFLSAExempt")),
        )

        department = location = None
        organizations = r.peek("organizations")  # consume only the rows we read
        if isinstance(organizations, list):
            for index, org in enumerate(organizations):
                if not isinstance(org, dict):
                    continue
                org_reader = Reader(org, f"organizations[{index}]", r.used)
                title = org_reader.peek("title")
                if title == "Department" and department is None:
                    org_reader.consume("title")
                    department = Collector.raw_code(org_reader.get("value"), org_reader.get("valueDescription"))
                elif title == "Location" and location is None:
                    org_reader.consume("title")
                    location = Collector.raw_code(org_reader.get("value"), org_reader.get("valueDescription"))
        if location is None:
            location = Collector.raw_code(r.get("workLocation"), r.get("workLocationDashDescription"))
        manager = r.sub("assignedManager")
        job = Job(
            title=text(r.get("jobTitle")),
            job_code=Collector.raw_code(r.get("jobCode")),
            department=department,
            location=location,
            manager_employee_id=text(manager.get("id")) if isinstance(manager.data, dict) else None,
            job_start_date=self.issues.date(r.get("jobEffectiveDate"), "jobEffectiveDate", key),
        )

        standard_hours = self.issues.decimal(r.get("normalHours"), "normalHours", key)
        compensation = Compensation(
            pay_type=self.issues.code(PAY_TYPE, r.get("payType"), "payType", key),
            pay_frequency=self.issues.code(PAY_FREQUENCY, r.get("payFrequency"), "payFrequency", key,
                                           label=text(r.get("payGroup"))),
            hourly_rate=self.issues.money(r.get("hourlyRate"), "hourlyRate", key),
            annual_amount=self.issues.money(r.get("annualSalary"), "annualSalary", key),
            per_period_amount=self.issues.money(r.get("perPaySalary"), "perPaySalary", key),
            standard_hours=standard_hours,
            standard_hours_period=STANDARD_HOURS_PERIOD if standard_hours is not None else None,
            effective_date=self.issues.date(r.get("salaryEffectiveDate"), "salaryEffectiveDate", key),
        )

        return Employee(
            key=key,
            company_key=self.company_key,
            source=SourceRef(provider=PROVIDER, company_id=self.company_id, employee_id=employee_id,
                             secondary_ids=secondary),
            person=person,
            contact=Contact(addresses=addresses, phones=phones, emails=emails),
            employment=employment,
            job=job,
            compensation=compensation,
            unmapped=r.unmapped(),
        )


class _IsolvedDepositMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.issues = issues
        self.company_id = f"{bundle.request['client_id']}-{bundle.request['legal_id']}"
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.responses = bundle.response("direct_deposits") or {}

    def map(self, employee_id: str) -> list[DirectDeposit]:
        employee_key = f"{self.company_key}:{employee_id}"
        if employee_id not in self.responses:
            self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "direct_deposits",
                            "no deposit lines emitted", employee_key,
                            message=f"bundle has no responses.direct_deposits[{employee_id!r}] entry")
            return []
        lines = self.responses[employee_id]
        if not isinstance(lines, list):
            raise ValueError(f"responses.direct_deposits[{employee_id!r}] must be a list")
        return [self._line(Reader(line, f"direct_deposits[{index}]"), employee_id, employee_key, index)
                for index, line in enumerate(lines) if isinstance(line, dict)]

    def _allocation(self, r: Reader, key: str) -> Allocation:
        amount, percent, sequence = r.peek("amount"), r.peek("percent"), r.peek("sequenceNumber")
        for field, value in (("amount", amount), ("percent", percent)):
            if value is None:
                r.consume(field)
        if sequence == 0 and not isinstance(sequence, bool):
            if amount is not None or percent is not None:
                self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path("sequenceNumber"),
                                "amount and percent kept in unmapped", key, sequence,
                                f"sequence 0 is the Net Pay line but an amount or percent is set "
                                f"({DEPOSIT}/sequenceNumber)")
            return Allocation(method=METHOD_NET_PAY)
        if amount is not None and percent is not None:
            action = "method set to unknown; amount and percent kept in unmapped"
            message = "both amount and percent are set; the spec says only one may be"
        elif amount is not None:
            return Allocation(method=METHOD_FROM_AMOUNT,
                              amount=self.issues.money(r.get("amount"), r.path("amount"), key))
        elif percent is not None:
            return Allocation(method=METHOD_FROM_PERCENT,
                              percent=self.issues.decimal(r.get("percent"), r.path("percent"), key))
        else:
            action = "method set to unknown"
            message = "neither amount nor percent is set and the sequence is not 0 (Net Pay)"
        self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path("amount"), action, key,
                        message=f"{message} ({DEPOSIT}/amount, {DEPOSIT}/percent)")
        return Allocation(method=METHOD_UNKNOWN)

    def _line(self, r: Reader, employee_id: str, employee_key: str, index: int) -> DirectDeposit:
        deposit_id = text(r.get("id")) or str(index)
        key = f"{employee_key}:dd:{deposit_id}"
        sequence = r.get("sequenceNumber")
        return DirectDeposit(
            key=key,
            employee_key=employee_key,
            company_key=self.company_key,
            source=DepositSource(provider=PROVIDER, company_id=self.company_id, employee_id=employee_id,
                                 deposit_id=deposit_id),
            bank_name=text(r.get("bankName")),
            routing_number=text(r.get("routingNumber")),
            account_number_last4=self.issues.last4(r.get("accountNumber"), r.path("accountNumber"), key),
            account_type=self.issues.code(DEPOSIT_ACCOUNT_TYPE, r.get("accountType"), r.path("accountType"), key),
            allocation=self._allocation(r, key),
            priority=sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else None,
            status=self.issues.code(DEPOSIT_STATUS, r.get("status"), r.path("status"), key),
            unmapped=r.unmapped(),
        )


class _IsolvedDeductionMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.issues = issues
        self.company_id = f"{bundle.request['client_id']}-{bundle.request['legal_id']}"
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.responses = bundle.response("pay_items") or {}
        self.reported: set[str] = set()

    def _report_once(self, marker: str, code: IssueCode, path: str, raw: Any, message: str) -> None:
        if marker in self.reported:
            return
        self.reported.add(marker)
        severity = Severity.INFO if code is IssueCode.SPEC_LIVE_MISMATCH else Severity.WARNING
        action = "kept in unmapped" if code is IssueCode.SPEC_LIVE_MISMATCH else "kept raw value in unmapped"
        self.issues.add(code, severity, path, action, raw_value=raw, message=message)

    def map(self, employee_id: str) -> list[Deduction]:
        employee_key = f"{self.company_key}:{employee_id}"
        if employee_id not in self.responses:
            self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "pay_items",
                            "no deduction lines emitted", employee_key,
                            message=f"bundle has no responses.pay_items[{employee_id!r}] entry")
            return []
        items = self.responses[employee_id]
        if not isinstance(items, list):
            raise ValueError(f"responses.pay_items[{employee_id!r}] must be a list")
        records = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            r = Reader(item, f"pay_items[{index}]")
            kind = r.peek("payItemType")
            if kind == DEDUCTION_PAY_ITEM_TYPE:
                r.consume("payItemType")
                records.append(self._line(r, employee_id, employee_key, index))
            elif kind not in OTHER_PAY_ITEM_TYPES:
                self.issues.add(IssueCode.UNMAPPED_LABEL, Severity.WARNING, r.path("payItemType"),
                                "pay item skipped", employee_key, kind,
                                f"payItemType is not one of the labels seen live ({PAY_ITEM}/payItemType; "
                                f"labels from {LIVE_PAY_ITEMS})")
        return records

    def _calculation(self, r: Reader, key: str) -> Calculation:
        params = r.peek("calcParams")
        values: Dict[str, Any] = {}
        for index, param in enumerate(params if isinstance(params, list) else []):
            if not isinstance(param, dict):
                continue
            p = r.sub("calcParams", index)
            label = p.peek("paramType")
            slot = CALC_PARAM_SLOTS.get(label) if isinstance(label, str) else None
            if slot is None:
                self._report_once(f"paramType:{label!r}", IssueCode.UNMAPPED_LABEL, p.path("paramType"), label,
                                  f"calcParams.paramType has no documented values and this label is not on "
                                  f"the allowlist ({PAY_ITEM}/calcParams)")
                continue
            if slot in values:
                continue
            p.consume("paramType")
            values[slot] = (p.get("paramValue"), p.path("paramValue"))
        amount = percent = None
        if "amount" in values:
            amount = self.issues.money(*values["amount"], key)
        if "percent" in values:
            percent = self.issues.decimal(*values["percent"], key)
        return Calculation(amount=amount, percent=percent)

    def _line(self, r: Reader, employee_id: str, employee_key: str, index: int) -> Deduction:
        deduction_id = text(r.get("id")) or str(index)
        key = f"{employee_key}:ded:{deduction_id}"
        for field in LIVE_ONLY_PAY_ITEM_FIELDS:
            if r.has(field):
                self._report_once(f"live:{field}", IssueCode.SPEC_LIVE_MISMATCH, r.path(field), None,
                                  f"live API returns '{field}', which EmployeePayItemModel does not list "
                                  f"({PAY_ITEM})")
        code, name = text(r.get("payItemCode")), text(r.get("payItemName"))
        start = self.issues.date(r.get("startDate"), r.path("startDate"), key)
        end = self.issues.date(r.get("stopDate"), r.path("stopDate"), key)
        return Deduction(
            key=key,
            employee_key=employee_key,
            company_key=self.company_key,
            source=DeductionSource(provider=PROVIDER, company_id=self.company_id, employee_id=employee_id,
                                   deduction_id=deduction_id),
            code=CodedValue(raw=code, label=name) if code is not None or name is not None else None,
            calculation=self._calculation(r, key),
            effective=DateRange(start=start, end=end) if start is not None or end is not None else None,
            unmapped=r.unmapped(),
        )


def _employee_records(bundle: Bundle) -> Iterator[Dict[str, Any]]:
    for index, page in enumerate(bundle.response("employees") or []):
        if not isinstance(page, dict):
            raise ValueError(f"responses.employees[{index}] must be an object")
        results = page.get("results")
        if not isinstance(results, list):
            raise ValueError(f"responses.employees[{index}].results must be a list")
        for record in results:
            if isinstance(record, dict):
                yield record


def _company(company_id: str, legal_codes: set[str], issues: Collector) -> Company:
    issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses",
               "company name set null",
               message="the employees endpoint does not return the legal company name; "
                       "a legal endpoint is a later task")
    secondary = {}
    if len(legal_codes) == 1:
        secondary["legalCode"] = next(iter(legal_codes))
    return Company(
        key=f"{PROVIDER}:{company_id}",
        source=CompanySource(provider=PROVIDER, company_id=company_id, secondary_ids=secondary),
    )


def _check_provider(bundle: Bundle) -> None:
    if bundle.provider != PROVIDER:
        raise ValueError(f"bundle provider is {bundle.provider!r}, expected {PROVIDER!r}")


def normalize_employees(bundle: Bundle) -> NormalizedOutput:
    _check_provider(bundle)
    issues = Collector()
    mapper = _IsolvedEmployeeMapper(bundle, issues)
    employees = [mapper.map(record) for record in _employee_records(bundle)]
    company = _company(mapper.company_id, mapper.legal_codes, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, employees=employees, issues=issues.issues)


def normalize_direct_deposits(bundle: Bundle) -> NormalizedOutput:
    """One record per deposit line, for every employee in the pages and then any other captured id."""
    _check_provider(bundle)
    issues = Collector()
    mapper = _IsolvedDepositMapper(bundle, issues)
    employee_ids, legal_codes = [], set()
    for record in _employee_records(bundle):
        employee_ids.append(text(record.get("id")) or "")
        legal_code = text(record.get("legalCode"))
        if legal_code:
            legal_codes.add(legal_code)
    listed = set(employee_ids)
    employee_ids += [employee_id for employee_id in mapper.responses if employee_id not in listed]
    deposits = [deposit for employee_id in employee_ids for deposit in mapper.map(employee_id)]
    company = _company(mapper.company_id, legal_codes, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, direct_deposits=deposits, issues=issues.issues)


def normalize_deductions(bundle: Bundle) -> NormalizedOutput:
    """One record per Deduction pay item, for every employee in the pages and then any other captured id."""
    _check_provider(bundle)
    issues = Collector()
    mapper = _IsolvedDeductionMapper(bundle, issues)
    employee_ids, legal_codes = [], set()
    for record in _employee_records(bundle):
        employee_ids.append(text(record.get("id")) or "")
        legal_code = text(record.get("legalCode"))
        if legal_code:
            legal_codes.add(legal_code)
    listed = set(employee_ids)
    employee_ids += [employee_id for employee_id in mapper.responses if employee_id not in listed]
    deductions = [record for employee_id in employee_ids for record in mapper.map(employee_id)]
    company = _company(mapper.company_id, legal_codes, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, deductions=deductions, issues=issues.issues)


NORMALIZERS = {"employee": normalize_employees, "direct-deposit": normalize_direct_deposits,
               "deduction": normalize_deductions}


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Dispatch wrapper used by the CLI. ``response`` is a parsed capture bundle."""
    if entity in NORMALIZERS:
        bundle = response if isinstance(response, Bundle) else parse_bundle(response, entity=entity)
        return NORMALIZERS[entity](bundle)
    raise NotImplementedError(f"isolved {entity} normalization is not implemented yet.")
