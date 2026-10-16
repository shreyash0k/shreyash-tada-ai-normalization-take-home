"""UKG Ready employee adapter.

Input: a capture bundle with the company employee list
(``GET /v2/companies/{cid}/employees``) and, keyed by account id as a string,
the per-employee detail, ``/demographics``, ``/pay-info`` and
``/compensation/history`` responses, plus the company lookups for employee
types, pay types and EINs.

UKG's closed schema enums (gender, citizenship, amount_period, time_period)
map directly. Tenant-configured lookups (employee types, pay types) resolve to
their display name but stay canonical ``unknown``. Durations arrive in
milliseconds and are converted to hours (docs/DECISIONS.md entry on units).
"""
from datetime import date
from decimal import Decimal
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
    Money,
    NormalizedOutput,
    PayPeriod,
    PayType,
    Person,
    Phone,
    PhoneKind,
    Severity,
    SourceRef,
)
from ._common import CodeTable, Collector, Reader, boolean, is_blank, text

PROVIDER = "ukg-ready"
SCHEMAS = "contracts/ukg-ready/reference-schemas.json#/schemas"
MS_PER_HOUR = Decimal(3_600_000)

STATUS = CodeTable(
    "status", EmploymentStatus,
    {"Active": EmploymentStatus.ACTIVE, "Terminated": EmploymentStatus.TERMINATED},
    f"{SCHEMAS}/106/schema/properties/status (string, no enum); labels from live "
    "GET /v2/companies/{cid}/employees capture (docs/DECISIONS.md allowlist entries)",
    kind="label",
)
GENDER = CodeTable(
    "demographics.gender", Gender,
    {"MALE": Gender.MALE, "FEMALE": Gender.FEMALE, "UNDEFINED": Gender.UNKNOWN},
    f"{SCHEMAS}/134/schema/properties/gender/enum",
)
CITIZENSHIP = CodeTable(
    "demographics.citizenship", Citizenship,
    {"US_CITIZEN": Citizenship.CITIZEN, "PERMANENT_RESIDENT": Citizenship.PERMANENT_RESIDENT,
     "ALIEN_WITH_WORK_PERMIT": Citizenship.WORK_PERMIT,
     "NONCITIZEN_NATIONAL_OF_US": Citizenship.NONCITIZEN_NATIONAL},
    f"{SCHEMAS}/134/schema/properties/citizenship/enum",
)
AMOUNT_PERIOD = CodeTable(
    "compensation.amount_period", PayPeriod,
    {"YEAR": PayPeriod.ANNUAL, "MONTH": PayPeriod.MONTHLY, "WEEK": PayPeriod.WEEKLY,
     "HOUR": PayPeriod.HOURLY, "PAY_PERIOD": PayPeriod.PAY_PERIOD},
    f"{SCHEMAS}/122/schema/properties/compensations/items/properties/amount_period/enum",
)
TIME_PERIOD = CodeTable(
    "compensation.time_period", PayPeriod,
    {"YEAR": PayPeriod.ANNUAL, "MONTH": PayPeriod.MONTHLY, "WEEK": PayPeriod.WEEKLY,
     "PAY_PERIOD": PayPeriod.PAY_PERIOD},
    f"{SCHEMAS}/122/schema/properties/compensations/items/properties/time_period/enum",
)
# Tenant-configured lookups: the id resolves to a display name, never to a canonical value.
EMPLOYEE_TYPE = CodeTable(
    "pay_info.employee_type.id", EmploymentType, {},
    f"{SCHEMAS}/159/schema/properties/employee_type (id only; names come from "
    "GET /v2/companies/{cid}/lookup/employee-types and are tenant-defined)",
    kind="label",
)
PAY_TYPE = CodeTable(
    "pay_info.pay_type.id", PayType, {},
    f"{SCHEMAS}/159/schema/properties/pay_type (id only; names come from "
    "GET /v2/companies/{cid}/lookup/pay-types and are tenant-defined)",
    kind="label",
)
PREFERRED_PHONE = {"HOME": "home_phone", "CELL": "cell_phone", "WORK": "work_phone"}
EEO4_FIELDS = ("eeo4_classification", "eeo4_function")


