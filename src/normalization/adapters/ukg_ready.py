"""UKG Ready employee, direct deposit, deduction and payroll adapter.

Input: a capture bundle with the company employee list
(``GET /v2/companies/{cid}/employees``) and, keyed by account id as a string,
the per-employee detail, ``/demographics``, ``/pay-info`` and
``/compensation/history`` responses, plus the company lookups for employee
types, pay types and EINs. The optional ``responses.lookup_jobs``
(``GET .../lookup/jobs``) names each default job, and the optional
``responses.tax_info`` (account id -> ``.../employees/{aid}/tax-info``) carries
the 1099 flag.

Direct deposits come from ``responses.direct_deposits``, keyed by account id:
the ``{"deposits": [...]}`` body of
``GET /v2/companies/{cid}/employees/{aid}/direct-deposits``.

Deductions come from ``responses.deductions``, keyed by account id (the
``{"deductions": [...]}`` body of ``GET .../employees/{aid}/deductions``), and
``responses.deduction_detail``, keyed by deduction id (the body of
``GET .../employees/{aid}/deductions/{id}``). Only the detail carries the
amounts, frequency and limits.

Payroll comes from ``responses.payrolls`` (the ``GET .../payrolls`` list, the
pay runs), ``responses.pay_statements`` (payroll id -> the
``.../payrolls/{id}/pay-statements`` list) and
``responses.pay_statement_detail`` (statement id -> the statement detail,
which carries the lines). Pay statements have no gross or net totals, and
earnings hours arrive in milliseconds like every other UKG duration.

The company comes from ``responses.lookup_eins`` (``GET .../lookup/eins``, the
tax ids) and the optional ``responses.lookup_pay_period_profiles``
(``GET .../lookup/pay-period-profiles``, read as pay groups). UKG Ready has no
company profile endpoint, so name, address and status stay empty.

UKG's closed schema enums (gender, citizenship, amount_period, time_period)
map directly. Tenant-configured lookups (employee types, pay types) resolve to
their display name but stay canonical ``unknown``. Durations arrive in
milliseconds and are converted to hours (docs/DECISIONS.md entry on units).
"""
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from ..bundle import Bundle, parse_bundle
from ..canonical import (
    AccountType,
    Address,
    AddressKind,
    Allocation,
    AllocationMethod,
    Calculation,
    CalculationMethod,
    Citizenship,
    CodedValue,
    Company,
    CompanySource,
    Compensation,
    Contact,
    ContributionLine,
    DateRange,
    Deduction,
    DeductionFrequency,
    DeductionLine,
    DeductionSource,
    DepositSource,
    DepositStatus,
    DirectDeposit,
    EarningLine,
    Email,
    EmailKind,
    Employee,
    EmployerMatch,
    Employment,
    EmploymentStatus,
    EmploymentType,
    Gender,
    IssueCode,
    Job,
    Limits,
    Money,
    NormalizedOutput,
    Paycheck,
    PaycheckSource,
    PaycheckStatus,
    PaycheckType,
    Payee,
    PayGroup,
    PaymentLine,
    PaymentMethod,
    PayPeriod,
    PayRun,
    PayRunSource,
    PayRunStatus,
    PayRunType,
    PayType,
    Person,
    Phone,
    PhoneKind,
    Severity,
    SourceRef,
    TaxId,
    TaxLine,
)
from ._common import CodeTable, Collector, Reader, boolean, is_blank, line_readers, nonzero, text

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
DEPOSIT = f"{SCHEMAS}/137/schema/properties/deposits/items/properties"
DEPOSIT_CALC_METHOD = CodeTable(
    "deposits.calc_method.type", AllocationMethod,
    {"FLAT_AMOUNT": AllocationMethod.FIXED_AMOUNT, "GROSS_EARNING": AllocationMethod.PERCENT_OF_GROSS,
     "NET_PAY": AllocationMethod.PERCENT_OF_NET,
     "DIRECT_DEPOSIT_PER_OF_REMAINDER": AllocationMethod.PERCENT_OF_REMAINDER,
     "FULL": AllocationMethod.REMAINDER},
    f"{DEPOSIT}/calc_method/properties/type/enum",
)
DEPOSIT_ACCOUNT_TYPE = CodeTable(
    "deposits.account_type", AccountType,
    {"CHECKING": AccountType.CHECKING, "SAVINGS": AccountType.SAVINGS},
    f"{DEPOSIT}/account_type/enum",
)
PERCENT_CALC_METHODS = {AllocationMethod.PERCENT_OF_GROSS, AllocationMethod.PERCENT_OF_NET,
                        AllocationMethod.PERCENT_OF_REMAINDER}
