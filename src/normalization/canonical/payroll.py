"""Canonical payroll records: pay runs, and employee paychecks with their lines."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from .common import CanonicalEnum, CodedValue, DateRange, Model, Money


class PayRunType(CanonicalEnum):
    REGULAR = "regular"
    MANUAL = "manual"
    SPECIAL = "special"
    VOID = "void"
    ADJUSTMENT = "adjustment"
    OTHER = "other"
    UNKNOWN = "unknown"


class PayRunStatus(CanonicalEnum):
    OPEN = "open"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PaycheckType(CanonicalEnum):
    REGULAR = "regular"
    SUPPLEMENTAL = "supplemental"
    VACATION = "vacation"
    ARREARS = "arrears"
    ADJUSTMENT = "adjustment"
    OTHER = "other"
    UNKNOWN = "unknown"


class PaycheckStatus(CanonicalEnum):
    OPEN = "open"
    CLOSED = "closed"
    FINALIZED = "finalized"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class EarningCategory(CanonicalEnum):
    EARNINGS = "earnings"
    REIMBURSEMENT = "reimbursement"
    FRINGE = "fringe"
    TIPS = "tips"
    MEMO = "memo"
    UNKNOWN = "unknown"


class PaymentMethod(CanonicalEnum):
    CHECK = "check"
    DIRECT_DEPOSIT = "direct_deposit"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PayRunSource(Model):
    provider: str
    company_id: str
    pay_run_id: str


@dataclass(frozen=True, slots=True)
class PayRun(Model):
    key: str
    company_key: str
    source: PayRunSource
    type: Optional[CodedValue] = None
    status: Optional[CodedValue] = None
    pay_date: Optional[date] = None
    period: Optional[DateRange] = None
    description: Optional[str] = None
    pay_group: Optional[CodedValue] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaycheckSource(Model):
    """Provider, company and employee IDs, the paycheck's ID, and its run's ID when known."""

    provider: str
    company_id: str
    employee_id: str
    paycheck_id: str
    pay_run_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class EarningLine(Model):
    code: Optional[CodedValue] = None
    category: Optional[CodedValue] = None
    hours: Optional[Decimal] = None
    rate: Optional[Money] = None
    amount: Optional[Money] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaxLine(Model):
    """One tax; UKG Ready sends both sides on one line, the others fill one side."""

    code: Optional[CodedValue] = None
    employee_amount: Optional[Money] = None
    employer_amount: Optional[Money] = None
    employee_taxable_wages: Optional[Money] = None
    employer_taxable_wages: Optional[Money] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeductionLine(Model):
    """An amount taken from the employee's pay in this paycheck."""

    code: Optional[CodedValue] = None
    category: Optional[CodedValue] = None
    amount: Optional[Money] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContributionLine(Model):
    """An amount the employer paid on top of the employee's pay."""

    code: Optional[CodedValue] = None
    amount: Optional[Money] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentLine(Model):
    method: Optional[CodedValue] = None
    amount: Optional[Money] = None
    account_last4: Optional[str] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Paycheck(Model):
    """One employee's paycheck. Gross and net pay are copied, never summed from the lines."""

    key: str
    employee_key: str
    company_key: str
    source: PaycheckSource
    pay_run_key: Optional[str] = None
    type: Optional[CodedValue] = None
    status: Optional[CodedValue] = None
    pay_date: Optional[date] = None
    period: Optional[DateRange] = None
    check_number: Optional[str] = None
    gross_pay: Optional[Money] = None
    net_pay: Optional[Money] = None
    void_date: Optional[date] = None
    earnings: list[EarningLine] = field(default_factory=list)
    taxes: list[TaxLine] = field(default_factory=list)
    deductions: list[DeductionLine] = field(default_factory=list)
    employer_contributions: list[ContributionLine] = field(default_factory=list)
    payments: list[PaymentLine] = field(default_factory=list)
    unmapped: dict[str, Any] = field(default_factory=dict)
