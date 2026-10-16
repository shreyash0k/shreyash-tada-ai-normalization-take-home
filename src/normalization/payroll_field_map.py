"""Where each canonical payroll field comes from, per provider.

Reference data for the coverage view, in the same form as ``field_map``:
statuses, source paths and ``<file>#<JSON pointer>`` evidence.
``tests/test_payroll_field_map.py`` checks each pointer resolves and each
status agrees with the golden payroll outputs.

Row names start with the record or line list (``pay_run``, ``paycheck``,
``earnings``, and so on), because the same name occurs on more than one.
"""
from .field_map import FieldEntry, mapped, not_offered

SECTION_FIELDS = {
    "pay_run": ("pay_run.type", "pay_run.status", "pay_run.pay_date", "pay_run.period.start",
                "pay_run.period.end", "pay_run.description", "pay_run.pay_group"),
    "paycheck": ("paycheck.type", "paycheck.status", "paycheck.pay_date", "paycheck.period.start",
                 "paycheck.period.end", "paycheck.check_number", "paycheck.gross_pay", "paycheck.net_pay",
                 "paycheck.void_date"),
    "earnings": ("earnings.code", "earnings.category", "earnings.hours", "earnings.rate", "earnings.amount"),
    "taxes": ("taxes.code", "taxes.employee_amount", "taxes.employer_amount", "taxes.employee_taxable_wages",
              "taxes.employer_taxable_wages"),
    "deductions": ("deductions.code", "deductions.category", "deductions.amount"),
    "employer_contributions": ("employer_contributions.code", "employer_contributions.amount"),
    "payments": ("payments.method", "payments.amount", "payments.account_last4"),
}

def canonical_fields() -> tuple[str, ...]:
    """Every row of the coverage grid, in display order."""
    return tuple(field for fields in SECTION_FIELDS.values() for field in fields)


def section(field: str) -> str:
    for name, fields in SECTION_FIELDS.items():
        if field in fields:
            return name
    raise KeyError(field)


def _has(record: dict, field: str) -> bool:
    value = record
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value not in (None, [], {})


def is_filled(output: dict, field: str) -> bool:
    """True when any pay run, paycheck or line in a normalized payroll output has a value for a grid row."""
    head, _, rest = field.partition(".")
    if head == "pay_run":
        records = output["pay_runs"]
    elif head == "paycheck":
        records = output["paychecks"]
    else:
        records = [line for check in output["paychecks"] for line in check[head]]
    return any(_has(record, rest) for record in records)


PRISM = "contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas"
P_RUN = PRISM + "/BatchList/properties"
P_GROUP = PRISM + "/BatchByDateResponse-BatchList-PayGroup/properties"
P_INFO = PRISM + "/BatchControl/properties"
P_CHK = PRISM + "/PayrollVoucher/properties"
P_EARN = PRISM + "/Earning/properties"
P_EE_TAX = PRISM + "/EmployeeTax/properties"
P_ER_TAX = PRISM + "/CompanyTax/properties"
P_DED = PRISM + "/Deduction/properties"
P_CONTRIB = PRISM + "/EmployerContribution/properties"
P_DEPOSIT = PRISM + "/PayrollVoucher-DirectDeposit/properties"

