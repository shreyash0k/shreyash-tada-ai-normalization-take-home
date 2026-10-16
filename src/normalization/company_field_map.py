"""Where each canonical company field comes from, per provider.

Reference data for the coverage view, in the same form as ``field_map``:
statuses, source paths and ``<file>#<JSON pointer>`` evidence.
``tests/test_company_field_map.py`` checks each pointer resolves and each
status agrees with the golden company outputs.

Row names start with the record or list (``company``, ``contact``,
``tax_ids``, and so on). Address, phone, email and website sit under
``contact`` even though they are top-level on the company record.
"""
from .field_map import FieldEntry, mapped, not_offered

SECTION_FIELDS = {
    "company": ("company.name", "company.legal_name", "company.ein", "company.status", "company.status_date",
                "company.entity_type", "company.service_type", "company.naics_code", "company.sic_code",
                "company.parent"),
    "contact": ("contact.address", "contact.phone", "contact.email", "contact.website"),
    "tax_ids": ("tax_ids.tax_id", "tax_ids.name", "tax_ids.country"),
    "work_locations": ("work_locations.code", "work_locations.address", "work_locations.active",
                       "work_locations.end_date", "work_locations.remote"),
    "pay_groups": ("pay_groups.code", "pay_groups.frequency", "pay_groups.active",
                   "pay_groups.effective.start", "pay_groups.effective.end"),
}

PROFILE_FIELDS = {"company", "contact"}


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
    """True when the company profile or any list entry has a value for a grid row."""
    head, _, rest = field.partition(".")
    company = output["company"]
    records = [company] if head in PROFILE_FIELDS else company[head]
    return any(_has(record, rest) for record in records)


PRISM = "contracts/prismhr/openapi/prismhr-2025.09.openapi.json#/components/schemas"
CLIENT = PRISM + "/ClientMaster/properties"
LOC = PRISM + "/ClientCodes-LocationCode/properties"
GROUPS = PRISM + "/PayGroups/properties"
SCHED = PRISM + "/ClientPayrollSchedule/properties"

PRISM_NO_PARENT = ("benefitParentClient is a parent for benefits only, and controlGroupCompany is the master "
                   "of a 401(k) group. Neither is the company's parent.")
PRISM_ONE_EIN = "The client record has one federal ID, with no name and no country."
PRISM_GROUP_DATES = "A pay group from client codes has a code and a description, but no active flag and no dates."

PRISMHR = {
    "company.name": mapped("clientName", CLIENT + "/clientName"),
    "company.legal_name": mapped("legalName", CLIENT + "/legalName"),
    "company.ein": mapped("federalIdNumber, when it is not masked", CLIENT + "/federalIdNumber"),
    "company.status": mapped("statusClass", CLIENT + "/statusClass"),
    "company.status_date": mapped("statusDate", CLIENT + "/statusDate"),
    "company.entity_type": mapped("corporationType, labelled from the spec", CLIENT + "/corporationType"),
    "company.service_type": mapped("serviceType, labelled from the spec", CLIENT + "/serviceType"),
    "company.naics_code": mapped("naicsCode", CLIENT + "/naicsCode"),
    "company.sic_code": mapped("sicCode", CLIENT + "/sicCode"),
    "company.parent": not_offered(PRISM_NO_PARENT, CLIENT + "/benefitParentClient"),
    "contact.address": mapped("addressLine1, addressLine2, city, stateCode, zipCode", CLIENT + "/addressLine1"),
    "contact.phone": mapped("mainPhone", CLIENT + "/mainPhone"),
    "contact.email": mapped("emailAddress", CLIENT + "/emailAddress"),
    "contact.website": mapped("websiteUrl", CLIENT + "/websiteUrl"),
    "tax_ids.tax_id": mapped("federalIdNumber, when it is not masked", CLIENT + "/federalIdNumber"),
    "tax_ids.name": not_offered(PRISM_ONE_EIN, CLIENT + "/federalIdNumber"),
    "tax_ids.country": not_offered(PRISM_ONE_EIN, CLIENT + "/federalIdNumber"),
    "work_locations.code": mapped("id, labelled by locationName", LOC + "/id"),
    "work_locations.address": mapped("addressLine1, addressLine2, city, state, zipCode", LOC + "/addressLine1"),
    "work_locations.active": mapped("locationObsolete, inverted", LOC + "/locationObsolete"),
    "work_locations.end_date": mapped("obsoleteDate", LOC + "/obsoleteDate"),
    # remoteLocation is documented on LocationCode. The client-codes location schema leaves it out.
    "work_locations.remote": mapped("remoteLocation", PRISM + "/LocationCode/properties/remoteLocation"),
    "pay_groups.code": mapped("payGroupCode, labelled by description", GROUPS + "/payGroupCode"),
    "pay_groups.frequency": mapped("clientPayrollSchedule.payPeriod, labelled by payPeriodDesc",
                                   SCHED + "/payPeriod"),
    "pay_groups.active": not_offered(PRISM_GROUP_DATES, GROUPS),
    "pay_groups.effective.start": not_offered(PRISM_GROUP_DATES, GROUPS),
    "pay_groups.effective.end": not_offered(PRISM_GROUP_DATES, GROUPS),
}

