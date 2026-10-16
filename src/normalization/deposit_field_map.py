"""Where each canonical direct deposit field comes from, per provider.

Reference data for the coverage view, in the same form as ``field_map``:
statuses, source paths and ``<file>#<JSON pointer>`` evidence.
``tests/test_deposit_field_map.py`` checks each pointer resolves and each
status agrees with the golden direct deposit outputs.
"""
from .field_map import FieldEntry, mapped, not_offered

SECTION_FIELDS = {
    "bank_account": ("bank_name", "routing_number", "account_number_last4", "account_type"),
    "allocation": ("allocation.method", "allocation.amount", "allocation.percent", "priority"),
    "status_dates": ("status", "effective.start", "effective.end"),
}


def canonical_fields() -> tuple[str, ...]:
    """Every row of the coverage grid, in display order."""
    return tuple(field for fields in SECTION_FIELDS.values() for field in fields)


def section(field: str) -> str:
    for name, fields in SECTION_FIELDS.items():
        if field in fields:
            return name
    raise KeyError(field)


def is_filled(deposit: dict, field: str) -> bool:
    """True when a normalized deposit (``to_dict`` form) has a value for a grid row."""
    value = deposit
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value not in (None, [], {})


P = "contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/AchVoucher/properties"
I = ("contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/"
     "AOS.PayrollOffice.RestAPI.Models.EmployeeDirectDepositModel/properties")
U = "contracts/ukg-ready/reference-schemas.json#/schemas/137/schema/properties/deposits/items/properties"
NO_DATES = "Deposit lines have no start or end date."

PRISMHR = {
    "bank_name": mapped("bankName", P + "/bankName"),
    "routing_number": mapped("transitNum", P + "/transitNum"),
    "account_number_last4": mapped("accountNum, last four digits", P + "/accountNum"),
    "account_type": mapped("accountType", P + "/accountType"),
    "allocation.method": mapped("method", P + "/method"),
    "allocation.amount": mapped("amount, when method is F or FS", P + "/amount"),
    "allocation.percent": mapped("amount, when method is P or PN", P + "/amount"),
    "priority": not_offered(
        "Deposit lines have no sequence number, and PrismHR does not say the list order is the payment "
        "order (docs/DECISIONS.md, PrismHR deposit position entry).", P),
    "status": mapped("status", P + "/status"),
    "effective.start": not_offered(NO_DATES, P),
    "effective.end": not_offered(NO_DATES, P),
}

ISOLVED = {
    "bank_name": mapped("bankName", I + "/bankName"),
    "routing_number": mapped("routingNumber", I + "/routingNumber"),
    "account_number_last4": mapped("accountNumber, last four digits", I + "/accountNumber"),
    "account_type": mapped("accountType", I + "/accountType"),
    "allocation.method": mapped("amount or percent, whichever is set; sequenceNumber 0 is the remainder",
                                I + "/sequenceNumber"),
    "allocation.amount": mapped("amount", I + "/amount"),
    "allocation.percent": mapped("percent", I + "/percent"),
    "priority": mapped("sequenceNumber", I + "/sequenceNumber"),
    "status": mapped("status", I + "/status"),
    "effective.start": not_offered(
        "Deposit lines have no start or end date. frequency says how often a line applies, not when.", I),
    "effective.end": not_offered(
        "Deposit lines have no start or end date. frequency says how often a line applies, not when.", I),
}

UKG_READY = {
    "bank_name": not_offered(
        "Lines carry a routing number but no bank name. name has no description, and the JSON and XML "
        "schemas disagree on its type, so it is not known to be the bank name.", U),
    "routing_number": mapped("routing_number", U + "/routing_number"),
    "account_number_last4": mapped("account_number, last four digits", U + "/account_number"),
    "account_type": mapped("account_type", U + "/account_type"),
    "allocation.method": mapped("calc_method.type, labelled by calc_method.display_name",
                                U + "/calc_method/properties/type"),
    "allocation.amount": mapped("amount, when calc_method is FLAT_AMOUNT", U + "/amount"),
    "allocation.percent": mapped(
        "percentage, when calc_method is GROSS_EARNING, NET_PAY or "
        "DIRECT_DEPOSIT_PER_OF_REMAINDER", U + "/percentage"),
    "priority": mapped("sequence", U + "/sequence"),
    "status": mapped("active", U + "/active"),
    "effective.start": mapped("active_from", U + "/active_from"),
    "effective.end": mapped("active_to", U + "/active_to"),
}

FIELD_MAP: dict[str, dict[str, FieldEntry]] = {
    "prismhr": PRISMHR,
    "isolved": ISOLVED,
    "ukg-ready": UKG_READY,
}
