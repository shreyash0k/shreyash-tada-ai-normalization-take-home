"""Where each canonical employee field comes from, per provider.

The field map is reference data for the coverage view; normalization does not
read it. Every entry cites evidence as ``<file>#<JSON pointer>`` into the
supplied contracts, and ``tests/test_field_map.py`` checks each pointer
resolves and each status agrees with the golden fixture outputs.

Statuses:

* ``mapped``: the adapter fills the field from ``source``.
* ``not_mapped_yet``: the provider offers the data at ``source``, but the
  adapter does not use it yet. ``reason`` says why.
* ``not_offered``: the provider has no such field. ``reason`` says what it
  has instead, and ``evidence`` points at the schema that lacks it.
"""
import re
from dataclasses import dataclass
from typing import Optional

MAPPED = "mapped"
NOT_MAPPED_YET = "not_mapped_yet"
NOT_OFFERED = "not_offered"
STATUSES = (MAPPED, NOT_MAPPED_YET, NOT_OFFERED)


@dataclass(frozen=True)
class FieldEntry:
    status: str
    evidence: str
    source: Optional[str] = None
    reason: Optional[str] = None
    sample_gap: Optional[str] = None


def mapped(source: str, evidence: str, sample_gap: Optional[str] = None) -> FieldEntry:
    return FieldEntry(MAPPED, evidence, source=source, sample_gap=sample_gap)


def not_mapped_yet(source: str, evidence: str, reason: str) -> FieldEntry:
    return FieldEntry(NOT_MAPPED_YET, evidence, source=source, reason=reason)


def not_offered(reason: str, evidence: str) -> FieldEntry:
    return FieldEntry(NOT_OFFERED, evidence, reason=reason)


SECTIONS = ("person", "contact", "employment", "job", "compensation")
LIST_KINDS = {
    "addresses": ("home", "mailing", "w2", "work"),
    "phones": ("home", "mobile", "work", "other"),
    "emails": ("personal", "work", "other", "unknown"),
}
SCALAR_FIELDS = {
    "person": ("first_name", "middle_name", "last_name", "preferred_name", "birth_date", "gender",
               "marital_status", "citizenship", "ethnicity", "ssn_last4"),
    "employment": ("status", "status_date", "employment_type", "hire_date", "original_hire_date",
                   "rehire_date", "termination_date", "seniority_date", "termination_reason",
                   "rehire_eligible", "flsa_exempt", "contractor_1099"),
    "job": ("title", "job_code", "department", "location", "division", "manager_employee_id",
            "job_start_date"),
    "compensation": ("pay_type", "pay_frequency", "rate", "rate_period", "hourly_rate",
                     "annual_amount", "per_period_amount", "standard_hours", "standard_hours_period",
                     "standard_work_day_hours", "effective_date"),
}


def canonical_fields() -> tuple[str, ...]:
    """Every row of the coverage grid, in display order."""
    rows = []
    for section in SECTIONS:
        if section == "contact":
            for list_name, kinds in LIST_KINDS.items():
                rows.extend(f"contact.{list_name}[{kind}]" for kind in kinds)
        else:
            rows.extend(f"{section}.{name}" for name in SCALAR_FIELDS[section])
    return tuple(rows)


_LIST_ROW = re.compile(r"^contact\.(addresses|phones|emails)\[(\w+)\]$")


def is_filled(employee: dict, field: str) -> bool:
    """True when a normalized employee (``to_dict`` form) has a value for a grid row."""
    match = _LIST_ROW.match(field)
    if match:
        return any(item.get("kind") == match[2] for item in employee["contact"][match[1]])
    section, name = field.split(".", 1)
    return employee[section][name] not in (None, [], {})


GENERATOR_GAP = "The synthetic generator does not set this field."

