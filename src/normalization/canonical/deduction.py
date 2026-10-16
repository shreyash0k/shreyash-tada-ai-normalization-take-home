"""Canonical deduction record: the setup of one recurring employee deduction."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from .common import CanonicalEnum, CodedValue, DateRange, Model, Money


class DeductionCategory(CanonicalEnum):
    VOLUNTARY = "voluntary"
    SECTION_125 = "section_125"
    POST_TAX_BENEFIT = "post_tax_benefit"
    FSA = "fsa"
    GARNISHMENT = "garnishment"
    LOAN = "loan"
    RETIREMENT_PRE_TAX = "retirement_pre_tax"
    RETIREMENT_CATCH_UP = "retirement_catch_up"
    RETIREMENT_POST_TAX = "retirement_post_tax"
    RETIREMENT_LOAN = "retirement_loan"
    RETIREMENT_ROTH = "retirement_roth"
    RETIREMENT_ROTH_CATCH_UP = "retirement_roth_catch_up"
    UNKNOWN = "unknown"


class CalculationMethod(CanonicalEnum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENT_OF_GROSS = "percent_of_gross"
    PERCENT_OF_EARNINGS = "percent_of_earnings"
    RATE_PER_HOUR = "rate_per_hour"
    GARNISHMENT_RULE = "garnishment_rule"
    RETIREMENT_PLAN_RULE = "retirement_plan_rule"
    TABLE_LOOKUP = "table_lookup"
    OTHER = "other"  # documented by the provider, but none of the methods above
    UNKNOWN = "unknown"


class DeductionFrequency(CanonicalEnum):
    EVERY_PAY = "every_pay"
    EVERY_OTHER_PAY = "every_other_pay"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    MANUAL = "manual"
    BENEFIT_PLAN = "benefit_plan"
    OTHER = "other"  # documented by the provider, but none of the frequencies above
    UNKNOWN = "unknown"


class MatchMethod(CanonicalEnum):
    FLAT = "flat"
    PERCENT = "percent"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DeductionSource(Model):
    """Provider, company and employee IDs, plus the provider's ID for the line when it has one."""

    provider: str
    company_id: str
    employee_id: str
    deduction_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Calculation(Model):
    """How the employee amount is worked out. Amount and percent are copied, never derived."""

    method: Optional[CodedValue] = None
    amount: Optional[Money] = None
    percent: Optional[Decimal] = None


@dataclass(frozen=True, slots=True)
class Limits(Model):
    """Caps on the employee amount, one slot per period the provider names."""

    per_pay: Optional[Money] = None
    monthly: Optional[Money] = None
    quarterly: Optional[Money] = None
    annual: Optional[Money] = None
    lifetime: Optional[Money] = None


@dataclass(frozen=True, slots=True)
class EmployerMatch(Model):
    method: Optional[CodedValue] = None
    amount: Optional[Money] = None
    percent: Optional[Decimal] = None
    annual_max: Optional[Money] = None


@dataclass(frozen=True, slots=True)
class Payee(Model):
    """The third party the deducted money is paid to."""

    id: Optional[str] = None
    name: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Deduction(Model):
    key: str
    employee_key: str
    company_key: str
    source: DeductionSource
    code: Optional[CodedValue] = None
    category: Optional[CodedValue] = None
    calculation: Calculation = field(default_factory=Calculation)
    frequency: Optional[CodedValue] = None
    limits: Limits = field(default_factory=Limits)
    employer_match: Optional[EmployerMatch] = None
    payee: Optional[Payee] = None
    priority: Optional[int] = None
    effective: Optional[DateRange] = None
    unmapped: dict[str, Any] = field(default_factory=dict)
