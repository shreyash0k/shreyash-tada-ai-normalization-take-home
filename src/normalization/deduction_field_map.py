"""Where each canonical deduction field comes from, per provider.

Reference data for the coverage view, in the same form as ``field_map``:
statuses, source paths and ``<file>#<JSON pointer>`` evidence.
``tests/test_deduction_field_map.py`` checks each pointer resolves and each
status agrees with the golden deduction outputs.
"""
from .field_map import FieldEntry, mapped, not_mapped_yet, not_offered

SECTION_FIELDS = {
    "deduction": ("code", "category"),
    "calculation": ("calculation.method", "calculation.amount", "calculation.percent", "frequency"),
    "limits": ("limits.per_pay", "limits.monthly", "limits.quarterly", "limits.annual", "limits.lifetime"),
    "employer_match": ("employer_match.method", "employer_match.amount", "employer_match.percent",
                       "employer_match.annual_max"),
    "payee_order": ("payee.id", "payee.name", "priority"),
    "dates": ("effective.start", "effective.end"),
}


def canonical_fields() -> tuple[str, ...]:
    """Every row of the coverage grid, in display order."""
    return tuple(field for fields in SECTION_FIELDS.values() for field in fields)


def section(field: str) -> str:
    for name, fields in SECTION_FIELDS.items():
        if field in fields:
            return name
    raise KeyError(field)


def is_filled(deduction: dict, field: str) -> bool:
    """True when a normalized deduction (``to_dict`` form) has a value for a grid row."""
    value = deduction
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value not in (None, [], {})


PRISM = "contracts/prismhr/openapi/prismhr-2025.09.openapi.json"
P = PRISM + "#/components/schemas/EmployeeDeductions-Deduction/properties"
I = ("contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/"
     "AOS.PayrollOffice.RestAPI.Models.EmployeePayItemModel/properties")
U = "contracts/ukg-ready/reference-schemas.json#/schemas/133/schema/properties"

PRISMHR_MAXIMUM = "maximum, when basis is {}"

PRISMHR = {
    "code": mapped("deductionCode, labelled by description", P + "/deductionCode"),
    "category": mapped("deductionType, labelled from the DeductionCodeDetail code list", P + "/deductionType"),
    "calculation.method": mapped("deductionMethod, labelled from the DeductionCodeDetail code list",
                                 P + "/deductionMethod"),
    "calculation.amount": mapped("amount, when usePercent is false", P + "/amount"),
    "calculation.percent": mapped("amount, when usePercent is true", P + "/amount"),
    "frequency": not_mapped_yet(
        "period", P + "/period",
        "period lists the pay periods of the month when the deduction is taken. Turning it into a shared "
        "frequency needs the pay schedule, which the deduction call does not return."),
    "limits.per_pay": mapped("limit", P + "/limit"),
    "limits.monthly": mapped(PRISMHR_MAXIMUM.format("M"), P + "/maximum"),
    "limits.quarterly": mapped(PRISMHR_MAXIMUM.format("Q"), P + "/maximum"),
    "limits.annual": mapped(PRISMHR_MAXIMUM.format("A"), P + "/maximum"),
    "limits.lifetime": mapped(PRISMHR_MAXIMUM.format("L"), P + "/maximum"),
    "employer_match.method": mapped("matchMethod", P + "/matchMethod"),
    "employer_match.amount": mapped("matchAmount, when matchMethod is F", P + "/matchAmount"),
    "employer_match.percent": mapped("matchAmount, when matchMethod is P", P + "/matchAmount"),
    "employer_match.annual_max": not_offered("The match has a method and an amount but no cap.", P),
    "payee.id": mapped("cutbackPayeeCode", P + "/cutbackPayeeCode"),
    "payee.name": mapped("getPayee: payeeName", PRISM + "#/components/schemas/PayeeDetails/properties/payeeName"),
    "priority": not_offered("Deduction lines have no order number.", P),
    "effective.start": mapped("startDate", P + "/startDate"),
    "effective.end": mapped("stopDate", P + "/stopDate"),
}

ISOLVED_NO_SETUP = "Pay items carry a code, figures and dates, but no {}."