DEDUCTION = f"{SCHEMAS}/133/schema/properties"
DEDUCTION_FREQUENCY = CodeTable(
    "deduction.ee_frequency.type", DeductionFrequency,
    {"EVERY_PAY": DeductionFrequency.EVERY_PAY, "EVERY_SCHEDULED_PAY": DeductionFrequency.EVERY_PAY,
     "EVERY_OTHER_SCHEDULED_PAY": DeductionFrequency.EVERY_OTHER_PAY, "MONTHLY": DeductionFrequency.MONTHLY,
     "QUARTERLY": DeductionFrequency.QUARTERLY, "ANNUAL": DeductionFrequency.ANNUAL,
     "MANUAL": DeductionFrequency.MANUAL, "BENEFIT_PLAN": DeductionFrequency.BENEFIT_PLAN,
     "EVERY_SCHEDULED_MONTH_ODD_PAY": DeductionFrequency.OTHER,
     "EVERY_SCHEDULED_MONTH_EVEN_PAY": DeductionFrequency.OTHER,
     "HOLIDAY_TABLE": DeductionFrequency.OTHER},
    f"{DEDUCTION}/ee_frequency/properties/type/enum",
)
# ee_calc_method.method.type is a free string in the schema; no value maps.
DEDUCTION_CALC_METHOD = CodeTable(
    "deduction.ee_calc_method.method.type", CalculationMethod, {},
    f"{DEDUCTION}/ee_calc_method/properties/method/properties/type (string, no enum)",
)
PREFERRED_PHONE = {"HOME": "home_phone", "CELL": "cell_phone", "WORK": "work_phone"}
EEO4_FIELDS = ("eeo4_classification", "eeo4_function")

PAYROLL = f"{SCHEMAS}/358/schema/properties/payrolls/items/properties"
STATEMENT = f"{SCHEMAS}/364/schema/properties"
LIVE_PAYROLL = ("live GET /v2/companies/{cid}/payrolls and .../pay-statements captures "
                "(docs/DECISIONS.md payroll entries)")
PAYROLL_STATUS = CodeTable(
    "payrolls.status", PayRunStatus,
    {"NEW": PayRunStatus.OPEN, "OPEN": PayRunStatus.OPEN, "CLOSED": PayRunStatus.SUBMITTED,
     "SUBMITTED": PayRunStatus.SUBMITTED, "FINALIZED": PayRunStatus.COMPLETED,
     "OPEN_FAILED": PayRunStatus.FAILED, "CLOSE_FAILED": PayRunStatus.FAILED,
     "ROLLBACK_FAILED": PayRunStatus.FAILED, "FINALIZE_FAILED": PayRunStatus.FAILED},
    f"{PAYROLL}/status/enum",
)
STATEMENT_STATUS = CodeTable(
    "pay_statements.status", PaycheckStatus,
    {"INVALID": PaycheckStatus.INVALID, "NEW": PaycheckStatus.OPEN, "OPEN": PaycheckStatus.OPEN,
     "CLOSED": PaycheckStatus.CLOSED, "FINALIZED": PaycheckStatus.FINALIZED},
    f"{STATEMENT}/status/enum",
)
# Payroll and statement types are tenant lookups (id and display_name).
PAYROLL_TYPE = CodeTable(
    "payrolls.type.display_name", PayRunType, {"Regular": PayRunType.REGULAR},
    f"{PAYROLL}/type (tenant lookup); labels from {LIVE_PAYROLL}",
    kind="label",
)
STATEMENT_TYPE = CodeTable(
    "pay_statements.type.display_name", PaycheckType, {"Regular": PaycheckType.REGULAR},
    f"{STATEMENT}/type (tenant lookup); labels from {LIVE_PAYROLL}",
    kind="label",
)
PAYMENT_TYPE = CodeTable(
    "payments.type_name", PaymentMethod,
    {"Check": PaymentMethod.CHECK, "Direct Deposit": PaymentMethod.DIRECT_DEPOSIT},
    f"{STATEMENT}/payments/items/properties/type_name (string, no enum); labels from {LIVE_PAYROLL}",
    kind="label",
)
LIVE_ONLY_STATEMENT_FIELDS = ("calcUpto", "emptyEarning")

