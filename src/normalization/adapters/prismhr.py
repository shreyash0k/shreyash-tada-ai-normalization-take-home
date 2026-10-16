"""PrismHR employee and direct deposit adapter.

Input: a capture bundle whose ``responses.get_employee`` holds raw
``GET /employee/v1/getEmployee`` responses requested with
``options=Person,ContactInformation,Client,Compensation``. Each response
carries up to twenty ``employee[]`` records with ``person``,
``contactInformation``, ``client`` and ``compensation`` sections.

Direct deposits come from the same call requested with
``options=DirectDeposit`` (``responses.get_employee_direct_deposit``): each
employee's ``directDeposit`` header holds the ``achVoucher[]`` bank lines.

Every code table below cites the OpenAPI description it rests on. Codes the
spec does not explain stay raw with an ``undocumented_code`` issue.
"""
from typing import Any, Dict, Optional

from ..bundle import Bundle, parse_bundle
from ..canonical import (
    AccountType,
    Address,
    AddressKind,
    Allocation,
    AllocationMethod,
    Citizenship,
    CodedValue,
    Company,
    CompanySource,
    Compensation,
    Contact,
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

PROVIDER = "prismhr"
SPEC = "contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas"

STATUS_CLASS = CodeTable(
    "client.statusClass", EmploymentStatus,
    {"A": EmploymentStatus.ACTIVE, "L": EmploymentStatus.ON_LEAVE, "T": EmploymentStatus.TERMINATED},
    f"{SPEC}/Client/properties/statusClass/description",
)
TYPE_CLASS = CodeTable(
    "client.typeClass", EmploymentType,
    {"F": EmploymentType.FULL_TIME, "P": EmploymentType.PART_TIME},
    "contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/paths/~1employee~1v1~1getEmployeeList"
    "/get/parameters (typeClass: '(F)ull-time or (P)art-time')",
)
GENDER = CodeTable(
    "person.gender", Gender,
    {"M": Gender.MALE, "F": Gender.FEMALE, "X": Gender.NONBINARY, "D": Gender.DECLINED},
    f"{SPEC}/NewHireEmployee/properties/gender/description (Person.gender lists M, F, X or D)",
)
MARITAL_STATUS = CodeTable(
    "person.maritalStatus", MaritalStatus,
    {"S": MaritalStatus.SINGLE, "M": MaritalStatus.MARRIED, "D": MaritalStatus.DIVORCED,
     "W": MaritalStatus.WIDOWED, "C": MaritalStatus.CIVIL_UNION, "O": MaritalStatus.OTHER},
    f"{SPEC}/Person/properties/maritalStatus/description",
)
CITIZENSHIP = CodeTable(
    "compensation.citizenshipStatus", Citizenship,
    {"Z01": Citizenship.CITIZEN, "Z02": Citizenship.NONCITIZEN_NATIONAL,
     "Z03": Citizenship.PERMANENT_RESIDENT, "Z04": Citizenship.WORK_PERMIT},
    f"{SPEC}/Compensation/properties/citizenshipStatus/description",
)
PAY_METHOD = CodeTable(
    "compensation.payMethod", PayType,
    {"S": PayType.SALARY, "H": PayType.HOURLY, "C": PayType.COMMISSION, "D": PayType.DRIVER},
    f"{SPEC}/Compensation/properties/payMethod/description",
)
HOURLY_PAY_PERIOD = CodeTable(
    "compensation.hourlyPayPeriod", PayPeriod,
    {"H": PayPeriod.HOURLY, "W": PayPeriod.WEEKLY, "B": PayPeriod.BIWEEKLY,
     "S": PayPeriod.SEMIMONTHLY, "M": PayPeriod.MONTHLY, "Y": PayPeriod.ANNUAL},
    f"{SPEC}/Compensation/properties/hourlyPayPeriod/description",
)
# Compensation.payPeriod is described only as "pay period associated with the
# payGroup"; its codes are not explained on this schema, so none map.
PAY_PERIOD = CodeTable(
    "compensation.payPeriod", PayPeriod, {},
    f"{SPEC}/Compensation/properties/payPeriod/description (no code meanings)",
)
# Spec says "standard hours per pay period (for example, 40.00 if 40 hours per week)".
STANDARD_HOURS_PERIOD = CodedValue(raw=None, label="per pay period", value=PayPeriod.PAY_PERIOD)

# 'C' is "checking account or pay card"; pay cards are set up as checking accounts.
ACCOUNT_TYPE = CodeTable(
    "achVoucher.accountType", AccountType,
    {"C": AccountType.CHECKING, "S": AccountType.SAVINGS, "IP": AccountType.INSTANT_PAY},
    f"{SPEC}/AchVoucher/properties/accountType/description",
)
# 'FS' is fixed, skipped when the full amount cannot be taken; the skip rule stays in the raw code.
DEPOSIT_METHOD = CodeTable(
    "achVoucher.method", AllocationMethod,
    {"F": AllocationMethod.FIXED_AMOUNT, "FS": AllocationMethod.FIXED_AMOUNT,
     "P": AllocationMethod.PERCENT, "PN": AllocationMethod.PERCENT_OF_NET,
     "B": AllocationMethod.REMAINDER},
    f"{SPEC}/AchVoucher/properties/method/description",
)
DEPOSIT_STATUS = CodeTable(
    "achVoucher.status", DepositStatus,
    {"D": DepositStatus.ACTIVE, "I": DepositStatus.INACTIVE, "P": DepositStatus.PRENOTE},
    f"{SPEC}/AchVoucher/properties/status/description",
)
AMOUNT_METHODS = {AllocationMethod.FIXED_AMOUNT}
PERCENT_METHODS = {AllocationMethod.PERCENT, AllocationMethod.PERCENT_OF_NET}

# Property names where the live API differs from the OpenAPI document:
# (section, live name, spec name). Spec name None means the field is absent from the spec.
LIVE_SHAPE_DIFFERENCES = (
    ("person", "employerId", "employerIds"),
    ("person", "autoPolicy", "autoPolicies"),
    ("client", "hawaiiMedWaiver", "hawaiiMedWaivers"),
    ("compensation", "payPeriodsPerWeek", None),
)
SPEC_SECTION = {"person": "Person", "client": "Client", "compensation": "Compensation",
                "contactInformation": "ContactInformation"}


def _postal(zipcode: Optional[str], suffix: Optional[str]) -> Optional[str]:
    if zipcode is None:
        return None
    return f"{zipcode}-{suffix}" if suffix else zipcode


def _address(reader: Reader, kind: AddressKind, line1, line2, city, state, zipcode,
             suffix=None, country=None) -> Optional[Address]:
    values = {
        "line1": text(reader.get(line1)),
        "line2": text(reader.get(line2)) if line2 else None,
        "city": text(reader.get(city)),
        "region": text(reader.get(state)),
        "postal_code": _postal(text(reader.get(zipcode)), text(reader.get(suffix)) if suffix else None),
        "country": text(reader.get(country)) if country else None,
    }
    if all(v is None for v in values.values()):
        return None
    return Address(kind=kind, **values)


def _phone(reader: Reader, kind: PhoneKind, key: str, ext_key: Optional[str] = None) -> Optional[Phone]:
    number = text(reader.get(key))
    extension = text(reader.get(ext_key)) if ext_key else None
    if number is None:
        return None
    return Phone(kind=kind, number=number, extension=extension)


def _email(reader: Reader, kind: EmailKind, key: str) -> Optional[Email]:
    address = text(reader.get(key))
    return None if address is None else Email(kind=kind, address=address)


class _PrismEmployeeMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.bundle = bundle
        self.issues = issues
        self.company_id = bundle.request["client_id"]
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.reported_mismatch: set[str] = set()

    def _report_live_shape(self, record: Reader) -> None:
        """Emit spec_live_mismatch once per bundle for each renamed or extra field."""
        for section, live, spec_name in LIVE_SHAPE_DIFFERENCES:
            path = record.path(section, live)
            if path in self.reported_mismatch or not record.has(section, live):
                continue
            self.reported_mismatch.add(path)
            schema = SPEC_SECTION[section]
            if spec_name:
                message = (f"live API returns '{live}' where the OpenAPI document names '{spec_name}' "
                           f"({SPEC}/{schema}/properties/{spec_name})")
            else:
                message = (f"live API returns '{live}', which the OpenAPI document does not list on "
                           f"{schema} ({SPEC}/{schema}/properties)")
            self.issues.add(IssueCode.SPEC_LIVE_MISMATCH, Severity.INFO, path,
                            "kept under the live name in unmapped", message=message)

    def map(self, raw: Dict[str, Any]) -> Employee:
        r = Reader(raw)
        employee_id = text(r.get("id")) or ""
        key = f"{self.company_key}:{employee_id}"
        person, contact, client, comp = r.sub("person"), r.sub("contactInformation"), r.sub("client"), r.sub("compensation")
        for name, section in (("person", person), ("contactInformation", contact),
                              ("client", client), ("compensation", comp)):
            if section.data is None:
                self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, name,
                                "fields from this section set null", key,
                                message=f"getEmployee response lacks the '{name}' section; "
                                        "request options=Person,ContactInformation,Client,Compensation")
        self._report_live_shape(r)

        secondary = {}
        for label, reader, field in (("clientEmployeeId", client, "clientEmployeeId"),
                                     ("legacyEmployeeId", person, "legacyEmployeeId")):
            value = text(reader.get(field))
            if value is not None:
                secondary[label] = value

        person_model = Person(
            first_name=text(r.get("firstName")),
            middle_name=text(r.get("middleInitial")),
            last_name=text(r.get("lastName")),
            preferred_name=text(r.get("preferredName")),
            birth_date=self.issues.date(person.get("birthDate"), person.path("birthDate"), key),
            gender=self.issues.code(GENDER, person.get("gender"), person.path("gender"), key),
            marital_status=self.issues.code(MARITAL_STATUS, person.get("maritalStatus"),
                                            person.path("maritalStatus"), key),
            # Live returns prose ("A lawful permanent resident") where the spec documents Z01-Z04.
            citizenship=self.issues.code(CITIZENSHIP, comp.get("citizenshipStatus"),
                                         comp.path("citizenshipStatus"), key,
                                         issue_code=IssueCode.UNMAPPED_LABEL),
            ethnicity=Collector.raw_code(person.get("ethnicCode")),
            ssn_last4=self.issues.last4(comp.get("ssn"), comp.path("ssn"), key),
        )

        addresses = [a for a in (
            _address(contact, AddressKind.HOME, "addressLine1", "addressLine2", "city", "state",
                     "zipcode", "zipSuffix"),
            _address(client, AddressKind.MAILING, "addressLine1", "addressLine2", "city", "state",
                     "zip", "zipSuffix"),
            _address(person, AddressKind.W2, "w2AddressLine1", "w2AddressLine2", "w2City",
                     "w2State", "w2PostalCode"),
        ) if a is not None]
        address_info = (self.bundle.response("get_address_info") or {}).get(employee_id)
        if isinstance(address_info, dict):
            alt = Reader(address_info).sub("addressInfo", "altAddress")
            mailing = _address(alt, AddressKind.MAILING, "addressLine1", "addressLine2", "city",
                               "stateAbbr", "zipCode", "zipSuffix", "mailAddressCountry")
            if mailing is not None and not any(a.kind is AddressKind.MAILING for a in addresses):
                addresses.append(mailing)
        phones = [p for p in (
            _phone(contact, PhoneKind.HOME, "homePhone"),
            _phone(contact, PhoneKind.MOBILE, "mobilePhone"),
            _phone(client, PhoneKind.WORK, "workPhone", "workPhoneExt"),
        ) if p is not None]
        emails = [e for e in (
            _email(contact, EmailKind.UNKNOWN, "emailAddress"),  # spec: "the employee's email address"
            _email(client, EmailKind.WORK, "workEmail"),
        ) if e is not None]

        rehire_ok = text(client.get("rehireOk"))
        employment = Employment(
            status=self.issues.code(STATUS_CLASS, client.get("statusClass"), client.path("statusClass"),
                                    key, label=text(client.get("employeeStatus"))),
            status_date=self.issues.date(client.get("statusDate"), client.path("statusDate"), key),
            employment_type=self.issues.code(TYPE_CLASS, client.get("typeClass"), client.path("typeClass"),
                                             key, label=text(client.get("employeeType"))),
            hire_date=self.issues.date(client.get("lastHireDate"), client.path("lastHireDate"), key),
            original_hire_date=self.issues.date(client.get("firstHireDate"), client.path("firstHireDate"), key),
            seniority_date=self.issues.date(client.get("seniorityDate"), client.path("seniorityDate"), key),
            termination_reason=Collector.raw_code(client.get("termReasonCode"), client.get("termExplanation")),
            rehire_eligible={"Y": True, "N": False}.get(rehire_ok) if rehire_ok else None,
            flsa_exempt=boolean(client.get("flsaExempt")),
            contractor_1099=boolean(client.get("employee1099")),
        )

        job = Job(
            job_code=Collector.raw_code(client.get("jobCode")),
            department=Collector.raw_code(client.get("homeDepartment")),
            location=Collector.raw_code(client.get("homeLocation")),
            division=Collector.raw_code(client.get("homeDivision")),
            manager_employee_id=text(client.get("manager")),
            job_start_date=self.issues.date(client.get("jobStartDate"), client.path("jobStartDate"), key),
        )

        standard_hours = self.issues.decimal(comp.get("standardHours"), comp.path("standardHours"), key)
        compensation = Compensation(
            pay_type=self.issues.code(PAY_METHOD, comp.get("payMethod"), comp.path("payMethod"), key),
            pay_frequency=self.issues.code(PAY_PERIOD, comp.get("payPeriod"), comp.path("payPeriod"), key),
            rate=self.issues.money(comp.get("hourlyPayRate"), comp.path("hourlyPayRate"), key),
            rate_period=self.issues.code(HOURLY_PAY_PERIOD, comp.get("hourlyPayPeriod"),
                                         comp.path("hourlyPayPeriod"), key),
            hourly_rate=self.issues.money(comp.get("hourlyPay"), comp.path("hourlyPay"), key),
            annual_amount=self.issues.money(comp.get("annualPay"), comp.path("annualPay"), key),
            per_period_amount=self.issues.money(comp.get("salary"), comp.path("salary"), key),
            standard_hours=standard_hours,
            standard_hours_period=STANDARD_HOURS_PERIOD if standard_hours is not None else None,
            effective_date=self.issues.date(comp.get("effectiveDate"), comp.path("effectiveDate"), key),
        )

        return Employee(
            key=key,
            company_key=self.company_key,
            source=SourceRef(provider=PROVIDER, company_id=self.company_id, employee_id=employee_id,
                             secondary_ids=secondary),
            person=person_model,
            contact=Contact(addresses=addresses, phones=phones, emails=emails),
            employment=employment,
            job=job,
            compensation=compensation,
            unmapped=r.unmapped(),
        )