PRISMHR = {
    "pay_run.type": mapped("batchType", P_RUN + "/batchType"),
    "pay_run.status": mapped("batchStatus", P_RUN + "/batchStatus"),
    "pay_run.pay_date": mapped("payDate", P_RUN + "/payDate"),
    "pay_run.period.start": mapped("payGroup[0].payPeriodStartDate", P_GROUP + "/payPeriodStartDate"),
    "pay_run.period.end": mapped("payGroup[0].payPeriodEndDate", P_GROUP + "/payPeriodEndDate"),
    "pay_run.description": mapped("batchDescription", P_INFO + "/batchDescription"),
    "pay_run.pay_group": mapped("payGroup[0].payGroupId", P_GROUP + "/payGroupId"),
    "paycheck.type": mapped("type", P_CHK + "/type"),
    "paycheck.status": mapped("status", P_CHK + "/status"),
    "paycheck.pay_date": mapped("payDate", P_CHK + "/payDate"),
    "paycheck.period.start": mapped("payPeriodStart", P_CHK + "/payPeriodStart"),
    "paycheck.period.end": mapped("payPeriodEnd", P_CHK + "/payPeriodEnd"),
    "paycheck.check_number": mapped("checkNumber", P_CHK + "/checkNumber"),
    "paycheck.gross_pay": mapped("totalEarnings", P_CHK + "/totalEarnings"),
    "paycheck.net_pay": mapped("netPay", P_CHK + "/netPay"),
    "paycheck.void_date": mapped("voidDate", P_CHK + "/voidDate"),
    "earnings.code": mapped("payCode, or otherEarnCode labelled by otherEarnsDesc", P_EARN + "/payCode"),
    "earnings.category": mapped("payClass, labelled by payClassDescription", P_EARN + "/payClass"),
    "earnings.hours": mapped("hoursUnits", P_EARN + "/hoursUnits"),
    "earnings.rate": mapped("unitRate", P_EARN + "/unitRate"),
    "earnings.amount": mapped("payAmount, or otherEarnAmount", P_EARN + "/payAmount"),
    "taxes.code": mapped("empTaxDeductCode, labelled by empTaxDeductCodeDesc, or comTaxDeductCode",
                         P_EE_TAX + "/empTaxDeductCode"),
    "taxes.employee_amount": mapped("empTaxAmount", P_EE_TAX + "/empTaxAmount"),
    "taxes.employer_amount": mapped("comTaxAmount", P_ER_TAX + "/comTaxAmount"),
    "taxes.employee_taxable_wages": mapped("empTaxableAmount", P_EE_TAX + "/empTaxableAmount"),
    "taxes.employer_taxable_wages": mapped("comTaxableAmount", P_ER_TAX + "/comTaxableAmount"),
    "deductions.code": mapped("deductCode, labelled by deductDescription, or otherDeductCode",
                              P_DED + "/deductCode"),
    "deductions.category": mapped("deductType", P_DED + "/deductType"),
    "deductions.amount": mapped("deductAmount, or otherDeductAmount", P_DED + "/deductAmount"),
    "employer_contributions.code": mapped("code, labelled by description", P_CONTRIB + "/code"),
    "employer_contributions.amount": mapped("amount", P_CONTRIB + "/amount"),
    "payments.method": mapped("checkAmt for a paper check, directDeposit for a deposit", P_CHK + "/checkAmt"),
    "payments.amount": mapped("checkAmt, or directDeposit.amount", P_CHK + "/checkAmt"),
    "payments.account_last4": mapped("directDeposit.accountNum", P_DEPOSIT + "/accountNum"),
}

ISO = "contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models"
I_RUN = ISO + ".PayrollRunHistoryModel/properties"
I_CHK = ISO + ".CheckModel/properties"
I_EARN = ISO + ".CheckEarningAccumulationModel/properties"
I_LINE = ISO + ".CheckAccumulationModel/properties"
I_TAX = ISO + ".CheckTaxAccumulationModel/properties"
I_BENEFIT = ISO + ".CheckBenefitTypeAccumulationModel/properties"
I_DEPOSIT = ISO + ".CheckDirectDepositAccumulationModel/properties"
I_PAY_GROUP = ("contracts/isolved/openapi/isolved-v6.swagger.json#/paths/"
               "~1api~1clients~1{clientId}~1legals~1{legalId}~1paygroupId~1{paygroupId}~1payrollRunHistory")

ISOLVED_NO_RATE = "Earning lines have hours and dollars, but no rate."
ISOLVED_NO_TYPE = "Deduction lines have a code and an amount, but no type."