PROFILE = f"{SCHEMAS}/273/schema/properties/items/items/properties"
# every_n_weeks is resolved from params.num_weeks. monthly_weekday pays once a month on a set
# weekday. quarterly has no shared value; every_n_days and user_defined name no fixed frequency.
PERIOD_TYPE = CodeTable(
    "period_type.type", PayPeriod,
    {"weekly": PayPeriod.WEEKLY, "semi_monthly": PayPeriod.SEMIMONTHLY, "monthly": PayPeriod.MONTHLY,
     "monthly_weekday": PayPeriod.MONTHLY,
     "every_n_weeks": PayPeriod.UNKNOWN, "quarterly": PayPeriod.UNKNOWN,
     "every_n_days": PayPeriod.UNKNOWN, "user_defined": PayPeriod.UNKNOWN},
    f"{PROFILE}/period_type/properties/type",
)
EVERY_N_WEEKS = {1: PayPeriod.WEEKLY, 2: PayPeriod.BIWEEKLY}


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
        for name, action, call in (("lookup_jobs", "job titles left empty", "GET .../lookup/jobs"),
                                   ("tax_info", "1099 flags left empty", "GET .../employees/{aid}/tax-info")):
            if bundle.response(name) is None:
                self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, f"responses.{name}", action,
                                message=f"{call} was not captured")
        jobs = bundle.response("lookup_jobs")
        self.job_names = _lookup_names(jobs) if jobs is not None else None

    def _section(self, name: str, aid: str, key: str, severity: Severity = Severity.WARNING) -> Any:
        data = (self.bundle.response(name) or {}).get(aid)
        if data is None:
            self.issues.add(IssueCode.MISSING_SECTION, severity, name,
                            f"fields from {name} set null", key,
                            message=f"bundle has no responses.{name}[{aid!r}] entry")
        return data

    def _job_title(self, pay_info: Reader, key: str) -> Optional[str]:
        job_id = pay_info.peek("default_job", "id")
        if is_blank(job_id) or self.job_names is None:
            return None
        name = self.job_names.get(str(job_id))
        if name is None:
            self.issues.add(IssueCode.MISSING_LOOKUP, Severity.WARNING, pay_info.path("default_job", "id"),
                            "kept the job id; title null", key, job_id,
                            f"default job id not present in the bundled jobs lookup ({SCHEMAS}/262)")
        return name or None

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
        return self.issues.code_once(table, raw_id, path, key, label=name)

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
        if self.bundle.response("tax_info") is not None:
            merged["tax_info"] = self._section("tax_info", aid, key, Severity.INFO)
        r = Reader(merged)
        demo, pay_info, dates, phones_r = r.sub("demographics"), r.sub("pay_info"), r.sub("dates"), r.sub("phones")
        tax_info = r.sub("tax_info")

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
            ssn_last4=self.issues.last4(r.get("social_security"), "social_security", key),
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
            contractor_1099=boolean(tax_info.get("employee-tax-type", "_1099")),
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
            title=self._job_title(pay_info, key),
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