P = "contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas/"
I = "contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models."
U = "contracts/ukg-ready/reference-schemas.json#/schemas/"
I_EMP = I + "EmployeeModel/properties"
I_NAME = I + "EmployeeNameAddressModel/properties"
I_PERSONAL = I + "EmployeePersonalModel/properties"
U_EMP = U + "106/schema/properties"
U_DEMO = U + "134/schema/properties"
U_PAY = U + "159/schema/properties"
U_COMP = U + "122/schema/properties/compensations/items/properties"

PRISMHR = {
    "person.first_name": mapped("firstName", P + "Employee/properties/firstName"),
    "person.middle_name": mapped("middleInitial", P + "Employee/properties/middleInitial"),
    "person.last_name": mapped("lastName", P + "Employee/properties/lastName"),
    "person.preferred_name": mapped("preferredName", P + "Employee/properties/preferredName",
                                    sample_gap=GENERATOR_GAP),
    "person.birth_date": mapped("person.birthDate", P + "Person/properties/birthDate"),
    "person.gender": mapped("person.gender", P + "Person/properties/gender"),
    "person.marital_status": mapped("person.maritalStatus", P + "Person/properties/maritalStatus"),
    "person.citizenship": mapped("compensation.citizenshipStatus",
                                 P + "Compensation/properties/citizenshipStatus"),
    "person.ethnicity": mapped("person.ethnicCode", P + "Person/properties/ethnicCode"),
    "person.ssn_last4": mapped("compensation.ssn", P + "Compensation/properties/ssn"),
    "contact.addresses[home]": mapped("contactInformation.addressLine1 to zipSuffix",
                                      P + "ContactInformation/properties/addressLine1"),
    "contact.addresses[mailing]": mapped("client.addressLine1 to zipSuffix, else getAddressInfo altAddress",
                                         P + "Client/properties/addressLine1"),
    "contact.addresses[w2]": mapped("person.w2AddressLine1 to w2PostalCode",
                                    P + "Person/properties/w2AddressLine1", sample_gap=GENERATOR_GAP),
    "contact.addresses[work]": not_offered("The employee record has no work address.",
                                           P + "Employee/properties"),
    "contact.phones[home]": mapped("contactInformation.homePhone",
                                   P + "ContactInformation/properties/homePhone"),
    "contact.phones[mobile]": mapped("contactInformation.mobilePhone",
                                     P + "ContactInformation/properties/mobilePhone"),
    "contact.phones[work]": mapped("client.workPhone and client.workPhoneExt",
                                   P + "Client/properties/workPhone"),
    "contact.phones[other]": not_offered("Only home, mobile and work phone numbers.",
                                         P + "ContactInformation/properties"),
    "contact.emails[personal]": not_offered(
        "No email on getEmployee is labelled personal; personalEmail exists only on the Rehire and "
        "Census schemas.", P + "ContactInformation/properties"),
    "contact.emails[work]": mapped("client.workEmail", P + "Client/properties/workEmail"),
    "contact.emails[other]": not_mapped_yet(
        "client.benefitEmail", P + "Client/properties/benefitEmail",
        "An address used for benefits enrollment. It has no canonical kind yet and stays in unmapped."),
    "contact.emails[unknown]": mapped("contactInformation.emailAddress",
                                      P + "ContactInformation/properties/emailAddress"),
    "employment.status": mapped("client.statusClass", P + "Client/properties/statusClass"),
    "employment.status_date": mapped("client.statusDate", P + "Client/properties/statusDate"),
    "employment.employment_type": mapped("client.typeClass", P + "Client/properties/typeClass"),
    "employment.hire_date": mapped("client.lastHireDate", P + "Client/properties/lastHireDate"),
    "employment.original_hire_date": mapped("client.firstHireDate", P + "Client/properties/firstHireDate"),
    "employment.rehire_date": not_offered(
        "PrismHR keeps the first and the most recent hire dates (firstHireDate, lastHireDate) but no "
        "separate rehire date.", P + "Client/properties"),
    "employment.termination_date": not_offered(
        "No termination date field. For a terminated employee, statusDate is the date of the status "
        "change.", P + "Client/properties"),
    "employment.seniority_date": mapped("client.seniorityDate", P + "Client/properties/seniorityDate"),
    "employment.termination_reason": mapped("client.termReasonCode and termExplanation",
                                            P + "Client/properties/termReasonCode"),
    "employment.rehire_eligible": mapped("client.rehireOk", P + "Client/properties/rehireOk"),
    "employment.flsa_exempt": mapped("client.flsaExempt", P + "Client/properties/flsaExempt"),
    "employment.contractor_1099": mapped("client.employee1099", P + "Client/properties/employee1099"),
    "job.title": not_offered("getEmployee has a job code but no job title.", P + "Client/properties"),
    "job.job_code": mapped("client.jobCode", P + "Client/properties/jobCode"),
    "job.department": mapped("client.homeDepartment", P + "Client/properties/homeDepartment"),
    "job.location": mapped("client.homeLocation", P + "Client/properties/homeLocation"),
    "job.division": mapped("client.homeDivision", P + "Client/properties/homeDivision"),
    "job.manager_employee_id": mapped("client.manager", P + "Client/properties/manager"),
    "job.job_start_date": mapped("client.jobStartDate", P + "Client/properties/jobStartDate"),
    "compensation.pay_type": mapped("compensation.payMethod", P + "Compensation/properties/payMethod"),
    "compensation.pay_frequency": mapped("compensation.payPeriod", P + "Compensation/properties/payPeriod"),
    "compensation.rate": mapped("compensation.hourlyPayRate", P + "Compensation/properties/hourlyPayRate"),
    "compensation.rate_period": mapped("compensation.hourlyPayPeriod",
                                       P + "Compensation/properties/hourlyPayPeriod"),
    "compensation.hourly_rate": mapped("compensation.hourlyPay", P + "Compensation/properties/hourlyPay"),
    "compensation.annual_amount": mapped("compensation.annualPay", P + "Compensation/properties/annualPay"),
    "compensation.per_period_amount": mapped("compensation.salary", P + "Compensation/properties/salary"),
    "compensation.standard_hours": mapped("compensation.standardHours",
                                          P + "Compensation/properties/standardHours"),
    "compensation.standard_hours_period": mapped("compensation.standardHours (period from its description)",
                                                 P + "Compensation/properties/standardHours/description"),
    "compensation.standard_work_day_hours": not_offered(
        "No work-day length; only standard hours per pay period.", P + "Compensation/properties"),
    "compensation.effective_date": mapped("compensation.effectiveDate",
                                          P + "Compensation/properties/effectiveDate"),
}