ISOLVED = {
    "pay_run.type": mapped("payrollRunType", I_RUN + "/payrollRunType"),
    "pay_run.status": mapped("status", I_RUN + "/status"),
    "pay_run.pay_date": mapped("payDate", I_RUN + "/payDate"),
    "pay_run.period.start": mapped("periodBeginDate", I_RUN + "/periodBeginDate"),
    "pay_run.period.end": mapped("periodEndDate", I_RUN + "/periodEndDate"),
    "pay_run.description": mapped("payOfTheMonth", I_RUN + "/payOfTheMonth"),
    "pay_run.pay_group": mapped("the paygroupId the run history was fetched under", I_PAY_GROUP),
    "paycheck.type": mapped("checkTypeDescription", I_CHK + "/checkTypeDescription"),
    "paycheck.status": not_offered("Checks have no status. The run has one; the check does not.", I_CHK),
    "paycheck.pay_date": mapped("checkDate", I_CHK + "/checkDate"),
    "paycheck.period.start": mapped("periodBeginDate", I_CHK + "/periodBeginDate"),
    "paycheck.period.end": mapped("periodEndDate", I_CHK + "/periodEndDate"),
    "paycheck.check_number": mapped("checkNumber", I_CHK + "/checkNumber"),
    "paycheck.gross_pay": mapped("grossPay", I_CHK + "/grossPay"),
    "paycheck.net_pay": mapped("netPay", I_CHK + "/netPay"),
    "paycheck.void_date": not_offered(
        "Checks carry a reissue date (reissueCheckDate), not a void date.", I_CHK + "/reissueCheckDate"),
    "earnings.code": mapped("itemCode, labelled by itemDescription", I_EARN + "/itemCode"),
    "earnings.category": mapped("isMemoEarning, when true", I_EARN + "/isMemoEarning"),
    "earnings.hours": mapped("checkHours", I_EARN + "/checkHours"),
    "earnings.rate": not_offered(ISOLVED_NO_RATE, I_EARN),
    "earnings.amount": mapped("checkDollars", I_EARN + "/checkDollars"),
    "taxes.code": mapped("itemCode, labelled by itemDescription", I_TAX + "/itemCode"),
    "taxes.employee_amount": mapped("checkDollars, when isEmployeeTax is true", I_TAX + "/checkDollars"),
    "taxes.employer_amount": mapped("checkDollars, when isEmployeeTax is false", I_TAX + "/checkDollars"),
    "taxes.employee_taxable_wages": mapped("checkTaxableWages, when isEmployeeTax is true",
                                           I_TAX + "/checkTaxableWages"),
    "taxes.employer_taxable_wages": mapped("checkTaxableWages, when isEmployeeTax is false",
                                           I_TAX + "/checkTaxableWages"),
    "deductions.code": mapped("itemCode, labelled by itemDescription", I_LINE + "/itemCode"),
    "deductions.category": not_offered(ISOLVED_NO_TYPE, I_LINE),
    "deductions.amount": mapped("checkDollars", I_LINE + "/checkDollars"),
    "employer_contributions.code": mapped("benefitTitle", I_BENEFIT + "/benefitTitle"),
    "employer_contributions.amount": mapped("checkEmployerContribution", I_BENEFIT + "/checkEmployerContribution"),
    "payments.method": mapped(
        "checkAmount for a paper check, directDeposits for each account, otherwise directDepositAmount",
        I_CHK + "/checkAmount"),
    "payments.amount": mapped("checkAmount, depositAmount, or directDepositAmount", I_CHK + "/checkAmount"),
    "payments.account_last4": mapped("directDeposits.account", I_DEPOSIT + "/account"),
}

UKG = "contracts/ukg-ready/reference-schemas.json#/schemas"
U_RUN = UKG + "/358/schema/properties/payrolls/items/properties"
U_CHK = UKG + "/364/schema/properties"
U_EARN = U_CHK + "/earnings/items/properties"
U_TAX = U_CHK + "/taxes/items/properties"
U_DED = U_CHK + "/deductions/items/properties"
U_PAY = U_CHK + "/payments/items/properties"