class _PrismDepositMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.issues = issues
        self.company_id = bundle.request["client_id"]
        self.company_key = f"{PROVIDER}:{self.company_id}"

    def map(self, raw: Dict[str, Any]) -> list[DirectDeposit]:
        employee_id = text(raw.get("id")) or ""
        employee_key = f"{self.company_key}:{employee_id}"
        header = raw.get("directDeposit")
        if not isinstance(header, dict):
            self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "directDeposit",
                            "no deposit lines emitted", employee_key,
                            message="getEmployee response lacks the 'directDeposit' section; "
                                    "request options=DirectDeposit")
            return []
        header_reader = Reader(header, "directDeposit")
        header_reader.consume("achVoucher")
        shared = header_reader.unmapped()
        lines = header.get("achVoucher") or []
        if not isinstance(lines, list):
            raise ValueError(f"directDeposit.achVoucher of employee {employee_id!r} must be a list")
        deposits = []
        for index, line in enumerate(lines):
            if isinstance(line, dict):
                deposits.append(self._line(Reader(line, f"directDeposit.achVoucher[{index}]"),
                                           employee_id, employee_key, str(index), shared))
        return deposits

    def _line(self, r: Reader, employee_id: str, employee_key: str, deposit_id: str,
              shared: Dict[str, Any]) -> DirectDeposit:
        key = f"{employee_key}:dd:{deposit_id}"
        method = self.issues.code(DEPOSIT_METHOD, r.get("method"), r.path("method"), key)
        amount = percent = None
        member = method.value if method is not None else None
        raw_amount = r.peek("amount")
        if raw_amount is None:
            r.consume("amount")
        if member is AllocationMethod.REMAINDER:
            if raw_amount is not None:
                self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path("amount"),
                                "kept in unmapped", key, raw_amount,
                                f"method 'B' takes the remaining balance and must not carry an amount "
                                f"({SPEC}/AchVoucher/properties/amount/description)")
        elif member in AMOUNT_METHODS or member in PERCENT_METHODS:
            if raw_amount is None:
                self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path("amount"),
                                "amount set null", key,
                                message=f"amount is mandatory for method {method.raw!r} "
                                        f"({SPEC}/AchVoucher/properties/amount/description)")
            elif member in AMOUNT_METHODS:
                amount = self.issues.money(r.get("amount"), r.path("amount"), key)
            else:
                percent = self.issues.decimal(r.get("amount"), r.path("amount"), key)
        return DirectDeposit(
            key=key,
            employee_key=employee_key,
            company_key=self.company_key,
            source=DepositSource(provider=PROVIDER, company_id=self.company_id, employee_id=employee_id,
                                 deposit_id=deposit_id),
            bank_name=text(r.get("bankName")),
            routing_number=text(r.get("transitNum")),
            account_number_last4=self.issues.last4(r.get("accountNum"), r.path("accountNum"), key),
            account_type=self.issues.code(ACCOUNT_TYPE, r.get("accountType"), r.path("accountType"), key),
            allocation=Allocation(method=method, amount=amount, percent=percent),
            status=self.issues.code(DEPOSIT_STATUS, r.get("status"), r.path("status"), key),
            unmapped={**r.unmapped(), **shared},
        )


