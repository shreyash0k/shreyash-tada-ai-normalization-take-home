"""Structured issues and the top-level normalization output."""
from dataclasses import dataclass, field
from typing import Any, Optional

from .common import CanonicalEnum, Model
from .company import Company
from .deduction import Deduction
from .direct_deposit import DirectDeposit
from .employee import Employee
from .payroll import Paycheck, PayRun


class IssueCode(CanonicalEnum):
    UNDOCUMENTED_CODE = "undocumented_code"
    UNMAPPED_LABEL = "unmapped_label"
    INVALID_DATE = "invalid_date"
    INVALID_NUMBER = "invalid_number"
    MISSING_SECTION = "missing_section"
    MISSING_LOOKUP = "missing_lookup"
    SPEC_LIVE_MISMATCH = "spec_live_mismatch"
    MASKED_VALUE = "masked_value"
    OUT_OF_SCHEMA_VALUE = "out_of_schema_value"
    MULTIPLE_CURRENT_RATES = "multiple_current_rates"
    INCONSISTENT_ALLOCATION = "inconsistent_allocation"
    UNKNOWN = "unknown"


class Severity(CanonicalEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Issue(Model):
    """One problem found while normalizing. ``raw_value`` is already redacted."""

    code: IssueCode
    severity: Severity
    source_path: str
    action: str
    record_key: Optional[str] = None
    raw_value: Any = None
    message: Optional[str] = None


@dataclass(frozen=True, slots=True)
class NormalizedOutput(Model):
    provider: str
    company: Company
    employees: list[Employee] = field(default_factory=list)
    direct_deposits: list[DirectDeposit] = field(default_factory=list)
    deductions: list[Deduction] = field(default_factory=list)
    pay_runs: list[PayRun] = field(default_factory=list)
    paychecks: list[Paycheck] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    schema_version: str = "1"