class _UkgDepositMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.issues = issues
        self.company_id = bundle.request["company_id"]
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.responses = bundle.response("direct_deposits") or {}

    def map(self, aid: str) -> list[DirectDeposit]:
        employee_key = f"{self.company_key}:{aid}"
        envelope = self.responses.get(aid)
        if not isinstance(envelope, dict):
            self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "direct_deposits",
                            "no deposit lines emitted", employee_key,
                            message=f"bundle has no responses.direct_deposits[{aid!r}] entry")
            return []
        envelope_reader = Reader(envelope)
        envelope_reader.consume("deposits")
        shared = envelope_reader.unmapped()
        lines = envelope.get("deposits") or []
        if not isinstance(lines, list):
            raise ValueError(f"responses.direct_deposits[{aid!r}].deposits must be a list")
        return [self._line(Reader(line, f"deposits[{index}]"), aid, employee_key, index, shared)
                for index, line in enumerate(lines) if isinstance(line, dict)]

    def _allocation(self, r: Reader, key: str) -> Allocation:
        method = self.issues.code(DEPOSIT_CALC_METHOD, r.get("calc_method", "type"),
                                  r.path("calc_method", "type"), key,
                                  label=text(r.get("calc_method", "display_name")),
                                  issue_code=IssueCode.OUT_OF_SCHEMA_VALUE)
        member = method.value if method is not None else None
        currency = text(r.get("currency")) or "USD"
        if member is AllocationMethod.FIXED_AMOUNT:
            expected, other = "amount", "percentage"
        elif member in PERCENT_CALC_METHODS:
            expected, other = "percentage", "amount"
        else:
            expected, other = None, None
        for field in ("amount", "percentage"):
            if r.peek(field) is None:
                r.consume(field)
        if member is AllocationMethod.REMAINDER:
            extra = [field for field in ("amount", "percentage") if r.peek(field) is not None]
            if extra:
                self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path(extra[0]),
                                "kept in unmapped", key, r.peek(extra[0]),
                                "calc_method FULL takes the entire or remaining pay but an amount or "
                                f"percentage is set ({DEPOSIT}/calc_method)")
        if expected is None:
            return Allocation(method=method)
        if r.peek(other) is not None:
            self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path(other),
                            "kept in unmapped", key, r.peek(other),
                            f"calc_method {method.raw} uses '{expected}', but '{other}' is also set")
        if r.peek(expected) is None:
            self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path(expected),
                            f"{expected} set null", key,
                            message=f"calc_method {method.raw} requires '{expected}' ({DEPOSIT}/{expected})")
            return Allocation(method=method)
        if expected == "amount":
            amount = self.issues.money(r.get("amount"), r.path("amount"), key, currency)
            return Allocation(method=method, amount=amount)
        percent = self.issues.decimal(r.get("percentage"), r.path("percentage"), key)
        return Allocation(method=method, percent=percent)

    def _status(self, r: Reader, key: str) -> Optional[CodedValue]:
        active = r.get("active")
        if active is None:
            return None
        if isinstance(active, bool):
            return CodedValue(raw="true" if active else "false", label=None,
                              value=DepositStatus.ACTIVE if active else DepositStatus.INACTIVE)
        self.issues.add(IssueCode.OUT_OF_SCHEMA_VALUE, Severity.WARNING, r.path("active"),
                        "kept raw value; canonical value set to unknown", key, active,
                        f"'active' is a boolean in the schema ({DEPOSIT}/active)")
        return CodedValue(raw=text(active), label=None, value=DepositStatus.UNKNOWN)

    def _line(self, r: Reader, aid: str, employee_key: str, index: int,
              shared: Dict[str, Any]) -> DirectDeposit:
        deposit_id = text(r.get("id")) or str(index)
        key = f"{employee_key}:dd:{deposit_id}"
        start = self.issues.date(r.get("active_from"), r.path("active_from"), key)
        end = self.issues.date(r.get("active_to"), r.path("active_to"), key)
        sequence = r.get("sequence")
        return DirectDeposit(
            key=key,
            employee_key=employee_key,
            company_key=self.company_key,
            source=DepositSource(provider=PROVIDER, company_id=self.company_id, employee_id=aid,
                                 deposit_id=deposit_id),
            routing_number=text(r.get("routing_number")),
            account_number_last4=self.issues.last4(r.get("account_number"), r.path("account_number"), key),
            account_type=self.issues.code(DEPOSIT_ACCOUNT_TYPE, r.get("account_type"), r.path("account_type"),
                                          key, issue_code=IssueCode.OUT_OF_SCHEMA_VALUE),
            allocation=self._allocation(r, key),
            priority=sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else None,
            status=self._status(r, key),
            effective=DateRange(start=start, end=end) if start is not None or end is not None else None,
            unmapped={**r.unmapped(), **shared},
        )


