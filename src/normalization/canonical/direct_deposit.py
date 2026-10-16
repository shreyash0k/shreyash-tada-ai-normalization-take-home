"""Canonical direct deposit record: one bank line of an employee's deposit setup."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from .common import CanonicalEnum, CodedValue, DateRange, Model, Money


class AccountType(CanonicalEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INSTANT_PAY = "instant_pay"
    UNKNOWN = "unknown"


class AllocationMethod(CanonicalEnum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENT = "percent"  # the provider does not say what the percentage is of
    PERCENT_OF_GROSS = "percent_of_gross"
    PERCENT_OF_NET = "percent_of_net"
    PERCENT_OF_REMAINDER = "percent_of_remainder"
    REMAINDER = "remainder"
    UNKNOWN = "unknown"


class DepositStatus(CanonicalEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PRENOTE = "prenote"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DepositSource(Model):
    """Provider, company and employee IDs, plus the provider's ID for the line when it has one."""

    provider: str
    company_id: str
    employee_id: str
    deposit_id: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Allocation(Model):
    """How much of the pay goes to this account. Amount and percent are copied, never derived."""

    method: Optional[CodedValue] = None
    amount: Optional[Money] = None
    percent: Optional[Decimal] = None


@dataclass(frozen=True, slots=True)
class DirectDeposit(Model):
    key: str
    employee_key: str
    company_key: str
    source: DepositSource
    bank_name: Optional[str] = None
    routing_number: Optional[str] = None
    account_number_last4: Optional[str] = None
    account_type: Optional[CodedValue] = None
    allocation: Allocation = field(default_factory=Allocation)
    priority: Optional[int] = None
    status: Optional[CodedValue] = None
    effective: Optional[DateRange] = None
    unmapped: dict[str, Any] = field(default_factory=dict)
