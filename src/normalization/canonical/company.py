"""Canonical company record: the profile plus its tax ids, work locations and pay groups.

Employee, direct deposit, deduction and payroll outputs carry the same class
with only ``key``, ``source`` and ``ein`` filled in; the full record comes from
a company bundle.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from .common import Address, CanonicalEnum, CodedValue, DateRange, Email, Model, Phone


class CompanyStatus(CanonicalEnum):
    ACTIVE = "active"
    PENDING = "pending"
    INACTIVE = "inactive"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CompanySource(Model):
    provider: str
    company_id: str
    secondary_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TaxId(Model):
    key: str
    source_id: Optional[str] = None
    tax_id: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkLocation(Model):
    key: str
    source_id: str
    code: Optional[CodedValue] = None
    address: Optional[Address] = None
    active: Optional[bool] = None
    end_date: Optional[date] = None
    remote: Optional[bool] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PayGroup(Model):
    key: str
    source_id: str
    code: Optional[CodedValue] = None
    frequency: Optional[CodedValue] = None
    active: Optional[bool] = None
    effective: Optional[DateRange] = None
    unmapped: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Company(Model):
    key: str
    source: CompanySource
    name: Optional[str] = None
    ein: Optional[str] = None
    legal_name: Optional[str] = None
    status: Optional[CodedValue] = None
    status_date: Optional[date] = None
    entity_type: Optional[CodedValue] = None
    service_type: Optional[CodedValue] = None
    naics_code: Optional[str] = None
    sic_code: Optional[str] = None
    address: Optional[Address] = None
    phone: Optional[Phone] = None
    email: Optional[Email] = None
    website: Optional[str] = None
    parent: Optional[CodedValue] = None
    tax_ids: list[TaxId] = field(default_factory=list)
    work_locations: list[WorkLocation] = field(default_factory=list)
    pay_groups: list[PayGroup] = field(default_factory=list)
    unmapped: dict[str, Any] = field(default_factory=dict)