class _UkgDeductionMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.issues = issues
        self.company_id = bundle.request["company_id"]
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.lists = bundle.response("deductions") or {}
        self.details = bundle.response("deduction_detail") or {}
        self.reported_methods: set[str] = set()

    def map(self, aid: str) -> list[Deduction]:
        employee_key = f"{self.company_key}:{aid}"
        envelope = self.lists.get(aid)
        if not isinstance(envelope, dict):
            self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "deductions",
                            "no deduction lines emitted", employee_key,
                            message=f"bundle has no responses.deductions[{aid!r}] entry")
            return []
        envelope_reader = Reader(envelope)
        envelope_reader.consume("deductions")
        shared = envelope_reader.unmapped()
        lines = envelope.get("deductions") or []
        if not isinstance(lines, list):
            raise ValueError(f"responses.deductions[{aid!r}].deductions must be a list")
        return [self._line(line, index, aid, employee_key, shared)
                for index, line in enumerate(lines) if isinstance(line, dict)]

    def _method(self, r: Reader, key: str) -> Optional[CodedValue]:
        """The method type has no enum: report each distinct value once, not on every line."""
        raw = r.get("ee_calc_method", "method", "type")
        label = text(r.get("ee_calc_method", "method", "display_name"))
        if is_blank(raw) or str(raw) not in self.reported_methods:
            self.reported_methods.add(str(raw))
            return self.issues.code(DEDUCTION_CALC_METHOD, raw, r.path("ee_calc_method", "method", "type"),
                                    key, label=label)
        return CodedValue(raw=raw if isinstance(raw, str) else str(raw), label=label,
                          value=CalculationMethod.UNKNOWN)

    def _calculation(self, r: Reader, key: str) -> Calculation:
        method = self._method(r, key)
        amount, percent = r.peek("ee_calc_method", "amount"), r.peek("ee_calc_method", "percent")
        if amount is not None and percent is not None:
            self.issues.add(IssueCode.INCONSISTENT_ALLOCATION, Severity.WARNING, r.path("ee_calc_method", "percent"),
                            "percent kept in unmapped; amount used", key, percent,
                            f"ee_calc_method sets both amount and percent; the schema allows one "
                            f"({DEDUCTION}/ee_calc_method/oneOf)")
            percent = None
        if amount is not None:
            return Calculation(method=method, amount=self.issues.money(
                r.get("ee_calc_method", "amount"), r.path("ee_calc_method", "amount"), key))
        if percent is not None:
            return Calculation(method=method, percent=self.issues.decimal(
                r.get("ee_calc_method", "percent"), r.path("ee_calc_method", "percent"), key))
        return Calculation(method=method)

    def _line(self, line: Dict[str, Any], index: int, aid: str, employee_key: str,
              shared: Dict[str, Any]) -> Deduction:
        deduction_id = text(line.get("id")) or str(index)
        key = f"{employee_key}:ded:{deduction_id}"
        detail = self.details.get(deduction_id)
        merged = dict(line)
        if isinstance(detail, dict):
            merged.update(detail)
        else:
            self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "deduction_detail",
                            "amounts, frequency and limits set null", key,
                            message=f"bundle has no responses.deduction_detail[{deduction_id!r}] entry; "
                                    "only the list fields are mapped")
        r = Reader(merged, f"deductions[{index}]")
        r.consume("id")
        start = self.issues.date(r.get("effective_from"), r.path("effective_from"), key)
        end = self.issues.date(r.get("effective_to"), r.path("effective_to"), key)
        sequence = r.get("sequence")
        er_annual_max = self.issues.money(r.get("er_annual_max_amount"), r.path("er_annual_max_amount"), key)
        vendor = r.sub("vendor")
        payee = None
        if isinstance(vendor.data, dict):
            payee = Payee(id=text(vendor.get("id")), name=text(vendor.get("name")))
        return Deduction(
            key=key,
            employee_key=employee_key,
            company_key=self.company_key,
            source=DeductionSource(provider=PROVIDER, company_id=self.company_id, employee_id=aid,
                                   deduction_id=deduction_id),
            code=Collector.raw_code(r.get("deduction", "code"), r.get("deduction", "name")),
            calculation=self._calculation(r, key),
            frequency=self.issues.code(DEDUCTION_FREQUENCY, r.get("ee_frequency", "type"),
                                       r.path("ee_frequency", "type"), key,
                                       label=text(r.get("ee_frequency", "display_name")),
                                       issue_code=IssueCode.OUT_OF_SCHEMA_VALUE),
            limits=Limits(
                per_pay=self.issues.money(r.get("ee_max_calc_method", "amount"),
                                          r.path("ee_max_calc_method", "amount"), key),
                annual=self.issues.money(r.get("annual_max_amount"), r.path("annual_max_amount"), key),
            ),
            employer_match=EmployerMatch(annual_max=er_annual_max) if er_annual_max is not None else None,
            payee=payee,
            priority=sequence if isinstance(sequence, int) and not isinstance(sequence, bool) else None,
            effective=DateRange(start=start, end=end) if start is not None or end is not None else None,
            unmapped={**r.unmapped(), **shared},
        )


