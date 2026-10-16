"""PrismHR employee adapter.

Input: a capture bundle whose ``responses.get_employee`` holds raw
``GET /employee/v1/getEmployee`` responses requested with
``options=Person,ContactInformation,Client,Compensation``. Each response
carries up to twenty ``employee[]`` records with ``person``,
``contactInformation``, ``client`` and ``compensation`` sections.

Every code table below cites the OpenAPI description it rests on. Codes the
spec does not explain stay raw with an ``undocumented_code`` issue.
"""
from typing import Any, Dict, Optional

from ..bundle import Bundle
from ..canonical import (
    Address,
    AddressKind,
    Citizenship,
    CodedValue,
    Company,
    CompanySource,
    Compensation,
    Contact,
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
            ssn_last4=self.issues.ssn_last4(comp.get("ssn"), comp.path("ssn"), key),
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


def normalize_employees(bundle: Bundle) -> NormalizedOutput:
    if bundle.provider != PROVIDER:
        raise ValueError(f"bundle provider is {bundle.provider!r}, expected {PROVIDER!r}")
    issues = Collector()
    mapper = _PrismEmployeeMapper(bundle, issues)
    employees = []
    for index, response in enumerate(bundle.response("get_employee") or []):
        if not isinstance(response, dict):
            raise ValueError(f"responses.get_employee[{index}] must be an object")
        error_code = response.get("errorCode")
        if error_code not in (None, "0", 0):
            issues.add(IssueCode.MISSING_SECTION, Severity.WARNING,
                       f"responses.get_employee[{index}].errorCode", "response skipped",
                       raw_value=error_code, message=text(response.get("errorMessage")))
            continue
        records = response.get("employee") or []
        if not isinstance(records, list):
            raise ValueError(f"responses.get_employee[{index}].employee must be a list")
        for record in records:
            if isinstance(record, dict):
                employees.append(mapper.map(record))

    issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses",
               "company name set null",
               message="getEmployee does not return the client name; a client endpoint is a later task")
    company = Company(key=mapper.company_key,
                      source=CompanySource(provider=PROVIDER, company_id=mapper.company_id))
    return NormalizedOutput(provider=PROVIDER, company=company, employees=employees, issues=issues.issues)


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Dispatch wrapper used by the CLI. ``response`` is a parsed capture bundle for employees."""
    if entity == "employee":
        from ..bundle import parse_bundle
        return normalize_employees(response if isinstance(response, Bundle) else parse_bundle(response))
    raise NotImplementedError(f"PrismHR {entity} normalization is not implemented yet.")