def _ms_to_hours(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return (Decimal(str(value)) / MS_PER_HOUR).quantize(Decimal("0.01"))


def _lookup_names(response: Any) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for item in (response or {}).get("items") or []:
        if isinstance(item, dict) and "id" in item:
            names[str(item["id"])] = text(item.get("name")) or ""
    return names


class _UkgEmployeeMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.bundle = bundle
        self.issues = issues
        self.company_id = bundle.request["company_id"]
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.employee_types = _lookup_names(bundle.response("lookup_employee_types"))
        self.pay_types = _lookup_names(bundle.response("lookup_pay_types"))
        self.reported_mismatch: set[str] = set()

    def _section(self, name: str, aid: str, key: str) -> Any:
        data = (self.bundle.response(name) or {}).get(aid)
        if data is None:
            self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, name,
                            f"fields from {name} set null", key,
                            message=f"bundle has no responses.{name}[{aid!r}] entry")
        return data

    def _lookup(self, table: CodeTable, names: Dict[str, str], raw_id: Any, path: str,
                key: str) -> Optional[CodedValue]:
        if is_blank(raw_id):
            return None
        name = names.get(str(raw_id))
        if name is None:
            self.issues.add(IssueCode.MISSING_LOOKUP, Severity.WARNING, path,
                            "kept raw id; label null; canonical value set to unknown", key, raw_id,
                            f"{table.name}: id not present in the bundled lookup ({table.evidence})")
            return CodedValue(raw=raw_id, label=None, value=table.enum.UNKNOWN)
        return self.issues.code(table, raw_id, path, key, label=name)

    def _report_once(self, path: str, message: str) -> None:
        if path in self.reported_mismatch:
            return
        self.reported_mismatch.add(path)
        self.issues.add(IssueCode.SPEC_LIVE_MISMATCH, Severity.INFO, path, "kept in unmapped",
                        message=message)

    def _current_compensation(self, rows: Any, key: str) -> tuple[Optional[int], Optional[date]]:
        """Index of the row with the latest effective_from on or before captured_at."""
        if not isinstance(rows, list):
            return None, None
        best_index, best_date, ties = None, None, 0
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if row.get("num_pp_in_year") == 0:
                # A count, not a frequency code; it stays in unmapped. The schema minimum is 1.
                self.issues.add(IssueCode.OUT_OF_SCHEMA_VALUE, Severity.WARNING,
                                f"compensation_history.compensations[{index}].num_pp_in_year",
                                "kept in unmapped", key, 0,
                                f"schema minimum is 1 ({SCHEMAS}/122/schema/properties/compensations/items/"
                                "properties/num_pp_in_year)")
            effective = self.issues.date(row.get("effective_from"),
                                         f"compensation_history.compensations[{index}].effective_from", key)
            if effective is None or effective > self.bundle.captured_at:
                continue
            if best_date is None or effective > best_date:
                best_index, best_date, ties = index, effective, 0
            elif effective == best_date:
                ties += 1
        if ties:
            self.issues.add(IssueCode.MULTIPLE_CURRENT_RATES, Severity.WARNING,
                            "compensation_history.compensations", "used the first row in response order",
                            key, best_date.isoformat() if best_date else None,
                            f"{ties + 1} compensation rows share effective_from {best_date}")
        return best_index, best_date

    def map(self, listed: Dict[str, Any]) -> Employee:
        aid = text(listed.get("id")) or ""
        key = f"{self.company_key}:{aid}"
        detail = self._section("employee", aid, key)
        merged = dict(listed)
        if isinstance(detail, dict):
            merged.update(detail)
            if "ein_name" in detail:
                self._report_once("ein_name", "live detail response carries 'ein_name', which the "
                                  f"schema lists only on the employee list ({SCHEMAS}/104)")
            if isinstance(detail.get("_links"), dict) and "country-fields" in detail["_links"]:
                self._report_once("_links.country-fields", "live detail response links 'country-fields', "
                                  f"which the schema does not list ({SCHEMAS}/106/schema/properties/_links)")
        merged["demographics"] = self._section("demographics", aid, key)
        merged["pay_info"] = self._section("pay_info", aid, key)
        merged["compensation_history"] = self._section("compensation_history", aid, key)
        r = Reader(merged)
        demo, pay_info, dates, phones_r = r.sub("demographics"), r.sub("pay_info"), r.sub("dates"), r.sub("phones")

        secondary = {}
        for field in ("employee_id", "username", "external_id"):
            value = text(r.get(field))
            if value is not None:
                secondary[field] = value

        person = Person(
            first_name=text(r.get("first_name")),
            middle_name=text(r.get("middle_name")),
            last_name=text(r.get("last_name")),
            preferred_name=text(r.get("nickname")),
            birth_date=self.issues.date(dates.get("birthday"), dates.path("birthday"), key),
            gender=self.issues.code(GENDER, demo.get("gender"), demo.path("gender"), key),
            citizenship=self.issues.code(CITIZENSHIP, demo.get("citizenship"), demo.path("citizenship"), key),
            ethnicity=Collector.raw_code(demo.get("ethnicity")),
            ssn_last4=self.issues.ssn_last4(r.get("social_security"), "social_security", key),
        )

        addresses = []
        for section, kind in (("address", AddressKind.HOME), ("mailing_address", AddressKind.MAILING)):
            addr = r.sub(section)
            if not isinstance(addr.data, dict):
                continue
            if section == "mailing_address" and boolean(r.peek("use_separate_mailing_address")) is False:
                continue
            values = {
                "line1": text(addr.get("address_line_1")), "line2": text(addr.get("address_line_2")),
                "city": text(addr.get("city")), "region": text(addr.get("state")),
                "postal_code": text(addr.get("zip")), "country": text(addr.get("country")),
            }
            if any(v is not None for v in values.values()):
                addresses.append(Address(kind=kind, **values))
        phones = []
        preferred = text(phones_r.get("preferred_phone"))
        for field, kind in (("home_phone", PhoneKind.HOME), ("cell_phone", PhoneKind.MOBILE),
                            ("work_phone", PhoneKind.WORK)):
            number = text(phones_r.get(field))
            if number is not None:
                phones.append(Phone(kind=kind, number=number,
                                    preferred=(PREFERRED_PHONE.get(preferred) == field) if preferred else None))
        emails = []
        for field, kind in (("primary_email", EmailKind.UNKNOWN), ("secondary_email", EmailKind.OTHER)):
            address = text(r.get(field))
            if address is not None:
                emails.append(Email(kind=kind, address=address))

        employee_type = self._lookup(EMPLOYEE_TYPE, self.employee_types, pay_info.get("employee_type", "id"),
                                     pay_info.path("employee_type", "id"), key)
        employment = Employment(
            status=self.issues.code(STATUS, r.get("status"), "status", key),
            employment_type=employee_type,
            hire_date=self.issues.date(dates.get("hired"), dates.path("hired"), key),
            rehire_date=self.issues.date(dates.get("re_hired"), dates.path("re_hired"), key),
            termination_date=self.issues.date(dates.get("terminated"), dates.path("terminated"), key),
            seniority_date=self.issues.date(dates.get("seniority"), dates.path("seniority"), key),
        )

        manager_id = None
        managers = r.peek("managers")
        if isinstance(managers, list) and managers:
            ordered = sorted((m for m in managers if isinstance(m, dict)),
                             key=lambda m: m.get("index", 0) if isinstance(m.get("index"), int) else 0)
            if ordered:
                first = ordered[0]
                position = managers.index(first)
                manager_id = text(r.get("managers", position, "empl_ref", "account_id"))
                r.consume("managers", position, "index")
        job = Job(
            job_code=Collector.raw_code(pay_info.get("default_job", "id")),
            manager_employee_id=manager_id,
        )

        for field in EEO4_FIELDS:
            value = pay_info.peek(field)
            if value == "UNKNOWN":
                self.issues.add(IssueCode.OUT_OF_SCHEMA_VALUE, Severity.WARNING, pay_info.path(field),
                                "kept in unmapped", key, value,
                                f"'UNKNOWN' is not in the schema enum ({SCHEMAS}/159/schema/properties/{field}/enum)")

        rows = (merged.get("compensation_history") or {}).get("compensations") if merged.get("compensation_history") else None
        index, effective = self._current_compensation(rows, key)
        pay_type = self._lookup(PAY_TYPE, self.pay_types, pay_info.get("pay_type", "id"),
                                pay_info.path("pay_type", "id"), key)
        compensation = Compensation(
            pay_type=pay_type,
            standard_work_day_hours=_ms_to_hours(pay_info.get("standard_work_day")),
        )
        if index is not None:
            row = r.sub("compensation_history", "compensations", index)
            row.consume("effective_from")
            currency = text(row.get("currency")) or "USD"
            amount = self.issues.decimal(row.get("amount"), row.path("amount"), key)
            period = self.issues.code(AMOUNT_PERIOD, row.get("amount_period"), row.path("amount_period"), key)
            hours = _ms_to_hours(row.get("time"))
            if row.peek("time") is not None and hours is None:
                self.issues.add(IssueCode.INVALID_NUMBER, Severity.ERROR, row.path("time"), "set null", key,
                                row.peek("time"), "time must be an integer number of milliseconds")
            money = Money(amount=amount, currency=currency) if amount is not None else None
            compensation = Compensation(
                pay_type=pay_type,
                rate=money,
                rate_period=period,
                hourly_rate=self.issues.money(row.get("hourly_pay"), row.path("hourly_pay"), key, currency),
                annual_amount=money if period is not None and period.value is PayPeriod.ANNUAL else None,
                per_period_amount=money if period is not None and period.value is PayPeriod.PAY_PERIOD else None,
                standard_hours=hours,
                standard_hours_period=self.issues.code(TIME_PERIOD, row.get("time_period"),
                                                       row.path("time_period"), key) if hours is not None else None,
                standard_work_day_hours=compensation.standard_work_day_hours,
                effective_date=effective,
            )

        return Employee(
            key=key,
            company_key=self.company_key,
            source=SourceRef(provider=PROVIDER, company_id=self.company_id, employee_id=aid,
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
    mapper = _UkgEmployeeMapper(bundle, issues)
    listed = bundle.response("employees").get("employees")
    if not isinstance(listed, list):
        raise ValueError("responses.employees.employees must be a list")
    employees = [mapper.map(record) for record in listed if isinstance(record, dict)]

    issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses", "company name set null",
               message="the employee endpoints do not return the company name; "
                       "a company endpoint is a later task")
    eins = [item for item in (bundle.response("lookup_eins") or {}).get("items") or [] if isinstance(item, dict)]
    ein, secondary = None, {}
    if len(eins) == 1:
        ein = text(eins[0].get("ein_tax_id"))
        ein_name = text(eins[0].get("ein_name"))
        if ein_name:
            secondary["ein_name"] = ein_name
    elif len(eins) > 1:
        issues.add(IssueCode.MISSING_LOOKUP, Severity.WARNING, "responses.lookup_eins.items",
                   "company ein set null", raw_value=len(eins),
                   message="multi-EIN company; employee-to-EIN assignment is a later task")
    company = Company(
        key=mapper.company_key,
        source=CompanySource(provider=PROVIDER, company_id=mapper.company_id, secondary_ids=secondary),
        ein=ein,
    )
    return NormalizedOutput(provider=PROVIDER, company=company, employees=employees, issues=issues.issues)


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Dispatch wrapper used by the CLI. ``response`` is a parsed capture bundle for employees."""
    if entity == "employee":
        from ..bundle import parse_bundle
        return normalize_employees(response if isinstance(response, Bundle) else parse_bundle(response))
    raise NotImplementedError(f"UKG Ready {entity} normalization is not implemented yet.")