class _UkgPayrollMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.issues = issues
        self.company_id = bundle.request["company_id"]
        self.company_key = f"{PROVIDER}:{self.company_id}"
        self.payrolls = bundle.response("payrolls") or {}
        self.statements = bundle.response("pay_statements") or {}
        self.details = bundle.response("pay_statement_detail") or {}
        self._reported: set = set()

    def _money(self, r: Reader, name: str, key: str):
        return self.issues.money(r.get(name), r.path(name), key)

    def _typed(self, table: CodeTable, r: Reader, key: str) -> Optional[CodedValue]:
        """A tenant type lookup: the id stays raw, the display name is matched against the allowlist."""
        type_id, name = text(r.get("type", "id")), text(r.get("type", "display_name"))
        if type_id is None and name is None:
            return None
        coded = self.issues.code_once(table, name, r.path("type", "display_name"), key)
        return CodedValue(raw=type_id, label=name, value=coded.value if coded else table.enum.UNKNOWN)

    def runs(self) -> list[PayRun]:
        items = self.payrolls.get("payrolls") or []
        if not isinstance(items, list):
            raise ValueError("responses.payrolls.payrolls must be a list")
        return [self._run(Reader(item, f"payrolls[{index}]"))
                for index, item in enumerate(items) if isinstance(item, dict)]

    def _run(self, r: Reader) -> PayRun:
        payroll_id = text(r.get("id")) or ""
        key = f"{self.company_key}:run:{payroll_id}"
        start = self.issues.date(r.get("start_date"), r.path("start_date"), key)
        end = self.issues.date(r.get("end_date"), r.path("end_date"), key)
        ein = r.sub("ein")
        return PayRun(
            key=key,
            company_key=self.company_key,
            source=PayRunSource(provider=PROVIDER, company_id=self.company_id, pay_run_id=payroll_id),
            type=self._typed(PAYROLL_TYPE, r, key),
            status=self.issues.code(PAYROLL_STATUS, r.get("status"), r.path("status"), key,
                                    issue_code=IssueCode.OUT_OF_SCHEMA_VALUE),
            pay_date=self.issues.date(r.get("pay_date"), r.path("pay_date"), key),
            period=DateRange(start=start, end=end) if start is not None or end is not None else None,
            description=text(r.get("name")),
            pay_group=Collector.raw_code(text(ein.get("id")), ein.get("ein_name")),
            unmapped=r.unmapped(),
        )

    def paychecks(self, run_keys: Dict[str, str]) -> list[Paycheck]:
        for payroll_id, run_key in run_keys.items():
            if payroll_id not in self.statements:
                self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "pay_statements",
                                "no paychecks emitted for this pay run", run_key,
                                message=f"bundle has no responses.pay_statements[{payroll_id!r}] entry")
        checks = []
        for payroll_id, envelope in self.statements.items():
            items = envelope.get("pay_statements") if isinstance(envelope, dict) else None
            if not isinstance(items, list):
                raise ValueError(f"responses.pay_statements[{payroll_id!r}].pay_statements must be a list")
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    checks.append(self._paycheck(item, index, payroll_id, run_keys.get(payroll_id)))
        return checks

    def _paycheck(self, item: Dict[str, Any], index: int, payroll_id: str, run_key: Optional[str]) -> Paycheck:
        statement_id = text(item.get("id")) or str(index)
        detail = self.details.get(statement_id)
        merged = dict(item)
        if isinstance(detail, dict):
            merged.update(detail)
        r = Reader(merged, f"pay_statements[{index}]")
        r.consume("id")
        aid = text(r.get("employee", "account_id")) or ""
        employee_key = f"{self.company_key}:{aid}"
        key = f"{employee_key}:chk:{statement_id}"
        if not isinstance(detail, dict):
            self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "pay_statement_detail",
                            "no lines emitted; list fields only", key,
                            message=f"bundle has no responses.pay_statement_detail[{statement_id!r}] entry")
        if run_key is None:
            self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, f"pay_statements[{payroll_id!r}]",
                            "pay_run_key set null", key, payroll_id, "the payroll is not in the payrolls list")
        for field_name in LIVE_ONLY_STATEMENT_FIELDS:
            if r.has(field_name) and field_name not in self._reported:
                self._reported.add(field_name)
                self.issues.add(IssueCode.SPEC_LIVE_MISMATCH, Severity.INFO, r.path(field_name),
                                "kept in unmapped",
                                message=f"live pay-statements returns '{field_name}', which the schema does not "
                                        f"list ({SCHEMAS}/362)")
        start = self.issues.date(r.get("pay_period_start"), r.path("pay_period_start"), key)
        end = self.issues.date(r.get("pay_period_end"), r.path("pay_period_end"), key)
        deductions, contributions = self._deductions(r, key)
        return Paycheck(
            key=key,
            employee_key=employee_key,
            company_key=self.company_key,
            source=PaycheckSource(provider=PROVIDER, company_id=self.company_id, employee_id=aid,
                                  paycheck_id=statement_id, pay_run_id=payroll_id),
            pay_run_key=run_key,
            type=self._typed(STATEMENT_TYPE, r, key),
            status=self.issues.code(STATEMENT_STATUS, r.get("status"), r.path("status"), key,
                                    issue_code=IssueCode.OUT_OF_SCHEMA_VALUE),
            pay_date=self.issues.date(r.get("pay_date"), r.path("pay_date"), key),
            period=DateRange(start=start, end=end) if start is not None or end is not None else None,
            earnings=self._earnings(r, key),
            taxes=[TaxLine(code=Collector.raw_code(t.get("company_tax", "code"), t.get("company_tax", "name")),
                           employee_amount=self._money(t, "ee_amount", key),
                           employer_amount=self._money(t, "er_amount", key),
                           employee_taxable_wages=self._money(t, "ee_subject_wage", key),
                           employer_taxable_wages=self._money(t, "er_subject_wage", key),
                           unmapped=t.unmapped())
                   for t in line_readers(r, "taxes")],
            deductions=deductions,
            employer_contributions=contributions,
            payments=[PaymentLine(method=self.issues.code_once(PAYMENT_TYPE, p.get("type_name"),
                                                               p.path("type_name"), key),
                                  amount=self._money(p, "ee_amount", key), unmapped=p.unmapped())
                      for p in line_readers(r, "payments")],
            unmapped=r.unmapped(),
        )

    def _earnings(self, r: Reader, key: str) -> list[EarningLine]:
        lines = []
        for line in line_readers(r, "earnings"):
            raw_hours = line.get("hours")
            hours = _ms_to_hours(raw_hours)
            if raw_hours is not None and hours is None:
                self.issues.add(IssueCode.INVALID_NUMBER, Severity.ERROR, line.path("hours"), "set null", key,
                                raw_hours, "hours must be a number of milliseconds")
            lines.append(EarningLine(
                code=Collector.raw_code(line.get("earning", "code"), line.get("earning", "name")),
                hours=hours,
                rate=self._money(line, "base_rate", key),
                amount=self._money(line, "ee_amount", key),
                unmapped=line.unmapped(),
            ))
        return lines

    def _deductions(self, r: Reader, key: str) -> tuple[list[DeductionLine], list[ContributionLine]]:
        """Split each line into the employee's deduction and the employer's contribution, when nonzero."""
        deductions, contributions = [], []
        for line in line_readers(r, "deductions"):
            code = Collector.raw_code(line.get("deduction", "code"), line.get("deduction", "name"))
            employee = self._money(line, "ee_amount", key) if nonzero(line.peek("ee_amount")) else None
            employer = self._money(line, "er_amount", key) if nonzero(line.peek("er_amount")) else None
            unmapped = line.unmapped()
            if employee is not None or employer is None:
                deductions.append(DeductionLine(code=code, amount=employee, unmapped=unmapped))
            if employer is not None:
                contributions.append(ContributionLine(code=code, amount=employer, unmapped=unmapped))
        return deductions, contributions