def _employee_records(bundle: Bundle, response_key: str, issues: Collector):
    """Yield every employee record of the getEmployee responses under ``response_key``."""
    for index, response in enumerate(bundle.response(response_key) or []):
        if not isinstance(response, dict):
            raise ValueError(f"responses.{response_key}[{index}] must be an object")
        error_code = response.get("errorCode")
        if error_code not in (None, "0", 0):
            issues.add(IssueCode.MISSING_SECTION, Severity.WARNING,
                       f"responses.{response_key}[{index}].errorCode", "response skipped",
                       raw_value=error_code, message=text(response.get("errorMessage")))
            continue
        records = response.get("employee") or []
        if not isinstance(records, list):
            raise ValueError(f"responses.{response_key}[{index}].employee must be a list")
        for record in records:
            if isinstance(record, dict):
                yield record


def _company(company_id: str, issues: Collector) -> Company:
    issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses",
               "company name set null",
               message="getEmployee does not return the client name; a client endpoint is a later task")
    return Company(key=f"{PROVIDER}:{company_id}",
                   source=CompanySource(provider=PROVIDER, company_id=company_id))


def _check_provider(bundle: Bundle) -> None:
    if bundle.provider != PROVIDER:
        raise ValueError(f"bundle provider is {bundle.provider!r}, expected {PROVIDER!r}")


def normalize_employees(bundle: Bundle) -> NormalizedOutput:
    _check_provider(bundle)
    issues = Collector()
    mapper = _PrismEmployeeMapper(bundle, issues)
    employees = [mapper.map(record) for record in _employee_records(bundle, "get_employee", issues)]
    company = _company(mapper.company_id, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, employees=employees, issues=issues.issues)


def normalize_direct_deposits(bundle: Bundle) -> NormalizedOutput:
    _check_provider(bundle)
    issues = Collector()
    mapper = _PrismDepositMapper(bundle, issues)
    deposits = []
    for record in _employee_records(bundle, "get_employee_direct_deposit", issues):
        deposits.extend(mapper.map(record))
    company = _company(mapper.company_id, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, direct_deposits=deposits, issues=issues.issues)


NORMALIZERS = {"employee": normalize_employees, "direct-deposit": normalize_direct_deposits}


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Dispatch wrapper used by the CLI. ``response`` is a parsed capture bundle."""
    if entity in NORMALIZERS:
        bundle = response if isinstance(response, Bundle) else parse_bundle(response, entity=entity)
        return NORMALIZERS[entity](bundle)
    raise NotImplementedError(f"PrismHR {entity} normalization is not implemented yet.")
