"""Canonical company record (a stub until the company data type is built)."""
from dataclasses import dataclass, field
from typing import Optional

from .common import Model


@dataclass(frozen=True, slots=True)
class CompanySource(Model):
    provider: str
    company_id: str
    secondary_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Company(Model):
    key: str
    source: CompanySource
    name: Optional[str] = None
    ein: Optional[str] = None