def _listed_employees(bundle: Bundle) -> list[Dict[str, Any]]:
    listed = bundle.response("employees").get("employees")
    if not isinstance(listed, list):
        raise ValueError("responses.employees.employees must be a list")
    return [record for record in listed if isinstance(record, dict)]


class _UkgCompanyMapper:
    def __init__(self, bundle: Bundle, issues: Collector):
        self.bundle = bundle
        self.issues = issues
        self.company_id = bundle.request["company_id"]
        self.key = f"{PROVIDER}:{self.company_id}"

    def company(self) -> Company:
        self.issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses",
                        "name, legal name, status and address set null", self.key,
                        message="UKG Ready has no company profile endpoint; GET /v2/companies/{cid} answers 404")
        self.issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "responses", "work locations left empty",
                        self.key, message="UKG Ready has no work location records; cost centres are "
                                          "tenant-defined trees")
        tax_ids = self._tax_ids()
        ein = None
        if len(tax_ids) == 1:
            ein = tax_ids[0].tax_id
        elif len(tax_ids) > 1:
            self.issues.add(IssueCode.MISSING_LOOKUP, Severity.WARNING, "lookup_eins.items", "company ein set null",
                            self.key, len(tax_ids), "several EINs; each one is listed under tax_ids")
        return Company(
            key=self.key,
            source=CompanySource(provider=PROVIDER, company_id=self.company_id),
            ein=ein,
            tax_ids=tax_ids,
            pay_groups=self._pay_groups(),
        )

    def _tax_ids(self) -> list[TaxId]:
        tax_ids = []
        for r in line_readers(Reader(self.bundle.response("lookup_eins"), "lookup_eins"), "items"):
            source_id = text(r.get("id"))
            tax_ids.append(TaxId(
                key=f"{self.key}:ein:{source_id}",
                source_id=source_id,
                tax_id=text(r.get("ein_tax_id")),
                name=text(r.get("ein_name")),
                country=text(r.get("ein_country_id")),
                unmapped=r.unmapped(),
            ))
        return tax_ids

    def _pay_groups(self) -> list[PayGroup]:
        response = self.bundle.response("lookup_pay_period_profiles")
        if response is None:
            return []
        groups = []
        for r in line_readers(Reader(response, "lookup_pay_period_profiles"), "items"):
            source_id = text(r.get("id")) or ""
            key = f"{self.key}:pg:{source_id}"
            start = self.issues.date(r.get("effective_from"), r.path("effective_from"), key)
            end = self.issues.date(r.get("effective_to"), r.path("effective_to"), key)
            groups.append(PayGroup(
                key=key,
                source_id=source_id,
                code=Collector.raw_code(source_id, text(r.get("name"))),
                frequency=self._frequency(r, key),
                active=boolean(r.get("active")),
                effective=DateRange(start=start, end=end) if start or end else None,
                unmapped=r.unmapped(),
            ))
        return groups

    def _frequency(self, r: Reader, key: str) -> Optional[CodedValue]:
        period = r.sub("period_type")
        raw = period.get("type")
        coded = self.issues.code_once(PERIOD_TYPE, raw, period.path("type"), key, label=text(raw),
                                      issue_code=IssueCode.OUT_OF_SCHEMA_VALUE)
        if raw == "every_n_weeks":
            weeks = period.get("params", "num_weeks")
            coded = CodedValue(raw=raw, label=coded.label, value=EVERY_N_WEEKS.get(weeks, PayPeriod.UNKNOWN))
        return coded