ISOLVED = {
    "code": mapped("payItemCode, labelled by payItemName", I + "/payItemCode"),
    "category": not_offered(ISOLVED_NO_SETUP.format("deduction type"), I),
    "calculation.method": not_offered(
        "Pay items have no calculation method. calcParams labels each figure, not how it is applied.",
        I + "/calcParams"),
    "calculation.amount": mapped("calcParams, the first Amount", I + "/calcParams"),
    "calculation.percent": mapped("calcParams, the first Percent", I + "/calcParams"),
    "frequency": not_offered(
        "Pay items have no frequency. scheduleOverride has no documented values, so it is not known to "
        "be one.", I + "/scheduleOverride"),
    "limits.per_pay": not_offered(ISOLVED_NO_SETUP.format("limits"), I),
    "limits.monthly": not_offered(ISOLVED_NO_SETUP.format("limits"), I),
    "limits.quarterly": not_offered(ISOLVED_NO_SETUP.format("limits"), I),
    "limits.annual": not_offered(ISOLVED_NO_SETUP.format("limits"), I),
    "limits.lifetime": not_offered(ISOLVED_NO_SETUP.format("limits"), I),
    "employer_match.method": not_offered(ISOLVED_NO_SETUP.format("employer match"), I),
    "employer_match.amount": not_offered(ISOLVED_NO_SETUP.format("employer match"), I),
    "employer_match.percent": not_offered(ISOLVED_NO_SETUP.format("employer match"), I),
    "employer_match.annual_max": not_offered(ISOLVED_NO_SETUP.format("employer match"), I),
    "payee.id": not_offered(ISOLVED_NO_SETUP.format("payee"), I),
    "payee.name": not_offered(ISOLVED_NO_SETUP.format("payee"), I),
    "priority": not_offered(ISOLVED_NO_SETUP.format("order number"), I),
    "effective.start": mapped("startDate", I + "/startDate"),
    "effective.end": mapped("stopDate", I + "/stopDate"),
}

UKG_NO_MATCH = "The employer side has an annual maximum and a frequency, but no calculation method."

UKG_READY = {
    "code": mapped("deduction.code, labelled by deduction.name", U + "/deduction/properties/code"),
    "category": not_offered(
        "Deduction lines and the deduction code lookup carry only a code and a name, no type.",
        U + "/deduction/properties"),
    "calculation.method": mapped("ee_calc_method.method.type, labelled by display_name",
                                 U + "/ee_calc_method/properties/method/properties/type"),
    "calculation.amount": mapped("ee_calc_method.amount", U + "/ee_calc_method/properties/amount"),
    "calculation.percent": mapped("ee_calc_method.percent", U + "/ee_calc_method/properties/percent"),
    "frequency": mapped("ee_frequency.type, labelled by display_name",
                        U + "/ee_frequency/properties/type"),
    "limits.per_pay": mapped("ee_max_calc_method.amount", U + "/ee_max_calc_method/properties/amount"),
    "limits.monthly": not_offered("The only caps are a per-pay maximum and an annual maximum.", U),
    "limits.quarterly": not_offered("The only caps are a per-pay maximum and an annual maximum.", U),
    "limits.annual": mapped("annual_max_amount", U + "/annual_max_amount"),
    "limits.lifetime": not_offered("The only caps are a per-pay maximum and an annual maximum.", U),
    "employer_match.method": not_offered(UKG_NO_MATCH, U),
    "employer_match.amount": not_offered(UKG_NO_MATCH, U),
    "employer_match.percent": not_offered(UKG_NO_MATCH, U),
    "employer_match.annual_max": mapped("er_annual_max_amount", U + "/er_annual_max_amount"),
    "payee.id": mapped("vendor.id", U + "/vendor/properties/id"),
    "payee.name": mapped("vendor.name", U + "/vendor/properties/name"),
    "priority": mapped("sequence", U + "/sequence"),
    "effective.start": mapped("effective_from", U + "/effective_from"),
    "effective.end": mapped("effective_to", U + "/effective_to"),
}

FIELD_MAP: dict[str, dict[str, FieldEntry]] = {
    "prismhr": PRISMHR,
    "isolved": ISOLVED,
    "ukg-ready": UKG_READY,
}