ISO = "contracts/isolved/openapi/isolved-v6.swagger.json#/definitions/AOS.PayrollOffice.RestAPI.Models"
LEGAL = ISO + ".LegalModel/properties"
ADDR = ISO + ".ClientAddressModel/properties"
WLOC = ISO + ".LegalWorkLocationModel/properties"
PGROUP = ISO + ".PayGroupModel/properties"
ICLIENT = ISO + ".ClientModel/properties"

ISOLVED_NO_DBA = "The live legal never sends dbaName, and the fixture follows it."
ISOLVED_NO_NAICS = "The live legal never sends naicsCode, and the fixture follows it."
ISOLVED_ONE_EIN = "The legal record has one federal EIN, with no name and no country."
ISOLVED_NO_SERVICE = "services lists the products the legal buys, each with dates. It is not one service type."
ISOLVED_GROUP_DATES = "A pay group has an inactive flag, but no effective dates."

ISOLVED = {
    "company.name": mapped("dbaName", LEGAL + "/dbaName", sample_gap=ISOLVED_NO_DBA),
    "company.legal_name": mapped("legalName", LEGAL + "/legalName"),
    "company.ein": mapped("federalEIN", LEGAL + "/federalEIN"),
    "company.status": mapped("status", LEGAL + "/status"),
    "company.status_date": not_offered("The legal record has a status, but no status date.", LEGAL + "/status"),
    "company.entity_type": not_offered("The legal record has no entity type.", LEGAL),
    "company.service_type": not_offered(ISOLVED_NO_SERVICE, LEGAL + "/services"),
    "company.naics_code": mapped("naicsCode", LEGAL + "/naicsCode", sample_gap=ISOLVED_NO_NAICS),
    "company.sic_code": not_offered("The legal record has no SIC code.", LEGAL),
    "company.parent": mapped("client.id, labelled by client.clientName", ICLIENT + "/id"),
    "contact.address": mapped("legalAddress.streetAddress1, streetAddress2, city, state, zipCode",
                              ADDR + "/streetAddress1"),
    "contact.phone": mapped("legalAddress.phoneNumber", ADDR + "/phoneNumber"),
    "contact.email": not_offered("The legal address has a phone number, but no email.", ADDR),
    "contact.website": not_offered("The legal record has no website.", LEGAL),
    "tax_ids.tax_id": mapped("federalEIN", LEGAL + "/federalEIN"),
    "tax_ids.name": not_offered(ISOLVED_ONE_EIN, LEGAL + "/federalEIN"),
    "tax_ids.country": not_offered(ISOLVED_ONE_EIN, LEGAL + "/federalEIN"),
    "work_locations.code": mapped("workLocationCode, labelled by workLocationDescription",
                                  WLOC + "/workLocationCode"),
    "work_locations.address": mapped("address1, address2, city, state, zipCode", WLOC + "/address1"),
    "work_locations.active": mapped("isInactive, inverted", WLOC + "/isInactive"),
    "work_locations.end_date": not_offered("A work location has an inactive flag, but no end date.", WLOC),
    "work_locations.remote": mapped("isRemoteWorkersOnly", WLOC + "/isRemoteWorkersOnly"),
    "pay_groups.code": mapped("id, labelled by payGroupName", PGROUP + "/id"),
    "pay_groups.frequency": mapped("payFrequency", PGROUP + "/payFrequency"),
    "pay_groups.active": mapped("isInactive, inverted", PGROUP + "/isInactive"),
    "pay_groups.effective.start": not_offered(ISOLVED_GROUP_DATES, PGROUP),
    "pay_groups.effective.end": not_offered(ISOLVED_GROUP_DATES, PGROUP),
}