def _company(company_id: str, bundle: Bundle, issues: Collector) -> Company:
    issues.add(IssueCode.MISSING_SECTION, Severity.WARNING, "responses", "company name set null",
               message="UKG Ready has no company profile endpoint; GET /v2/companies/{cid} answers 404")
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
                   message="several EINs; --entity company lists each one under tax_ids")
    return Company(
        key=f"{PROVIDER}:{company_id}",
        source=CompanySource(provider=PROVIDER, company_id=company_id, secondary_ids=secondary),
        ein=ein,
    )


def _check_provider(bundle: Bundle) -> None:
    if bundle.provider != PROVIDER:
        raise ValueError(f"bundle provider is {bundle.provider!r}, expected {PROVIDER!r}")


def normalize_employees(bundle: Bundle) -> NormalizedOutput:
    _check_provider(bundle)
    issues = Collector()
    mapper = _UkgEmployeeMapper(bundle, issues)
    employees = [mapper.map(record) for record in _listed_employees(bundle)]
    company = _company(mapper.company_id, bundle, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, employees=employees, issues=issues.issues)


def normalize_direct_deposits(bundle: Bundle) -> NormalizedOutput:
    """One record per deposit line, for every listed employee and then any other captured account id."""
    _check_provider(bundle)
    issues = Collector()
    mapper = _UkgDepositMapper(bundle, issues)
    aids = [text(record.get("id")) or "" for record in _listed_employees(bundle)]
    listed = set(aids)
    aids += [aid for aid in mapper.responses if aid not in listed]
    deposits = [deposit for aid in aids for deposit in mapper.map(aid)]
    company = _company(mapper.company_id, bundle, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, direct_deposits=deposits, issues=issues.issues)


def normalize_deductions(bundle: Bundle) -> NormalizedOutput:
    """One record per deduction line, for every listed employee and then any other captured account id."""
    _check_provider(bundle)
    issues = Collector()
    mapper = _UkgDeductionMapper(bundle, issues)
    aids = [text(record.get("id")) or "" for record in _listed_employees(bundle)]
    listed = set(aids)
    aids += [aid for aid in mapper.lists if aid not in listed]
    deductions = [record for aid in aids for record in mapper.map(aid)]
    company = _company(mapper.company_id, bundle, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, deductions=deductions, issues=issues.issues)


def normalize_payroll(bundle: Bundle) -> NormalizedOutput:
    """Pay runs in list order, then every captured statement in capture order."""
    _check_provider(bundle)
    issues = Collector()
    mapper = _UkgPayrollMapper(bundle, issues)
    pay_runs = mapper.runs()
    paychecks = mapper.paychecks({run.source.pay_run_id: run.key for run in pay_runs})
    if paychecks:
        issues.add(IssueCode.MISSING_SECTION, Severity.INFO, "pay_statement_detail", "gross_pay and net_pay set null",
                   message=f"pay statements carry no gross or net totals ({STATEMENT}); "
                           "they are never summed from the lines")
    company = _company(mapper.company_id, bundle, issues)
    return NormalizedOutput(provider=PROVIDER, company=company, pay_runs=pay_runs, paychecks=paychecks,
                            issues=issues.issues)


def normalize_company(bundle: Bundle) -> NormalizedOutput:
    """The company's EINs and pay-period profiles; UKG Ready has no company profile."""
    _check_provider(bundle)
    issues = Collector()
    company = _UkgCompanyMapper(bundle, issues).company()
    return NormalizedOutput(provider=PROVIDER, company=company, issues=issues.issues)


NORMALIZERS = {"company": normalize_company, "employee": normalize_employees,
               "direct-deposit": normalize_direct_deposits, "deduction": normalize_deductions,
               "payroll": normalize_payroll}


def normalize(entity: str, response: Any, reference: Dict[str, Any]) -> Any:
    """Dispatch wrapper used by the CLI. ``response`` is a parsed capture bundle."""
    if entity in NORMALIZERS:
        bundle = response if isinstance(response, Bundle) else parse_bundle(response, entity=entity)
        return NORMALIZERS[entity](bundle)
    raise NotImplementedError(f"UKG Ready {entity} normalization is not implemented yet.")
