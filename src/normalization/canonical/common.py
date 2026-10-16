"""Shared building blocks of the canonical model.

Every class here is a frozen dataclass. ``__post_init__`` checks that each
field holds exactly the declared type: nothing is coerced, so a string where a
``Decimal`` is expected is a programming error in an adapter, not something the
model papers over. ``to_dict`` turns a model into plain JSON-serializable data.
"""
import dataclasses
import types
import typing
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Union


class CanonicalEnum(Enum):
    """Base for canonical enums. Every member list ends with ``UNKNOWN``."""

    def __str__(self):
        return self.value


class EmploymentStatus(CanonicalEnum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


class EmploymentType(CanonicalEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    UNKNOWN = "unknown"


class PayType(CanonicalEnum):
    SALARY = "salary"
    HOURLY = "hourly"
    COMMISSION = "commission"
    DRIVER = "driver"  # PrismHR payMethod 'D' (driver); no other provider documents it
    CONTRACTOR_1099 = "contractor_1099"
    UNKNOWN = "unknown"


class PayPeriod(CanonicalEnum):
    HOURLY = "hourly"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMIMONTHLY = "semimonthly"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    PAY_PERIOD = "pay_period"
    UNKNOWN = "unknown"


class Gender(CanonicalEnum):
    MALE = "male"
    FEMALE = "female"
    NONBINARY = "nonbinary"
    DECLINED = "declined"
    UNKNOWN = "unknown"


class MaritalStatus(CanonicalEnum):
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    CIVIL_UNION = "civil_union"
    OTHER = "other"
    UNKNOWN = "unknown"


class Citizenship(CanonicalEnum):
    CITIZEN = "citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    WORK_PERMIT = "work_permit"
    NONCITIZEN_NATIONAL = "noncitizen_national"
    UNKNOWN = "unknown"


class AddressKind(CanonicalEnum):
    HOME = "home"
    MAILING = "mailing"
    W2 = "w2"
    WORK = "work"
    LEGAL = "legal"
    UNKNOWN = "unknown"


class PhoneKind(CanonicalEnum):
    HOME = "home"
    MOBILE = "mobile"
    WORK = "work"
    OTHER = "other"
    UNKNOWN = "unknown"


class EmailKind(CanonicalEnum):
    PERSONAL = "personal"
    WORK = "work"
    OTHER = "other"
    UNKNOWN = "unknown"


# --- type checking -----------------------------------------------------------

_NONE = type(None)


def _matches(value, hint) -> bool:
    """Return True when ``value`` is exactly of the declared ``hint`` (no coercion)."""
    if hint is Any:
        return True
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin in (Union, types.UnionType):
        return any(_matches(value, arg) for arg in args)
    if hint is _NONE:
        return value is None
    if origin is list:
        return isinstance(value, list) and all(_matches(item, args[0]) for item in value)
    if origin is dict:
        return isinstance(value, dict) and all(
            _matches(k, args[0]) and _matches(v, args[1]) for k, v in value.items()
        )
    if hint is bool:
        return isinstance(value, bool)
    if hint is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(hint, type):
        return isinstance(value, hint)
    return False


def check_types(instance) -> None:
    """Raise TypeError if any dataclass field of ``instance`` has the wrong type."""
    hints = typing.get_type_hints(type(instance))
    for f in dataclasses.fields(instance):
        value = getattr(instance, f.name)
        if not _matches(value, hints[f.name]):
            raise TypeError(
                f"{type(instance).__name__}.{f.name} expected {hints[f.name]!r}, "
                f"got {type(value).__name__} {value!r}"
            )


def to_jsonable(obj):
    """Convert a model (or any nested value) into JSON-serializable data."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, list):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, tuple):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    raise TypeError(f"Cannot serialize {type(obj).__name__}")


class Model:
    """Mixin giving every canonical dataclass strict type checks and ``to_dict``."""

    __slots__ = ()

    def __post_init__(self):
        check_types(self)

    def to_dict(self) -> dict:
        return to_jsonable(self)


# --- value objects -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CodedValue(Model):
    """A provider code kept alongside its canonical reading.

    ``raw`` is the value exactly as the provider sent it. ``label`` is the
    provider-side description when one exists (a lookup name, a value
    description). ``value`` is the canonical enum member, ``UNKNOWN`` when the
    code has no documented meaning, or ``None`` when the field has no canonical
    domain at all (tenant-defined departments, job codes, and so on).
    """

    raw: Optional[Union[str, int]]
    label: Optional[str] = None
    value: Optional[CanonicalEnum] = None


@dataclass(frozen=True, slots=True)
class Address(Model):
    kind: AddressKind
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


@dataclass(frozen=True, slots=True)
class Phone(Model):
    kind: PhoneKind
    number: str
    extension: Optional[str] = None
    preferred: Optional[bool] = None


@dataclass(frozen=True, slots=True)
class Email(Model):
    kind: EmailKind
    address: str


@dataclass(frozen=True, slots=True)
class Money(Model):
    amount: Decimal
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class DateRange(Model):
    start: Optional[date] = None
    end: Optional[date] = None