ISOLVED = {
    "person.first_name": mapped("nameAddress.firstName", I_NAME + "/firstName"),
    "person.middle_name": mapped("nameAddress.middleName", I_NAME + "/middleName"),
    "person.last_name": mapped("nameAddress.lastName", I_NAME + "/lastName"),
    "person.preferred_name": mapped("nameAddress.preferredName", I_NAME + "/preferredName"),
    "person.birth_date": mapped("birthDate", I_EMP + "/birthDate"),
    "person.gender": mapped("gender", I_EMP + "/gender"),
    "person.marital_status": mapped("maritalStatus", I_EMP + "/maritalStatus"),
    "person.citizenship": mapped("citizenship", I_EMP + "/citizenship"),
    "person.ethnicity": mapped("ethnicOrigin", I_EMP + "/ethnicOrigin"),
    "person.ssn_last4": mapped("ssn", I_EMP + "/ssn"),
    "contact.addresses[home]": mapped("nameAddress.address1 to zipCode", I_NAME + "/address1"),
    "contact.addresses[mailing]": not_offered(
        "Only the home address and the W-2 override address.", I_EMP),
    "contact.addresses[w2]": mapped("overrideAddress", I_EMP + "/overrideAddress", sample_gap=GENERATOR_GAP),
    "contact.addresses[work]": not_offered("The employee record has no work address.", I_EMP),
    "contact.phones[home]": mapped("personal.homePhone", I_PERSONAL + "/homePhone"),
    "contact.phones[mobile]": mapped("personal.mobilePhone", I_PERSONAL + "/mobilePhone"),
    "contact.phones[work]": mapped("personal.officePhone", I_PERSONAL + "/officePhone"),
    "contact.phones[other]": not_mapped_yet(
        "personal.faxNumber", I_PERSONAL + "/faxNumber",
        "A fax number has no canonical phone kind yet. It stays in unmapped."),
    "contact.emails[personal]": mapped("personal.personalEmailAddress", I_PERSONAL + "/personalEmailAddress"),
    "contact.emails[work]": not_offered(
        "No email is labelled as the work address; emailAddress does not state its kind.",
        I_EMP + "/emailAddress"),
    "contact.emails[other]": not_offered("Only emailAddress and personalEmailAddress.", I_PERSONAL),
    "contact.emails[unknown]": mapped("emailAddress", I_EMP + "/emailAddress"),
    "employment.status": mapped("employmentStatus", I_EMP + "/employmentStatus"),
    "employment.status_date": mapped("statusDate", I_EMP + "/statusDate"),
    "employment.employment_type": mapped("employmentCategoryCode", I_EMP + "/employmentCategoryCode"),
    "employment.hire_date": mapped("hireDate", I_EMP + "/hireDate"),
    "employment.original_hire_date": mapped("originalHireDate", I_EMP + "/originalHireDate"),
    "employment.rehire_date": mapped("rehireDate", I_EMP + "/rehireDate"),
    "employment.termination_date": mapped("terminationDate", I_EMP + "/terminationDate"),
    "employment.seniority_date": not_offered("The employee record has no seniority date.", I_EMP),
    "employment.termination_reason": mapped("terminationReason", I_EMP + "/terminationReason"),
    "employment.rehire_eligible": mapped("eligibleForRehire", I_EMP + "/eligibleForRehire"),
    "employment.flsa_exempt": mapped("jobFLSAExempt", I_EMP + "/jobFLSAExempt"),
    "employment.contractor_1099": not_offered(
        "No contractor flag. payType can read 1099, but that is a pay type, not the flag "
        "(docs/DECISIONS.md, isolved pay type entry).", I_EMP + "/payType"),
    "job.title": mapped("jobTitle", I_EMP + "/jobTitle"),
    "job.job_code": mapped("jobCode", I_EMP + "/jobCode"),
    "job.department": mapped("organizations[] row titled Department",
                             I + "EmployeeOrganizationModel/properties"),
    "job.location": mapped("organizations[] row titled Location, else workLocation",
                           I_EMP + "/workLocation"),
    "job.division": not_mapped_yet(
        "organizations[] rows, titled by each client", I + "EmployeeOrganizationModel/properties",
        "Only the Department and Location rows are read. A client-titled division row stays in unmapped."),
    "job.manager_employee_id": mapped("assignedManager.id", I_EMP + "/assignedManager"),
    "job.job_start_date": mapped("jobEffectiveDate", I_EMP + "/jobEffectiveDate"),
    "compensation.pay_type": mapped("payType", I_EMP + "/payType"),
    "compensation.pay_frequency": mapped("payFrequency (label from payGroup)", I_EMP + "/payFrequency"),
    "compensation.rate": not_mapped_yet(
        "payRates[]", I_EMP + "/payRates", "Pay-rate rows are not mapped yet. They stay in unmapped."),
    "compensation.rate_period": not_mapped_yet(
        "payRates[]", I_EMP + "/payRates", "Pay-rate rows are not mapped yet. They stay in unmapped."),
    "compensation.hourly_rate": mapped("hourlyRate", I_EMP + "/hourlyRate"),
    "compensation.annual_amount": mapped("annualSalary", I_EMP + "/annualSalary"),
    "compensation.per_period_amount": mapped("perPaySalary", I_EMP + "/perPaySalary"),
    "compensation.standard_hours": mapped("normalHours", I_EMP + "/normalHours"),
    "compensation.standard_hours_period": mapped("normalHours (period from its description)",
                                                 I_EMP + "/normalHours/description"),
    "compensation.standard_work_day_hours": not_offered(
        "No work-day length; only normal hours per pay period.", I_EMP),
    "compensation.effective_date": mapped("salaryEffectiveDate", I_EMP + "/salaryEffectiveDate"),
}

