"""isolved employee adapter.

Input: a capture bundle whose ``responses.employees`` is a list of paged
``GET /api/clients/{clientId}/legals/{legalId}/employees`` responses
(``PagedModelItemListOfEmployeeModel``: ``results[]``). Optional maps keyed
by the employee ``id`` (as a string) carry the single-employee detail,
``/personal`` and ``/nameAddress`` responses; when present they override the
list record field by field.

isolved returns English descriptions rather than codes for most coded fields
("Active", "Male", "Salary"). Only the short allowlists below map to canonical
values; everything else stays raw with an issue.
"""
from typing import Any, Dict

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
            ssn_last4=self.issues.ssn_last4(r.get("ssn"), "ssn", key),
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


def normalize_employees(bundle: Bundle) -> NormalizedOutput:
    if bundle.provider != PROVIDER:
        raise ValueError(f"bundle provider is {bundle.provider!r}, expected {PROVIDER!r}")
    issues = Collector()
    mapper = _IsolvedEmployeeMapper(bundle, issues)
    employees = []
    for index, page in enumerate(bundle.response("employees") or []):
        if not isinstance(page, dict):
            raise ValueError(f"responses.employees[{index}] must be an object")
        results = page.get("results")
        if not isinstance(results, list):
            raise ValueError(f"responses.employees[{index}].results must be a list")
        for record in results:
            if isinstance(record, dict):
                employees.append(mapper.map(record))

    issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses",
               "company name set null",
               message="the employees endpoint does not return the legal company name; "
                       "a legal endpoint is a later task")
    secondary = {}
    if len(mapper.legal_codes) == 1:
        secondary["legalCode"] = next(iter(mapper.legal_codes))
    company = Company(
        key=mapper.company_key,
        source=CompanySource(provider=PROVIDER, company_id=mapper.company_id, secondary_ids=secondary),
    )
    return NormalizedOutput(provider=PROVIDER, company=company, employees=employees, issues=issues.issues)


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Dispatch wrapper used by the CLI. ``response`` is a parsed capture bundle for employees."""
    if entity == "employee":
        from ..bundle import parse_bundle
        return normalize_employees(response if isinstance(response, Bundle) else parse_bundle(response))
    raise NotImplementedError(f"isolved {entity} normalization is not implemented yet.")