UKG_NO_TOTALS = "Pay statements carry lines, but no gross or net total."
UKG_NO_CATEGORY = "type_name is an undescribed string that names the line, not a category."

UKG_READY = {
    "pay_run.type": mapped("type.id, labelled by type.display_name", U_RUN + "/type/properties/display_name"),
    "pay_run.status": mapped("status", U_RUN + "/status"),
    "pay_run.pay_date": mapped("pay_date", U_RUN + "/pay_date"),
    "pay_run.period.start": mapped("start_date", U_RUN + "/start_date"),
    "pay_run.period.end": mapped("end_date", U_RUN + "/end_date"),
    "pay_run.description": mapped("name", U_RUN + "/name"),
    "pay_run.pay_group": mapped("ein.id, labelled by ein_name", U_RUN + "/ein/properties/id"),
    "paycheck.type": mapped("type.id, labelled by type.display_name", U_CHK + "/type/properties/display_name"),
    "paycheck.status": mapped("status", U_CHK + "/status"),
    "paycheck.pay_date": mapped("pay_date", U_CHK + "/pay_date"),
    "paycheck.period.start": mapped("pay_period_start", U_CHK + "/pay_period_start"),
    "paycheck.period.end": mapped("pay_period_end", U_CHK + "/pay_period_end"),
    "paycheck.check_number": not_offered("Pay statements have no check number.", U_CHK),
    "paycheck.gross_pay": not_offered(UKG_NO_TOTALS, U_CHK),
    "paycheck.net_pay": not_offered(UKG_NO_TOTALS, U_CHK),
    "paycheck.void_date": not_offered("Pay statements have no void date.", U_CHK),
    "earnings.code": mapped("earning.code, labelled by earning.name", U_EARN + "/earning/properties/code"),
    "earnings.category": not_offered(UKG_NO_CATEGORY, U_EARN + "/type_name"),
    "earnings.hours": mapped("hours, converted from milliseconds", U_EARN + "/hours"),
    "earnings.rate": mapped("base_rate", U_EARN + "/base_rate"),
    "earnings.amount": mapped("ee_amount", U_EARN + "/ee_amount"),
    "taxes.code": mapped("company_tax.code, labelled by company_tax.name", U_TAX + "/company_tax/properties/code"),
    "taxes.employee_amount": mapped("ee_amount", U_TAX + "/ee_amount"),
    "taxes.employer_amount": mapped("er_amount", U_TAX + "/er_amount"),
    "taxes.employee_taxable_wages": mapped("ee_subject_wage", U_TAX + "/ee_subject_wage"),
    "taxes.employer_taxable_wages": mapped("er_subject_wage", U_TAX + "/er_subject_wage"),
    "deductions.code": mapped("deduction.code, labelled by deduction.name", U_DED + "/deduction/properties/code"),
    "deductions.category": not_offered(
        "type_name names how the line was applied, not the deduction's type.", U_DED + "/type_name"),
    "deductions.amount": mapped("ee_amount", U_DED + "/ee_amount"),
    "employer_contributions.code": mapped("deduction.code, labelled by deduction.name",
                                          U_DED + "/deduction/properties/code"),
    "employer_contributions.amount": mapped("er_amount", U_DED + "/er_amount"),
    "payments.method": mapped("type_name", U_PAY + "/type_name"),
    "payments.amount": mapped("ee_amount", U_PAY + "/ee_amount"),
    "payments.account_last4": not_offered("Payment lines have a method and an amount, but no account number.", U_PAY),
}

FIELD_MAP: dict[str, dict[str, FieldEntry]] = {
    "prismhr": PRISMHR,
    "isolved": ISOLVED,
    "ukg-ready": UKG_READY,
}