UKG_READY = {
    "person.first_name": mapped("first_name", U_EMP + "/first_name"),
    "person.middle_name": mapped("middle_name", U_EMP + "/middle_name"),
    "person.last_name": mapped("last_name", U_EMP + "/last_name"),
    "person.preferred_name": mapped("nickname", U_EMP + "/nickname", sample_gap=GENERATOR_GAP),
    "person.birth_date": mapped("dates.birthday", U_EMP + "/dates/properties/birthday"),
    "person.gender": mapped("demographics.gender", U_DEMO + "/gender"),
    "person.marital_status": not_offered(
        "No marital status in the employee, demographics or pay-info responses.", U_DEMO),
    "person.citizenship": mapped("demographics.citizenship", U_DEMO + "/citizenship"),
    "person.ethnicity": mapped("demographics.ethnicity", U_DEMO + "/ethnicity"),
    "person.ssn_last4": mapped("social_security", U_EMP + "/social_security"),
    "contact.addresses[home]": mapped("address", U_EMP + "/address"),
    "contact.addresses[mailing]": mapped("mailing_address, unless use_separate_mailing_address is false",
                                         U_EMP + "/mailing_address"),
    "contact.addresses[w2]": not_offered("Only the home address and the mailing address.", U_EMP),
    "contact.addresses[work]": not_offered("The employee record has no work address.", U_EMP),
    "contact.phones[home]": mapped("phones.home_phone", U_EMP + "/phones/properties/home_phone"),
    "contact.phones[mobile]": mapped("phones.cell_phone", U_EMP + "/phones/properties/cell_phone"),
    "contact.phones[work]": mapped("phones.work_phone", U_EMP + "/phones/properties/work_phone",
                                   sample_gap=GENERATOR_GAP),
    "contact.phones[other]": not_offered("Only home, cell and work phone numbers.",
                                         U_EMP + "/phones/properties"),
    "contact.emails[personal]": not_offered(
        "Only primary_email and secondary_email; neither states its kind.", U_EMP),
    "contact.emails[work]": not_offered(
        "Only primary_email and secondary_email; neither states its kind.", U_EMP),
    "contact.emails[other]": mapped("secondary_email", U_EMP + "/secondary_email", sample_gap=GENERATOR_GAP),
    "contact.emails[unknown]": mapped("primary_email", U_EMP + "/primary_email"),
    "employment.status": mapped("status", U_EMP + "/status"),
    "employment.status_date": not_offered("No date for the current status.", U_EMP + "/dates/properties"),
    "employment.employment_type": mapped("pay_info.employee_type.id, named by the employee-types lookup",
                                         U_PAY + "/employee_type"),
    "employment.hire_date": mapped("dates.hired", U_EMP + "/dates/properties/hired"),
    "employment.original_hire_date": not_offered(
        "Only dates.hired and dates.re_hired; neither is labelled as the original hire date.",
        U_EMP + "/dates/properties"),
    "employment.rehire_date": mapped("dates.re_hired", U_EMP + "/dates/properties/re_hired"),
    "employment.termination_date": mapped("dates.terminated", U_EMP + "/dates/properties/terminated"),
    "employment.seniority_date": mapped("dates.seniority", U_EMP + "/dates/properties/seniority",
                                        sample_gap=GENERATOR_GAP),
    "employment.termination_reason": not_offered(
        "Termination details appear only in the write (PUT) schema, not in the read response.",
        U + "107/schema/properties/termination_details"),
    "employment.rehire_eligible": not_offered(
        "Rehire details appear only in the write (PUT) schema, not in the read response.",
        U + "107/schema/properties/rehire_details"),
    "employment.flsa_exempt": not_offered(
        "No FLSA field in the employee, demographics or pay-info responses.", U_PAY),
    "employment.contractor_1099": not_offered(
        "No contractor flag in the captured responses. tax-info's employee-tax-type has no documented "
        "values.", U + "166/schema/properties/employee-tax-type"),
    "job.title": not_mapped_yet(
        "pay_info.default_job.id, named by GET /v2/companies/{cid}/config/cost-center-jobs",
        U_PAY + "/default_job", "The bundle does not fetch the jobs configuration, so the name is not available."),
    "job.job_code": mapped("pay_info.default_job.id", U_PAY + "/default_job", sample_gap=GENERATOR_GAP),
    "job.department": not_mapped_yet(
        "cost_centers_info.defaults[].value.id", U_EMP + "/cost_centers_info",
        "Cost-centre levels (0 to 8) are defined by each company, so which level is the department is "
        "not known."),
    "job.location": not_mapped_yet(
        "cost_centers_info.defaults[].value.id", U_EMP + "/cost_centers_info",
        "Cost-centre levels (0 to 8) are defined by each company, so which level is the location is "
        "not known."),
    "job.division": not_mapped_yet(
        "cost_centers_info.defaults[].value.id", U_EMP + "/cost_centers_info",
        "Cost-centre levels (0 to 8) are defined by each company, so which level is the division is "
        "not known."),
    "job.manager_employee_id": mapped("managers[] with the lowest index: empl_ref.account_id",
                                      U_EMP + "/managers"),
    "job.job_start_date": not_mapped_yet(
        "pay_info.job_last_changed", U_PAY + "/job_last_changed",
        "The date the job last changed. Whether that is the current job's start date is not documented."),
    "compensation.pay_type": mapped("pay_info.pay_type.id, named by the pay-types lookup",
                                    U_PAY + "/pay_type"),
    "compensation.pay_frequency": not_mapped_yet(
        "compensation_history row num_pp_in_year", U_COMP + "/num_pp_in_year",
        "A count of pay periods per year, not a frequency code (docs/DECISIONS.md, UKG current pay entry)."),
    "compensation.rate": mapped("current compensation_history row: amount", U_COMP + "/amount"),
    "compensation.rate_period": mapped("current compensation_history row: amount_period",
                                       U_COMP + "/amount_period"),
    "compensation.hourly_rate": mapped("current compensation_history row: hourly_pay", U_COMP + "/hourly_pay"),
    "compensation.annual_amount": mapped("amount, when amount_period is YEAR", U_COMP + "/amount_period"),
    "compensation.per_period_amount": mapped("amount, when amount_period is PAY_PERIOD",
                                             U_COMP + "/amount_period"),
    "compensation.standard_hours": mapped("current compensation_history row: time (milliseconds)",
                                          U_COMP + "/time"),
    "compensation.standard_hours_period": mapped("current compensation_history row: time_period",
                                                 U_COMP + "/time_period"),
    "compensation.standard_work_day_hours": mapped("pay_info.standard_work_day (milliseconds)",
                                                   U_PAY + "/standard_work_day"),
    "compensation.effective_date": mapped("current compensation_history row: effective_from",
                                          U_COMP + "/effective_from"),
}

FIELD_MAP: dict[str, dict[str, FieldEntry]] = {
    "prismhr": PRISMHR,
    "isolved": ISOLVED,
    "ukg-ready": UKG_READY,
}