UKG = "contracts/ukg-ready/reference-schemas.json#/schemas"
EIN = UKG + "/249/schema/properties/items/items/properties"
PROFILE = UKG + "/273/schema/properties/items/items/properties"
COST_CENTERS = UKG + "/106/schema/properties/cost_centers_info"

UKG_NO_PROFILE = ("UKG Ready has no company profile endpoint. The EIN lookup has a tax id, a name and a "
                  "country, and nothing else.")
UKG_NO_LOCATION = "UKG Ready has no work location records. Cost centres are trees each company defines, not locations."

UKG_READY = {
    "company.name": not_offered(UKG_NO_PROFILE, EIN),
    "company.legal_name": not_offered(UKG_NO_PROFILE, EIN),
    "company.ein": mapped("ein_tax_id, when the lookup lists one EIN", EIN + "/ein_tax_id"),
    "company.status": not_offered(UKG_NO_PROFILE, EIN),
    "company.status_date": not_offered(UKG_NO_PROFILE, EIN),
    "company.entity_type": not_offered(UKG_NO_PROFILE, EIN),
    "company.service_type": not_offered(UKG_NO_PROFILE, EIN),
    "company.naics_code": not_offered(UKG_NO_PROFILE, EIN),
    "company.sic_code": not_offered(UKG_NO_PROFILE, EIN),
    "company.parent": not_offered(UKG_NO_PROFILE, EIN),
    "contact.address": not_offered(UKG_NO_PROFILE, EIN),
    "contact.phone": not_offered(UKG_NO_PROFILE, EIN),
    "contact.email": not_offered(UKG_NO_PROFILE, EIN),
    "contact.website": not_offered(UKG_NO_PROFILE, EIN),
    "tax_ids.tax_id": mapped("ein_tax_id", EIN + "/ein_tax_id"),
    "tax_ids.name": mapped("ein_name", EIN + "/ein_name"),
    "tax_ids.country": mapped("ein_country_id", EIN + "/ein_country_id"),
    "work_locations.code": not_offered(UKG_NO_LOCATION, COST_CENTERS),
    "work_locations.address": not_offered(UKG_NO_LOCATION, COST_CENTERS),
    "work_locations.active": not_offered(UKG_NO_LOCATION, COST_CENTERS),
    "work_locations.end_date": not_offered(UKG_NO_LOCATION, COST_CENTERS),
    "work_locations.remote": not_offered(UKG_NO_LOCATION, COST_CENTERS),
    "pay_groups.code": mapped("id, labelled by name", PROFILE + "/name"),
    "pay_groups.frequency": mapped("period_type.type; every_n_weeks reads params.num_weeks",
                                   PROFILE + "/period_type/properties/type"),
    "pay_groups.active": mapped("active", PROFILE + "/active"),
    "pay_groups.effective.start": mapped("effective_from", PROFILE + "/effective_from"),
    "pay_groups.effective.end": mapped("effective_to", PROFILE + "/effective_to"),
}

FIELD_MAP: dict[str, dict[str, FieldEntry]] = {
    "prismhr": PRISMHR,
    "isolved": ISOLVED,
    "ukg-ready": UKG_READY,
}
