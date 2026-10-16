"""Canonical employee record."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from .common import Address, CodedValue, Email, Model, Money, Phone


@dataclass(frozen=True, slots=True)
class SourceRef(Model):
    """Where a record came from: provider, company, and the provider's own IDs."""

    provider: str
    company_id: str
    employee_id: str
    secondary_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Person(Model):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[CodedValue] = None
    marital_status: Optional[CodedValue] = None
    citizenship: Optional[CodedValue] = None
    ethnicity: Optional[CodedValue] = None
    ssn_last4: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Contact(Model):
    addresses: list[Address] = field(default_factory=list)
    phones: list[Phone] = field(default_factory=list)
    emails: list[Email] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Employment(Model):
    status: Optional[CodedValue] = None
    status_date: Optional[date] = None
    employment_type: Optional[CodedValue] = None
    hire_date: Optional[date] = None
    original_hire_date: Optional[date] = None
    rehire_date: Optional[date] = None
    termination_date: Optional[date] = None
    seniority_date: Optional[date] = None
    termination_reason: Optional[CodedValue] = None
    rehire_eligible: Optional[bool] = None
    flsa_exempt: Optional[bool] = None
    contractor_1099: Optional[bool] = None


@dataclass(frozen=True, slots=True)
class Job(Model):
    title: Optional[str] = None
    job_code: Optional[CodedValue] = None
    department: Optional[CodedValue] = None
    location: Optional[CodedValue] = None
    division: Optional[CodedValue] = None
    manager_employee_id: Optional[str] = None
    job_start_date: Optional[date] = None


@dataclass(frozen=True, slots=True)
class Compensation(Model):
    """Current pay as the provider states it. Nothing is derived between fields."""

    pay_type: Optional[CodedValue] = None
    pay_frequency: Optional[CodedValue] = None
    rate: Optional[Money] = None
    rate_period: Optional[CodedValue] = None
    hourly_rate: Optional[Money] = None
    annual_amount: Optional[Money] = None
    per_period_amount: Optional[Money] = None
    standard_hours: Optional[Decimal] = None
    standard_hours_period: Optional[CodedValue] = None
    standard_work_day_hours: Optional[Decimal] = None
    effective_date: Optional[date] = None


@dataclass(frozen=True, slots=True)
class Employee(Model):
    key: str
    company_key: str
    source: SourceRef
    person: Person
    contact: Contact
    employment: Employment
    job: Job
    compensation: Compensation
    unmapped: dict[str, Any] = field(default_factory=dict)
