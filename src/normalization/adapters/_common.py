"""Helpers shared by every adapter.

Four ideas live here:

* ``Reader`` wraps a raw provider document and remembers which JSON paths an
  adapter consumed. Whatever is left over becomes the employee's ``unmapped``
  dictionary, so no provider field is silently dropped.
* ``Collector`` gathers structured ``Issue`` records and offers parsers that
  report problems instead of raising: a bad date becomes ``None`` plus an
  ``invalid_date`` issue.
* ``CodeTable`` is a documented code -> canonical enum mapping with its
  evidence pointer. ``Collector.code`` turns a raw code into a ``CodedValue``
  and reports codes the table does not know.
* ``line_readers`` gives each line of a paycheck its own ``Reader``, so a
  line's ``unmapped`` holds only that line's leftover fields.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union

from ..canonical import CanonicalEnum, CodedValue, Issue, IssueCode, Money, Severity

REDACTED = "[redacted]"
_SENSITIVE_PATH = re.compile(
    r"(?i)(ssn|social_security|social_insurance|national_insurance|national_id"
    r"|(^|[._\[])bsn($|[._\[])"
    r"|password|secret|token|ticket|photo_href|bank_account"
    r"|account_?num|routing_?num|transit_?num)"
)
_SECRET_QUERY = re.compile(r"(?i)([?&](?:token|ticket|sessionid|access_token)=)[^&#]*")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?$")
_MASKED = re.compile(r"^[*Xx\-\s]+$")


def is_blank(value: Any) -> bool:
    return value is None or value == ""


def is_masked(value: Any) -> bool:
    """True for a provider placeholder such as ``**********`` or ``XXX-XX-XXXX``."""
    return isinstance(value, str) and bool(_MASKED.match(value))


def text(value: Any) -> Optional[str]:
    """Return a non-empty string or None. Non-strings are converted with ``str``."""
    if is_blank(value):
        return None
    return value if isinstance(value, str) else str(value)


def redact(path: str, value: Any) -> Any:
    if _SENSITIVE_PATH.search(path) and not is_blank(value):
        return REDACTED
    if isinstance(value, str):
        return _SECRET_QUERY.sub(rf"\g<1>{REDACTED}", value)
    return value


def join_path(prefix: str, key: Union[str, int]) -> str:
    if isinstance(key, int):
        return f"{prefix}[{key}]"
    return f"{prefix}.{key}" if prefix else key


_MISSING = object()


class Reader:
    """A raw JSON document plus the set of paths an adapter has consumed."""

    def __init__(self, data: Any, prefix: str = "", used: Optional[set] = None):
        self.data = data
        self.prefix = prefix
        self.used = used if used is not None else set()

    def _resolve(self, keys):
        node, path = self.data, self.prefix
        for key in keys:
            path = join_path(path, key)
            if isinstance(node, dict) and key in node:
                node = node[key]
            elif isinstance(node, list) and isinstance(key, int) and 0 <= key < len(node):
                node = node[key]
            else:
                return _MISSING, path
        return node, path

    def has(self, *keys) -> bool:
        node, _ = self._resolve(keys)
        return node is not _MISSING

    def peek(self, *keys, default=None):
        node, _ = self._resolve(keys)
        return default if node is _MISSING else node

    def get(self, *keys, default=None):
        """Return the value at ``keys`` and mark the path consumed."""
        node, path = self._resolve(keys)
        self.used.add(path)
        return default if node is _MISSING else node

    def consume(self, *keys) -> None:
        _, path = self._resolve(keys)
        self.used.add(path)

    def path(self, *keys) -> str:
        _, path = self._resolve(keys)
        return path

    def sub(self, *keys) -> "Reader":
        """A reader for a nested object that shares this reader's consumed set."""
        node, path = self._resolve(keys)
        return Reader(None if node is _MISSING else node, path, self.used)

    def unmapped(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        self._walk(self.data, self.prefix, out)
        return out

    def _walk(self, node, path, out):
        if path in self.used:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                self._walk(value, join_path(path, key), out)
        elif isinstance(node, list) and node and all(isinstance(item, dict) for item in node):
            for index, value in enumerate(node):
                self._walk(value, join_path(path, index), out)
        else:
            out[path] = redact(path, node)


@dataclass(frozen=True)
class CodeTable:
    """Documented provider codes for one field, with the evidence they rest on.

    ``kind`` is ``"code"`` for provider codes with documented meanings and
    ``"label"`` for exact-match English labels observed live (allowlists).
    """

    name: str
    enum: type[CanonicalEnum]
    entries: dict[Union[str, int], CanonicalEnum]
    evidence: str
    kind: str = "code"


class Collector:
    """Accumulates issues and parses raw values without raising."""

    def __init__(self):
        self.issues: list[Issue] = []
        self._seen: dict[str, set] = {}

    def add(self, code: IssueCode, severity: Severity, source_path: str, action: str,
            record_key: Optional[str] = None, raw_value: Any = None,
            message: Optional[str] = None) -> None:
        self.issues.append(Issue(code=code, severity=severity, source_path=source_path,
                                 action=action, record_key=record_key,
                                 raw_value=redact(source_path, raw_value), message=message))

    # -- parsers -------------------------------------------------------------

    def date(self, raw: Any, path: str, record_key: Optional[str]) -> Optional[date]:
        if is_blank(raw):
            return None
        if isinstance(raw, str):
            try:
                if _DATE.match(raw):
                    return date.fromisoformat(raw)
                if _DATETIME.match(raw):
                    return datetime.fromisoformat(raw).date()
            except ValueError:
                pass
        self.add(IssueCode.INVALID_DATE, Severity.ERROR, path, "set null", record_key, raw,
                 "value is not a YYYY-MM-DD date or ISO 8601 date-time")
        return None

    def decimal(self, raw: Any, path: str, record_key: Optional[str]) -> Optional[Decimal]:
        if is_blank(raw):
            return None
        value: Optional[Decimal] = None
        if isinstance(raw, bool):
            value = None
        elif isinstance(raw, int):
            value = Decimal(raw)
        elif isinstance(raw, float):
            value = Decimal(repr(raw))
        elif isinstance(raw, str):
            try:
                value = Decimal(raw.strip())
            except InvalidOperation:
                value = None
        if value is None or not value.is_finite():
            self.add(IssueCode.INVALID_NUMBER, Severity.ERROR, path, "set null", record_key, raw,
                     "value is not a finite decimal number")
            return None
        return value

    def money(self, raw: Any, path: str, record_key: Optional[str],
              currency: str = "USD") -> Optional[Money]:
        amount = self.decimal(raw, path, record_key)
        return None if amount is None else Money(amount=amount, currency=currency)

    def last4(self, raw: Any, path: str, record_key: Optional[str]) -> Optional[str]:
        """Return the last four digits of an identifier, never the whole value.

        An identifier with fewer than four digits becomes None, since its
        "last four" would be the whole number.
        """
        if is_blank(raw):
            return None
        if not isinstance(raw, str):
            raw = str(raw)
        if _MASKED.match(raw):
            self.add(IssueCode.MASKED_VALUE, Severity.INFO, path, "set null", record_key, raw,
                     "provider returned a masked value")
            return None
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 4:
            self.add(IssueCode.INVALID_NUMBER, Severity.WARNING, path, "set null", record_key,
                     REDACTED, "identifier has fewer than four digits")
            return None
        return digits[-4:]

    # -- coded values ----------------------------------------------------------

    def code(self, table: CodeTable, raw: Any, path: str, record_key: Optional[str],
             label: Optional[str] = None,
             issue_code: Optional[IssueCode] = None) -> Optional[CodedValue]:
        """Map a raw code through ``table``; unknown codes become UNKNOWN plus an issue.

        ``issue_code`` overrides the issue reported for an unknown value (for
        example when a provider returns prose where the spec documents codes).
        """
        if is_blank(raw):
            return None
        if not isinstance(raw, (str, int)) or isinstance(raw, bool):
            raw = str(raw)
        member = table.entries.get(raw)
        if member is None:
            if issue_code is not None:
                code, message = issue_code, "value is not one of the documented codes"
            elif table.kind == "label":
                code, message = IssueCode.UNMAPPED_LABEL, "label is not on the documented allowlist"
            else:
                code, message = IssueCode.UNDOCUMENTED_CODE, "code has no documented meaning"
            self.add(code, Severity.WARNING, path, "kept raw value; canonical value set to unknown",
                     record_key, raw, f"{table.name}: {message} ({table.evidence})")
            member = table.enum.UNKNOWN
        return CodedValue(raw=raw, label=label, value=member)

    def code_once(self, table: CodeTable, raw: Any, path: str, record_key: Optional[str],
                  label: Optional[str] = None,
                  issue_code: Optional[IssueCode] = None) -> Optional[CodedValue]:
        """Like ``code``, but a value the table does not know is reported only the first time it appears."""
        seen = self._seen.setdefault(table.name, set())
        target = self if str(raw) not in seen else Collector()
        seen.add(str(raw))
        return target.code(table, raw, path, record_key, label, issue_code)

    @staticmethod
    def raw_code(raw: Any, label: Optional[str] = None) -> Optional[CodedValue]:
        """A tenant-defined code with no canonical domain: keep raw and label only."""
        if is_blank(raw):
            return None
        if not isinstance(raw, (str, int)) or isinstance(raw, bool):
            raw = str(raw)
        return CodedValue(raw=raw, label=text(label), value=None)


def line_readers(reader: Reader, name: str) -> list[Reader]:
    """One reader per object in the array ``name``, each keeping its own leftovers.

    The array is consumed from ``reader`` when it is a list or null; any other
    value stays in the parent's ``unmapped``.
    """
    items = reader.peek(name)
    if items is not None and not isinstance(items, list):
        return []
    reader.consume(name)
    base = reader.path(name)
    return [Reader(item, f"{base}[{index}]") for index, item in enumerate(items or [])
            if isinstance(item, dict)]


def nonzero(raw: Any) -> bool:
    """False for a missing, empty or zero amount."""
    return raw not in (None, "", 0)


def boolean(raw: Any) -> Optional[bool]:
    """Return a bool only when the provider sent a JSON boolean."""
    return raw if isinstance(raw, bool) else None
