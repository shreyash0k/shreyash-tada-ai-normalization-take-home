"""Canonical model: provider-independent records, coded values, and issues."""
from .common import (
    Address,
    AddressKind,
    CanonicalEnum,
    Citizenship,
    CodedValue,
    DateRange,
    Email,
    EmailKind,
    EmploymentStatus,
    EmploymentType,
    Gender,
    MaritalStatus,
    Model,
    Money,
    PayPeriod,
    PayType,
    Phone,
    PhoneKind,
    to_jsonable,
)
from .company import Company, CompanySource
from .deduction import (
    Calculation,
    CalculationMethod,
    Deduction,
    DeductionCategory,
    DeductionFrequency,
    DeductionSource,
    EmployerMatch,
    Limits,
    MatchMethod,
    Payee,
)
from .direct_deposit import (
    AccountType,
    Allocation,
    AllocationMethod,
    DepositSource,
    DepositStatus,
    DirectDeposit,
)
from .employee import Compensation, Contact, Employee, Employment, Job, Person, SourceRef
from .issues import Issue, IssueCode, NormalizedOutput, Severity

__all__ = [
    "Address", "AddressKind", "CanonicalEnum", "Citizenship", "CodedValue", "DateRange",
    "Email", "EmailKind", "EmploymentStatus", "EmploymentType", "Gender", "MaritalStatus",
    "Model", "Money", "PayPeriod", "PayType", "Phone", "PhoneKind", "to_jsonable",
    "Company", "CompanySource",
    "AccountType", "Allocation", "AllocationMethod", "DepositSource", "DepositStatus", "DirectDeposit",
    "Calculation", "CalculationMethod", "Deduction", "DeductionCategory", "DeductionFrequency",
    "DeductionSource", "EmployerMatch", "Limits", "MatchMethod", "Payee",
    "Compensation", "Contact", "Employee", "Employment", "Job", "Person", "SourceRef",
    "Issue", "IssueCode", "NormalizedOutput", "Severity",
]
