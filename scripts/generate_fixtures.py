"""Seeded synthetic capture bundles plus their expected normalized output.

Usage::

    python scripts/generate_fixtures.py            # write tests/fixtures/**
    python scripts/generate_fixtures.py --check    # exit 1 if committed files differ
    python scripts/generate_fixtures.py --seed 7   # a different synthetic population

Every value is invented. Shapes follow the provider contracts under
``contracts/`` and the live field spellings recorded in ``docs/DECISIONS.md``.
Each bundle also carries injected edge cases (listed per builder below) so
the adapter tests can assert one issue code per case.
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from normalization.adapters import ADAPTERS  # noqa: E402
from normalization.bundle import parse_bundle  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_SEED = 20261015
CAPTURED_AT = "2026-10-15"

FIRST_NAMES = ["Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Harper", "Rowan",
               "Emerson", "Sage", "Dakota", "Reese", "Finley", "Skyler", "Tatum", "Blake"]
LAST_NAMES = ["Okafor", "Lindqvist", "Marchetti", "Haddad", "Nakamura", "Oyelaran", "Petrov",
              "Delgado", "Whitfield", "Castellanos", "Brennan", "Achterberg", "Ferreira", "Kowalczyk"]
STREETS = ["Maple Ave", "Birch Ct", "Cedar Ln", "Harbor Rd", "Summit Dr", "Willow Way", "Granite St"]
CITIES = [("Springfield", "IL", "62704"), ("Fairview", "OR", "97024"), ("Riverton", "UT", "84065"),
          ("Madison", "WI", "53703"), ("Franklin", "TN", "37064"), ("Georgetown", "TX", "78626"),
          ("Clayton", "MO", "63105"), ("Ashland", "VA", "23005")]


class Pool:
    """Deterministic pick helpers over a seeded ``random.Random``."""

    def __init__(self, seed: int, salt: str):
        self.rng = random.Random(f"{seed}:{salt}")
        self._used_names: set = set()

    def name(self):
        while True:
            first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
            if (first, last) not in self._used_names:
                self._used_names.add((first, last))
                return first, last

    def middle(self):
        return self.rng.choice("ABCDEJKLMRST")

    def address(self):
        city, state, zipcode = self.rng.choice(CITIES)
        return {"line1": f"{self.rng.randint(100, 9899)} {self.rng.choice(STREETS)}",
                "city": city, "state": state, "zip": zipcode}

    def date(self, start_year: int, end_year: int) -> str:
        year = self.rng.randint(start_year, end_year)
        month = self.rng.randint(1, 12)
        day = self.rng.randint(1, 28)
        return f"{year:04d}-{month:02d}-{day:02d}"

    def phone(self) -> str:
        return f"{self.rng.randint(201, 989)}{self.rng.randint(200, 999)}{self.rng.randint(1000, 9999)}"

    def ssn(self) -> str:
        return f"{self.rng.randint(100, 899):03d}-{self.rng.randint(10, 99):02d}-{self.rng.randint(1000, 9999):04d}"

    def money(self, low: int, high: int, places: int = 2) -> float:
        return round(self.rng.uniform(low, high), places)


def bundle(provider, request, responses):
    return {"bundle_version": 1, "provider": provider, "captured_at": CAPTURED_AT,
            "request": request, "responses": responses}


# --- PrismHR -----------------------------------------------------------------
# Injected cases: statusClass "Q" (undocumented_code), masked SSN (masked_value),
# invalid birthDate (invalid_date), prose citizenshipStatus (unmapped_label),
# live spellings employerId/autoPolicy/hawaiiMedWaiver/payPeriodsPerWeek
# (spec_live_mismatch), undocumented payPeriod codes.

PRISM_CLIENT_ID = "132"


def prism_employee(pool: Pool, index: int, status: str, type_class: str, pay_method: str,
                   employee_status: str = None, ssn: str = None, birth_date: str = None,
                   citizenship: str = "Z01", employee_1099: bool = False, manager: str = "",
                   rehire_ok: str = "", term_reason: str = ""):
    first, last = pool.name()
    home = pool.address()
    hire = pool.date(2015, 2025)
    hourly = pay_method == "H"
    rate = pool.money(16, 48, 4) if hourly else 0.0
    salary = pool.money(1800, 6500) if not hourly else 0.0
    employee_id = f"{first[0]}{index:05d}"
    return {
        "id": employee_id,
        "lastName": last, "firstName": first, "middleInitial": pool.middle(), "preferredName": "",
        "person": {
            "ethnicCode": pool.rng.choice(["*", "W", "B", "H"]),
            "birthDate": birth_date or pool.date(1960, 2002),
            "driverLicenseId": "", "cobraSSN": "",
            "employerId": ["5"],  # live spelling; spec says employerIds
            "cobraOnly": False, "geoCode": "260030036",
            "maritalStatus": pool.rng.choice(["S", "M", "D", "W", "C", "O"]),
            "marriedDate": "", "smoker": "N", "peoStartDate": hire,
            "handicapped": "N", "blind": "N", "veteran": "N", "vietnamVet": "N", "disabledVet": "N",
            "hrpCitizenshipCountry": None, "deceased": False,
            "gender": pool.rng.choice(["M", "F", "X", "D"]),
            "taxZipCode": "", "highlyCompensated": False, "keyEmployee": False,
            "overrideGeoCode": "", "overrideGeoEndDate": "", "nickname": "", "deceasedDate": "",
            "driverState": "", "driverLicenseExpireDate": "", "driverLicenseClass": "",
            "ohioFormC112": False, "unincorporatedResidence": False,
            "w2AddressLine1": "", "w2AddressLine2": "", "w2City": "", "w2State": "", "w2PostalCode": "",
            "w2ElecForm": True, "w2ElecFormDate": "", "legacyEmployeeId": "",
            "hispanic": False, "agricultureWorker": False, "otherProtectedVet": "N",
            "activeDutyBadgeVet": "N", "recentlySeparatedVet": "N", "serviceMedalVet": "N",
            "preferredLanguage": "ENG", "emergencyContact": [], "userId": "",
            "autoPolicy": [],  # live spelling; spec says autoPolicies
            "vehicleDetails": [], "personChecksum": str(pool.rng.randint(10_000_000, 99_999_999)),
        },
        "contactInformation": {
            "addressLine1": home["line1"], "addressLine2": "", "city": home["city"], "state": home["state"],
            "zipcode": home["zip"], "zipSuffix": "", "county": "", "schoolDistrict": "",
            "homePhone": pool.phone(), "mobilePhone": pool.phone() if index % 2 else "",
            "emailAddress": f"{first.lower()}.{last.lower()}@example.test",
        },
        "client": {
            "employeeStatus": employee_status or status, "statusClass": status, "statusDate": hire,
            "employeeType": {"F": "FT", "P": "PT"}.get(type_class, type_class), "typeClass": type_class,
            "typeDate": hire, "transferInfo": [], "property": [],
            "hawaiiMedWaiver": [],  # live spelling; spec says hawaiiMedWaivers
            "jobCode": pool.rng.choice(["OFFICE", "WHSE", "SALES", "TECH"]), "jobStartDate": hire,
            "firstHireDate": hire, "lastHireDate": hire,
            "flsaExempt": pay_method == "S", "cafeteriaPlan": [], "seniorityDate": hire,
            "officer": False, "workCompOfficer": False, "scorpOwner": False, "businessOwner": False,
            "termReasonCode": term_reason, "termExplanation": "Resigned" if term_reason else "",
            "lastStatusChangeDate": "", "lastJobChangeDate": "", "newHireReportDate": "",
            "employee1099": employee_1099, "clientEmployeeId": str(index), "clockNum": "",
            "primaryEmailSource": "", "benefitEmail": "", "rehireOk": rehire_ok, "returnDate": "",
            "workPhone": pool.phone() if index % 3 == 0 else "", "workPhoneExt": "12" if index % 3 == 0 else "",
            "probationDate": hire, "courtOrderMedical": False, "childSpouseSupport": False,
            "childSpouseArrears": False,
            "addressLine1": "", "addressLine2": "", "city": "", "state": "", "zip": "", "zipSuffix": "",
            "handbookMailDate": "", "handbookRecvDate": "", "unionCode": "", "unionDate": "",
            "subCostCenter": "", "electronicOnboard": False, "electronicOnboardDate": "", "reportsTo": "",
            "onboardInProgress": False, "backgroundTest": False, "backgroundTestDate": "",
            "workersCompExempt": None, "genderDesignation": "", "preferredPronoun": "",
            "clientChecksum": str(pool.rng.randint(10_000_000, 99_999_999)),
            "homeLocation": str(pool.rng.randint(1, 3)), "homeDivision": pool.rng.choice(["", "EAST", "WEST"]),
            "homeDepartment": str(pool.rng.choice([100, 200, 300])), "workShift": "", "projCostCenter": "",
            "workGroupCode": "", "benefitGroup": "1", "retirementBenefitGroup": "1",
            "workEmail": f"{first[0].lower()}{last.lower()}@client.test" if index % 2 == 0 else "",
            "electronic1095C": "N", "manager": manager, "selfIdDisabilityForm": "", "applicantId": "",
        },
        "compensation": {
            "ssn": ssn if ssn is not None else pool.ssn(),
            "payGroup": "WFRI", "payPeriod": pool.rng.choice(["W", "B", "S", "M"]), "payPeriodsPerWeek": "",
            "payPeriodInfo": [{"periodCode": c, "periodBase": "0.00"} for c in "WBSMA"],
            "defaultHours": "0.00", "payMethod": pay_method, "allocationTemplateId": "", "payAllocation": [],
            "standardHours": "40.00" if type_class == "F" else "24.00",
            "stateTax": [{"stateCode": home["state"], "nonResCertFiled": "", "filingStatus": "Single",
                          "primaryAllowance": "0", "secondaryAllowance": "", "exemptAmount": "",
                          "supplExemptAmount": "", "overrideType": "", "overrideAmount": "",
                          "reduceAddlWithholding": None, "fixedWithholding": None, "alternateCalc": "",
                          "stateW4Filed": "", "stateW4Year": "", "multipleJobs": False, "dependents": 0.0,
                          "otherIncome": 0.0, "deductions": 0.0, "nonResCertYear": ""}],
            "hourlyPay": f"{rate:.4f}", "salary": f"{salary:.2f}", "workShift": "", "paidThruDate": hire,
            "eicFileStatus": "", "fedFilingStatus": pool.rng.choice(["SS", "MJ", "H", "M", "S"]),
            "fedWithholdAllowance": "0", "fedOverrideType": "", "fedOverrideAmt": "", "fedTaxCalc": "",
            "fedMultipleJobs": False, "fedDependents": 0.0, "fedOtherIncome": 0.0, "fedDeductions": 0.0,
            "hourlyPayRate": f"{rate:.4f}" if hourly else f"{salary:.2f}",
            "hourlyPayPeriod": "H" if hourly else pool.rng.choice(["W", "B", "S", "M", "Y"]),
            "deliverCheckHome": False, "autoAcceptTimeSheet": False, "longPayTable": "", "longBasisDate": "",
            "annualPay": f"{(rate * 2080 if hourly else salary * 26):.2f}",
            "effectiveDate": pool.date(2025, 2026), "localTax": [], "lastChangePct": "0.00",
            "lastChangeAmt": "0.00", "lastPayDate": "", "quartile": "", "compaRatio": "", "benefitsBasePay": "",
            "perDiemPay": "", "taxCreditEmp": False, "autoPayCode": "", "altPayRate": [], "pensionStatus": "N",
            "profitSharing": "", "eeImage": [], "wagePlanCA": False, "perfReviewLastDate": "",
            "perfReviewNextDate": "", "i9imageAudit": [], "perfReviewLastRating": "", "compReviewNextDate": "",
            "perfReviewLastTitle": "", "fedW5Year": "", "fedW5Filed": False, "fedW4Filed": False,
            "fedW4Year": "", "lockIns": [], "formI9Filed": True, "formI9RenewDate": "", "notes": "",
            "ficaExempt": False, "benefitsPerHour": "", "perfAgreement": False, "payRate2": "", "payRate3": "",
            "payRate4": "", "payChangeLastDate": "", "overrideWorkGeocode": "", "familyMemberMI": "",
            "probationCodeMO": "", "electronicPayStub": True, "healthInsVT": False, "lastWorkedDate": "",
            "irsLockInDate": "", "nonResAlien": False, "alienRegExpDate": "", "benefitSalary": "",
            "citizenshipStatus": citizenship, "firstPayPeriodHours": "",
            "compensationChecksum": str(pool.rng.randint(10_000_000, 99_999_999)),
            "providerNotifiedOn": "", "alternateId": "", "w8Filed": False,
        },
        "directDeposit": None, "hsa": None, "employeeEvents": None, "health": None,
        "skillsAndEducation": None, "absenceJournalId": None, "benefitEnrollmentCompleted": None,
        "scheduledDeduction": None, "newHireQuestions": None, "enrollmentInProgress": None,
    }


def prism_response(records):
    return {"employee": records, "infoMessage": None, "updateMessage": None,
            "errorCode": "0", "errorMessage": "", "extension": None}


def build_prismhr(seed: int):
    pool = Pool(seed, "prismhr")
    manager = prism_employee(pool, 1, "A", "F", "S", rehire_ok="Y")
    records = [
        manager,
        prism_employee(pool, 2, "A", "F", "H", manager=manager["id"], ssn="***-**-****"),  # masked SSN
        prism_employee(pool, 3, "L", "P", "H", employee_status="LOA", manager=manager["id"]),
        prism_employee(pool, 4, "T", "F", "S", rehire_ok="N", term_reason="RES",
                       citizenship="A lawful permanent resident"),  # prose where spec says Z01-Z04
        prism_employee(pool, 5, "Q", "F", "C", employee_status="Q", manager=manager["id"]),  # undocumented
        prism_employee(pool, 6, "A", "P", "H", birth_date="2001-02-30"),  # invalid date
        prism_employee(pool, 7, "A", "F", "D", employee_1099=True, manager=manager["id"]),
    ]
    address_info = {
        records[0]["id"]: {
            "addressInfo": {
                "checksum": "528208", "homeGeoCode": "260030036",
                "homeAddress": {"unincorporatedResidence": False,
                                "addressLine1": records[0]["contactInformation"]["addressLine1"],
                                "addressLine2": "", "city": records[0]["contactInformation"]["city"],
                                "county": "", "stateAbbr": records[0]["contactInformation"]["state"],
                                "zipCode": records[0]["contactInformation"]["zipcode"], "zipSuffix": ""},
                "w2Address": {"addressLine1": "", "addressLine2": "", "city": "", "county": None,
                              "stateAbbr": "", "zipCode": "", "zipSuffix": None},
                "altAddress": {"internationalAddress": False, "mailAddressCountry": "USA",
                               "addressLine1": "PO Box 410", "addressLine2": "", "city": "Clayton",
                               "county": None, "stateAbbr": "MO", "zipCode": "63105", "zipSuffix": "1234"},
            },
            "errorCode": "0", "errorMessage": "", "extension": None,
        }
    }
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_employee": [prism_response(records[:4]), prism_response(records[4:])],
        "get_employee_list": {"employeeList": {"employeeId": [r["id"] for r in records]},
                              "errorCode": "0", "errorMessage": "", "extension": None},
        "get_address_info": address_info,
    })


# --- isolved -----------------------------------------------------------------
# Injected cases: employmentStatus "Leave of Absence" and gender "Non-binary"
# (unmapped_label), employmentCategoryCode FT/PT and integer payFrequency
# (undocumented_code), invalid salaryEffectiveDate (invalid_date), one record
# without the optional sub-objects, detail/personal/nameAddress overrides.

ISOLVED_CLIENT_ID, ISOLVED_LEGAL_ID = "4046", "5806"
ISOLVED_BASE = f"https://myisolved.example/rest/api/clients/{ISOLVED_CLIENT_ID}/legals/{ISOLVED_LEGAL_ID}/employees"


def isolved_links(employee_id):
    base = f"{ISOLVED_BASE}/{employee_id}"
    return [{"href": base, "rel": "self"}, {"href": f"{base}/checks", "rel": "Checks"},
            {"href": f"{base}/taxWithholding", "rel": "EmployeeTaxWithholding"}]


def isolved_employee(pool: Pool, employee_id: int, number: int, status: str, pay_type: str,
                     gender: str, category: str = "FT", marital=None, manager=None,
                     terminated: str = None, rehired: str = None, salary_effective: str = None,
                     ssn: str = "", sparse: bool = False):
    first, last = pool.name()
    home = pool.address()
    hire = pool.date(2016, 2025)
    hourly = pool.money(15, 60, 4)
    annual = round(hourly * 2080, 2)
    record = {
        "id": employee_id,
        "acaEmploymentStatus": "ACA Full Time" if category == "FT" else "ACA Variable",
        "annualSalary": annual if pay_type != "1099" else 0.0,
        "birthDate": f"{pool.date(1958, 2001)}T00:00:00",
        "emailAddress": f"{first.lower()}{number}@example.test",
        "employeeNumber": str(number),
        "employmentCategoryCode": category,
        "employmentCategoryEffectiveDate": f"{hire}T00:00:00",
        "employmentCategoryFullTimeEquivalent": None,
        "employmentStatus": status,
        "enableSelfService": False,
        "ethnicOrigin": pool.rng.choice(["White (Not Hispanic or Latino)", "Hispanic or Latino", "Asian"]),
        "gender": gender,
        "hireDate": f"{hire}T00:00:00",
        "hourlyRate": hourly,
        "i9Documents": {"i9Completed": False, "i9CompletedDate": None},
        "isRecentlySeparatedVeteran": False, "isRemoteWorker": False,
        "jobCode": str(pool.rng.choice([100, 200, 400, 450, 1000])),
        "jobEeoCategory": "Professionals",
        "jobEffectiveDate": f"{hire}T00:00:00",
        "jobFLSAExempt": pay_type == "Salary",
        "jobId": 92000 + number,
        "jobIsSeasonal": False, "jobIsUnion": False,
        "jobTitle": pool.rng.choice(["Analyst", "Technician", "Coordinator", "Driver", "Sub-Contractor"]),
        "legalCode": "BK422-1",
        "maritalStatus": marital,
        "militaryStatus": None,
        "nameAddress": {
            "id": 1245000 + number, "address1": home["line1"], "address2": None, "city": home["city"],
            "firstName": first, "lastName": last, "middleName": pool.middle(), "preferredName": None,
            "preferredPronouns": None, "prefix": None, "residentGeoCode": f"{home['state']}0350270",
            "state": home["state"], "suffix": None, "zipCode": home["zip"],
            "links": [{"href": None, "rel": "self"}, {"href": None, "method": "PUT", "rel": "EmployeeNameAddressUpdate"}],
        },
        "normalHours": 173.33 if category == "FT" else 86.67,
        "originalHireDate": f"{hire}T00:00:00",
        "payFrequency": 12,
        "payGroup": "Monthly",
        "payType": pay_type,
        "perPaySalary": round(annual / 12, 2) if pay_type != "1099" else 0.0,
        "personal": {
            "id": 1245000 + number, "faxNumber": None,
            "homePhone": pool.phone() if number % 2 else None, "mobilePhone": pool.phone(),
            "officePhone": None, "personalEmailAddress": None, "preferredPronouns": None,
            "links": [{"href": None, "rel": "self"}, {"href": None, "method": "PUT", "rel": "EmployeePersonalUpdate"}],
        },
        "previousPunchLabors": None, "protectedVeteran": False, "reciprocityRule": "",
        "salaryEffectiveDate": salary_effective or f"{hire}T00:00:00",
        "ssn": ssn,
        "statusDate": f"{terminated or hire}T00:00:00",
        "timecardPunchStatusDate": None, "timecardPunchStatusIsIn": None, "timeclockId": None,
        "tobaccoUse": False, "uniqueId": None, "veteranStatusNotSpecified": False,
        "workLocation": "UT1", "workLocationDashDescription": "UT1 - SALT LAKE CITY, UT",
        "links": isolved_links(employee_id),
    }
    if manager is not None:
        record["assignedManager"] = {"id": manager["id"], "employeeName": f"{manager['nameAddress']['firstName']} "
                                     f"{manager['nameAddress']['lastName']}", "employeeNumber": manager["employeeNumber"],
                                     "jobTitle": manager["jobTitle"], "legalId": int(ISOLVED_LEGAL_ID)}
    if terminated:
        record["terminationDate"] = f"{terminated}T00:00:00"
        record["terminationReason"] = "Retirement"
        record["terminationType"] = "Voluntary Termination"
        record["eligibleForRehire"] = False
    if rehired:
        record["rehireDate"] = f"{rehired}T00:00:00"
    if sparse:
        for key in ("acaEmploymentStatus", "employmentCategoryFullTimeEquivalent", "i9Documents",
                    "militaryStatus", "previousPunchLabors", "timecardPunchStatusDate",
                    "timecardPunchStatusIsIn", "timeclockId", "uniqueId", "reciprocityRule"):
            record.pop(key, None)
    else:
        record["citizenship"] = "Citizen of the United States"
        record["isManager"] = manager is None
        record["isSupervisor"] = manager is None
    return record


def isolved_page(results, page, total_pages, total_items):
    return {
        "nextPageUrl": f"{ISOLVED_BASE}?pageSize=3&page={page + 1}" if page < total_pages else None,
        "previousPageUrl": f"{ISOLVED_BASE}?pageSize=3&page={page - 1}" if page > 1 else None,
        "results": results, "totalItems": total_items, "totalPages": float(total_pages),
    }


def build_isolved(seed: int):
    pool = Pool(seed, "isolved")
    manager = isolved_employee(pool, 859201, 1, "Active", "Salary", "Male", marital="Married")
    records = [
        manager,
        isolved_employee(pool, 859202, 2, "Active", "Hourly", "Female", marital="Single", manager=manager),
        isolved_employee(pool, 859203, 3, "Terminated", "Salary", "Female", manager=manager,
                         terminated="2024-03-29", ssn=pool.ssn()),
        isolved_employee(pool, 859204, 4, "Leave of Absence", "Hourly", "Non-binary",  # off-allowlist labels
                         category="PT", manager=manager),
        isolved_employee(pool, 859205, 5, "Active", "1099", "Male", category="PT", manager=manager,
                         rehired="2023-01-09", salary_effective="not-a-date"),  # invalid date
        isolved_employee(pool, 859206, 6, "Active", "Hourly", "Female", sparse=True),  # live-absent fields
    ]
    detail = dict(records[0])
    detail["organizations"] = [
        {"id": -1, "displayOrder": 1, "organizationId": 9943, "title": "Location", "value": "10",
         "valueDescription": "Main Yard"},
        {"id": -2, "displayOrder": 2, "organizationId": 9944, "title": "Department", "value": "100",
         "valueDescription": "Executives"},
    ]
    detail["payRates"] = []
    detail["taxes"] = {
        "federal": {"id": 1556268, "additionalAmount": None, "filingStatus": "FDM", "isBlocked": False,
                    "multipleJobsOrSpouseWorks": False, "primaryExemptions": 0, "taxCategoryId": "FEDWT",
                    "taxState": "", "links": []},
        "nonResidentCity": None, "nonResidentState": None, "residentCity": None,
        "residentState": {"id": 1556269, "filingStatus": "UTM", "isBlocked": False, "primaryExemptions": 0,
                          "taxCategoryId": "STATEWT", "taxDescription": "UTAH WH", "taxState": "UT", "links": []},
    }
    personal = dict(records[1]["personal"])
    personal["officePhone"] = pool.phone()
    personal["personalEmailAddress"] = "personal.two@example.test"
    name_address = {k: v for k, v in records[1]["nameAddress"].items() if k != "links"}
    name_address["id"] = 0
    name_address["preferredName"] = "Jo"
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": [isolved_page(records[:3], 1, 2, len(records)), isolved_page(records[3:], 2, 2, len(records))],
        "employee_detail": {str(records[0]["id"]): detail},
        "personal": {str(records[1]["id"]): personal},
        "name_address": {str(records[1]["id"]): name_address},
    })


# --- UKG Ready ---------------------------------------------------------------
# Injected cases: missing demographics (missing_section), 1900-12-31 zero row
# with num_pp_in_year 0 (out_of_schema_value) plus a future-dated row, two rows
# sharing effective_from (multiple_current_rates), eeo4_* "UNKNOWN"
# (out_of_schema_value), employee_type id absent from the lookup
# (missing_lookup), status "Suspended" (unmapped_label), invalid seniority
# date (invalid_date), ein_name and _links.country-fields on the detail
# (spec_live_mismatch).

UKG_COMPANY_ID = "33704016"
UKG_BASE = f"https://secure.example-ukg.test/ta/rest/v2/companies/{UKG_COMPANY_ID}"
UKG_EMPLOYEE_TYPES = [(35330176, "FT Non-Exempt"), (35330178, "FT Exempt"), (35330177, "PT Hourly"),
                      (35330181, "Temp"), (35330179, "Consultant")]
UKG_PAY_TYPES = [(35043008, "Hourly"), (35043009, "Salaried")]


def ukg_links(aid, detail=False):
    base = f"{UKG_BASE}/employees/{aid}"
    links = {"self": base}
    if detail:
        links["country-fields"] = f"{base}/country-fields"  # live-only link
    links.update({"demographics": f"{base}/demographics", "badges": f"{base}/badges",
                  "pay-info": f"{base}/pay-info", "profiles": f"{base}/profiles"})
    return links


def ukg_employee(pool: Pool, aid: int, number: int, status: str, terminated: str = None,
                 rehired: str = None, seniority: str = None, managers=None, mailing: bool = False):
    first, last = pool.name()
    home = pool.address()
    hire = pool.date(2016, 2025)
    dates = {"hired": hire, "started": hire}
    if rehired:
        dates["re_hired"] = rehired
    if terminated:
        dates["terminated"] = terminated
    if seniority:
        dates["seniority"] = seniority
    listed = {
        "id": aid, "employee_id": str(number), "username": f"{first[0]}{last}".lower(),
        "first_name": first, "last_name": last, "primary_account_id": aid, "ein_name": "Primary EIN",
        "_links": ukg_links(aid), "status": status, "dates": dict(dates),
    }
    detail = {
        "id": aid, "employee_id": str(number), "username": listed["username"],
        "first_name": first, "last_name": last, "primary_account_id": aid,
        "ein_name": "Primary EIN",  # live-only on the detail response
        "_links": ukg_links(aid, detail=True),
        "photo_href": f"https://secure.example-ukg.test/ta/fs?ticket=synthetic-{aid}",
        "isPhotoUploaded": False, "middle_name": pool.middle(), "status": status, "locked": False,
        "force_change_password": False, "social_security": pool.ssn(),
        "first_screen": {"id": "SCREEN:101"},
        "address": {"address_line_1": home["line1"], "country": "USA", "city": home["city"],
                    "state": home["state"], "zip": home["zip"], "state_code": home["state"]},
        "use_separate_mailing_address": mailing,
        "timezone": "America/Chicago",
        "dates": dict(dates, birthday=pool.date(1960, 2002)),
        "ein": {"id": 35419520},
        "phones": {"cell_phone": pool.phone(), "home_phone": pool.phone() if number % 2 else "",
                   "work_phone": "", "preferred_phone": "CELL" if number % 2 else "HOME"},
        "primary_email": f"{listed['username']}@example.test",
        "add_to_new_hire_export": True,
        "hardware_settings": {"in_touch": {"security_level": "EMPLOYEE", "pin": 0}},
        "managed_cost_centers_enabled": False,
        "national_id_numbers": [{"type": "SSN", "value": None, "primary": True}],
    }
    detail["national_id_numbers"][0]["value"] = detail["social_security"]
    if mailing:
        detail["mailing_address"] = {"address_line_1": "PO Box 77", "country": "USA", "city": home["city"],
                                     "state": home["state"], "zip": home["zip"], "state_code": home["state"]}
    if managers:
        detail["managers"] = [{"index": i, "empl_ref": {"account_id": m}} for i, m in enumerate(managers)]
    return listed, detail


def ukg_demographics(pool: Pool, gender: str):
    return {"citizenship": pool.rng.choice(["US_CITIZEN", "PERMANENT_RESIDENT", "ALIEN_WITH_WORK_PERMIT"]),
            "ethnicity": pool.rng.choice(["WHITE", "ASIAN", "HISPANIC_OR_LATINO", "TWO_OR_MORE_RACES"]),
            "gender": gender}


def ukg_pay_info(employee_type: int, pay_type: int, eeo4: str = None, work_day_ms: int = 28_800_000):
    info = {"standard_work_day": work_day_ms, "employee_type": {"id": employee_type}, "pay_type": {"id": pay_type}}
    if eeo4:
        info["eeo4_classification"] = eeo4
        info["eeo4_function"] = eeo4
    info["ttoc"] = []
    info["payroll_classification"] = "REGULAR"
    return info


def ukg_comp(aid: int, effective: str, amount: float, hourly: float, amount_period: str,
             num_pp: int = 26, time_ms: int = 7_488_000_000, time_period: str = "YEAR"):
    row_id = int(effective.replace("-", "") + str(aid))
    return {"id": row_id, "employee": {"account_id": aid}, "effective_from": effective, "amount": amount,
            "hourly_pay": hourly, "amount_period": amount_period, "time": time_ms, "time_period": time_period,
            "num_pp_in_year": num_pp, "_links": {"self": f"{UKG_BASE}/compensation/history/{row_id}"},
            "currency": "USD"}


def build_ukg(seed: int):
    pool = Pool(seed, "ukg-ready")
    ids = [12935181566 + i for i in range(6)]
    people = [
        ukg_employee(pool, ids[0], 1, "Active", managers=None),
        ukg_employee(pool, ids[1], 2, "Active", managers=[ids[0]], mailing=True),
        ukg_employee(pool, ids[2], 3, "Terminated", terminated="2024-06-28", managers=[ids[0]]),
        ukg_employee(pool, ids[3], 4, "Active", rehired="2022-02-14", managers=[ids[1], ids[0]]),
        ukg_employee(pool, ids[4], 5, "Suspended", managers=[ids[0]]),  # off-allowlist status
        ukg_employee(pool, ids[5], 6, "Active", seniority="2020-13-01", managers=[ids[1]]),  # invalid date
    ]
    salaried = pool.money(60_000, 140_000)
    hourly_rate = pool.money(18, 45, 4)
    responses = {
        "employees": {"employees": [listed for listed, _ in people]},
        "employee": {str(aid): detail for aid, (_, detail) in zip(ids, people)},
        "demographics": {
            str(ids[0]): ukg_demographics(pool, "MALE"),
            str(ids[1]): ukg_demographics(pool, "FEMALE"),
            str(ids[2]): ukg_demographics(pool, "FEMALE"),
            # ids[3] has no demographics response -> missing_section
            str(ids[4]): ukg_demographics(pool, "UNDEFINED"),
            str(ids[5]): ukg_demographics(pool, "MALE"),
        },
        "pay_info": {
            str(ids[0]): ukg_pay_info(35330178, 35043009, work_day_ms=0),
            str(ids[1]): ukg_pay_info(35330176, 35043008, eeo4="UNKNOWN"),  # out_of_schema_value
            str(ids[2]): ukg_pay_info(35330178, 35043009),
            str(ids[3]): ukg_pay_info(35330177, 35043008),
            str(ids[4]): ukg_pay_info(99999999, 35043008),  # id absent from lookup -> missing_lookup
            str(ids[5]): ukg_pay_info(35330179, 35043009, eeo4="PROFESSIONALS"),
        },
        "compensation_history": {
            str(ids[0]): {"compensations": [
                ukg_comp(ids[0], "1900-12-31", 0.0, 0.0, "HOUR", num_pp=0),  # placeholder zero row
                ukg_comp(ids[0], "2026-01-01", salaried, round(salaried / 2080, 4), "YEAR"),
                ukg_comp(ids[0], "2027-01-01", round(salaried * 1.05, 2), round(salaried * 1.05 / 2080, 4), "YEAR"),
            ]},
            str(ids[1]): {"compensations": [
                ukg_comp(ids[1], "2025-07-01", hourly_rate, hourly_rate, "HOUR", time_ms=288_000_000, time_period="PAY_PERIOD"),
            ]},
            str(ids[2]): {"compensations": [
                ukg_comp(ids[2], "2023-01-01", 72_000.0, 34.6154, "YEAR"),
            ]},
            str(ids[3]): {"compensations": [
                ukg_comp(ids[3], "2025-01-01", 2_400.0, 30.0, "PAY_PERIOD", time_ms=288_000_000, time_period="PAY_PERIOD"),
                ukg_comp(ids[3], "2025-01-01", 2_500.0, 31.25, "PAY_PERIOD", time_ms=288_000_000, time_period="PAY_PERIOD"),  # tie
            ]},
            str(ids[4]): {"compensations": [
                ukg_comp(ids[4], "2024-05-06", round(hourly_rate + 2, 4), round(hourly_rate + 2, 4), "HOUR"),
            ]},
            str(ids[5]): {"compensations": []},
        },
        "lookup_employee_types": {"items": [{"id": i, "name": n} for i, n in UKG_EMPLOYEE_TYPES]},
        "lookup_pay_types": {"items": [{"id": i, "name": n} for i, n in UKG_PAY_TYPES]},
        "lookup_eins": {"items": [{"id": 35419520, "ein_name": "Primary EIN", "ein_tax_id": "12-3456789",
                                   "ein_country_id": "USA"}]},
    }
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, responses)


BUILDERS = {"prismhr": build_prismhr, "isolved": build_isolved, "ukg-ready": build_ukg}


def dumps(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def generate(seed: int = DEFAULT_SEED) -> dict:
    """Return {relative path: file text} for every fixture file."""
    files = {}
    for provider, builder in BUILDERS.items():
        raw = builder(seed)
        files[f"{provider}/employee-bundle.json"] = dumps(raw)
        output = ADAPTERS[provider].normalize_employees(parse_bundle(raw))
        files[f"expected/{provider}-employees.json"] = dumps(output.to_dict())
    return files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--check", action="store_true", help="compare with committed files instead of writing")
    args = parser.parse_args(argv)
    files = generate(args.seed)
    stale = []
    for relative, content in files.items():
        path = FIXTURES / relative
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("stale fixtures: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
