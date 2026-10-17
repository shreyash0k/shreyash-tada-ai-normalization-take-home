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

BANKS = ["First Example Bank", "Harbor Sample Credit Union", "Granite Test Savings", "Summit Demo Bank N.A."]

FIRST_NAMES = ["Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Harper", "Rowan",
               "Emerson", "Sage", "Dakota", "Reese", "Finley", "Skyler", "Tatum", "Blake"]
LAST_NAMES = ["Okafor", "Lindqvist", "Marchetti", "Haddad", "Nakamura", "Oyelaran", "Petrov",
              "Delgado", "Whitfield", "Castellanos", "Brennan", "Achterberg", "Ferreira", "Kowalczyk"]
# One person belongs to one company. Scranton, Stamford and Utica each have eight.
SCRANTON_ROSTER = (
    ("Michael", "Scott"),
    ("Dwight", "Schrute"),
    ("Jim", "Halpert"),
    ("Pam", "Beesly"),
    ("Angela", "Martin"),
    ("Kevin", "Malone"),
    ("Oscar", "Martinez"),
    ("Stanley", "Hudson"),
)
STAMFORD_ROSTER = (
    ("Phyllis", "Vance"),
    ("Creed", "Bratton"),
    ("Meredith", "Palmer"),
    ("Ryan", "Howard"),
    ("Kelly", "Kapoor"),
    ("Toby", "Flenderson"),
    ("Darryl", "Philbin"),
    ("Andy", "Bernard"),
)
UTICA_ROSTER = (
    ("Erin", "Hannon"),
    ("Gabe", "Lewis"),
    ("Holly", "Flax"),
    ("Jan", "Levinson"),
    ("David", "Wallace"),
    ("Karen", "Filippelli"),
    ("Roy", "Anderson"),
    ("Charles", "Miner"),
)
SCRANTON = {"line1": "1725 Slough Avenue", "city": "Scranton", "state": "PA", "zip": "18503"}
STAMFORD = {"line1": "400 Canal Street", "city": "Stamford", "state": "CT", "zip": "06902"}
STREETS = ["Maple Ave", "Birch Ct", "Cedar Ln", "Harbor Rd", "Summit Dr", "Willow Way", "Granite St"]
CITIES = [("Springfield", "IL", "62704"), ("Fairview", "OR", "97024"), ("Riverton", "UT", "84065"),
          ("Madison", "WI", "53703"), ("Franklin", "TN", "37064"), ("Georgetown", "TX", "78626"),
          ("Clayton", "MO", "63105"), ("Ashland", "VA", "23005")]


class Pool:
    """Deterministic pick helpers over a seeded ``random.Random``."""

    def __init__(self, seed: int, salt: str, roster=()):
        self.rng = random.Random(f"{seed}:{salt}")
        self._name_index = 0
        self._roster = tuple(roster)
        self._used_names = set(self._roster)
        self._locals: set[str] = set()

    def name(self):
        if self._name_index < len(self._roster):
            first, last = self._roster[self._name_index]
            self._name_index += 1
            return first, last
        while True:
            first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
            if (first, last) not in self._used_names:
                self._used_names.add((first, last))
                return first, last

    def email(self, first: str, last: str) -> str:
        local = f"{first[0].lower()}{last.lower()}"
        candidate = local
        suffix = 2
        while candidate in self._locals:
            candidate = f"{local}{suffix}"
            suffix += 1
        self._locals.add(candidate)
        return f"{candidate}@dundermifflin.example"

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

    def routing(self) -> str:
        # ABA routing numbers never start with 99, so these cannot be real banks.
        return f"99{self.rng.randint(0, 9_999_999):07d}"

    def account(self, digits: int = 10) -> str:
        return "".join(str(self.rng.randint(0, 9)) for _ in range(digits))

    def bank(self) -> str:
        return self.rng.choice(BANKS)


def bundle(provider, request, responses):
    return {"bundle_version": 1, "provider": provider, "captured_at": CAPTURED_AT,
            "request": request, "responses": responses}


# --- PrismHR -----------------------------------------------------------------
# Eight Scranton employees. Stanley's birth date is not a real day (invalid_date).
# The other seven are ordinary. Live spellings employerId, autoPolicy,
# hawaiiMedWaiver and payPeriodsPerWeek are reported once per bundle.

PRISM_CLIENT_ID = "132"


def prism_employee(pool: Pool, index: int, status: str, type_class: str, pay_method: str, job_code: str,
                   birth_date: str = None, manager: str = "", rehire_ok: str = "", term_reason: str = ""):
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
            "emailAddress": pool.email(first, last),
        },
        "client": {
            "employeeStatus": status, "statusClass": status, "statusDate": hire,
            "employeeType": {"F": "FT", "P": "PT"}.get(type_class, type_class), "typeClass": type_class,
            "typeDate": hire, "transferInfo": [], "property": [],
            "hawaiiMedWaiver": [],  # live spelling; spec says hawaiiMedWaivers
            "jobCode": job_code, "jobStartDate": hire,
            "firstHireDate": hire, "lastHireDate": hire,
            "flsaExempt": pay_method == "S", "cafeteriaPlan": [], "seniorityDate": hire,
            "officer": False, "workCompOfficer": False, "scorpOwner": False, "businessOwner": False,
            "termReasonCode": term_reason, "termExplanation": "Resigned" if term_reason else "",
            "lastStatusChangeDate": "", "lastJobChangeDate": "", "newHireReportDate": "",
            "employee1099": False, "clientEmployeeId": str(index), "clockNum": "",
            "primaryEmailSource": "",
            "benefitEmail": f"{first.lower()}.benefits@example.test" if index == 1 else "",  # empty live
            "rehireOk": rehire_ok, "returnDate": "",
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
            "ssn": pool.ssn(),
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
            "citizenshipStatus": "Z01", "firstPayPeriodHours": "",
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


# getClientCodes with options=Job, shaped like the live response.
def prism_job_codes():
    jobs = [{"id": code, "jobTitle": title, "glSegmentCode": "", "jobClass": job_class, "payGrade": "",
             "jobDescription": "", "jobObsolete": False, "supervisory": False, "flsaExempt": exempt}
            for code, title, job_class, exempt in (("OFFICE", "Receptionist", "8810N1", True),
                                                   ("WHSE", "Warehouse Associate", "8292N0", False),
                                                   ("SALES", "Sales Representative", "8742N4", False))]
    return {"clientCodes": {"clientId": PRISM_CLIENT_ID, "jobCode": jobs, "locationCode": None, "payGroups": None},
            "errorCode": "0", "errorMessage": "", "extension": None}


def build_prismhr(seed: int):
    pool = Pool(seed, "prismhr", SCRANTON_ROSTER)
    jobs = ("SALES", "WHSE", "OFFICE")
    manager = prism_employee(pool, 1, "A", "F", "S", rehire_ok="Y", job_code="SALES")
    records = [manager]
    for number in range(2, 8):
        records.append(prism_employee(pool, number, "A", "F", "H" if number % 2 == 0 else "S",
                                      manager=manager["id"], job_code=jobs[number % 3]))
    records.append(prism_employee(pool, 8, "T", "F", "H", manager=manager["id"], job_code="SALES",
                                  birth_date="2001-02-30", term_reason="RES"))
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
        "get_client_codes_job": prism_job_codes(),
    })


# PrismHR direct deposits: one checking deposit per employee. Stanley's account
# number is masked (masked_value). The other seven send the full number.

def prism_ach_line(pool: Pool, method: str, amount, masked=False):
    digits = pool.rng.randint(7, 11)
    return {"transitNum": pool.routing(), "accountNum": "*" * digits if masked else pool.account(digits),
            "accountType": "C", "method": method, "amount": amount, "limit": None,
            "status": "D", "bankName": pool.bank().upper(), "voucherTypeOverride": "RVS"}


def prism_dd_record(employee, direct_deposit):
    record = {key: employee[key] for key in ("id", "lastName", "firstName", "middleInitial", "preferredName")}
    for section in ("person", "contactInformation", "client", "compensation"):
        record[section] = None
    record["directDeposit"] = direct_deposit
    for section in ("hsa", "employeeEvents", "health", "skillsAndEducation", "absenceJournalId",
                    "benefitEnrollmentCompleted", "scheduledDeduction", "newHireQuestions",
                    "enrollmentInProgress"):
        record[section] = None
    return record


def prism_dd_header(pool: Pool, lines):
    return {"achStatus": "A", "voucherType": "RVS", "suppressAccountPrint": False,
            "achVoucher": lines, "directDepositChecksum": str(pool.rng.randint(1_000_000, 9_999_999))}


def build_prismhr_direct_deposits(seed: int):
    employees = [r for response in build_prismhr(seed)["responses"]["get_employee"] for r in response["employee"]]
    pool = Pool(seed, "prismhr-direct-deposit")
    records = []
    for index, employee in enumerate(employees):
        lines = [prism_ach_line(pool, "F", pool.money(100, 500), masked=index == len(employees) - 1)]
        if index == 0:
            lines.append(prism_ach_line(pool, "P", 10.0))
        records.append(prism_dd_record(employee, prism_dd_header(pool, lines)))
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_employee_direct_deposit": [prism_response(records[:4]), prism_response(records[4:])],
    })


# PrismHR deductions: one flat medical deduction per employee. Stanley's start
# date is not a real day (invalid_date). The other seven start on 2024-01-01.

def prism_deduction(code, deduction_type, method, description, amount, use_percent=False,
                    start="2024-01-01", **extra):
    line = {"deductionCode": code, "deductionType": deduction_type, "deductionMethod": method,
            "description": description, "usePercent": use_percent, "amount": amount, "period": "12345",
            "loanOrGarnishId": "", "benefitPlanId": "", "lastDedPerAdj": amount, "basis": "",
            "trackArrears": False, "startDate": start, "glOverrideAcct": "", "mandatory": False,
            "matchMethod": "", "matchDescription": "", "cutbackPayeeCode": "", "rateTableId": "",
            "rateTier": "", "achOption": ""}
    line.update(extra)
    return line


def prism_deductions_response(lines):
    return {"employeeDeductions": {"deduction": lines}, "errorCode": "0", "errorMessage": "", "extension": None}


def build_prismhr_deductions(seed: int):
    employee_list = build_prismhr(seed)["responses"]["get_employee_list"]
    ids = employee_list["employeeList"]["employeeId"]
    pool = Pool(seed, "prismhr-deduction")
    responses = {}
    for index, employee_id in enumerate(ids):
        amount = pool.money(40, 120)
        if index == len(ids) - 1:
            responses[employee_id] = prism_deductions_response([
                prism_deduction("MED", "V", "F", "Medical", amount, start="2025-02-30"),
                prism_deduction("401k", "K", "K", "401k", 5.0, use_percent=True, start="2016-12-01",
                                stopDate="2026-12-31", maximum=23000.0, basis="A", matchMethod="F",
                                matchAmount=50.0, cutbackPayeeCode="MEDCO"),
                prism_deduction("401KR", "KR", "PG", "Roth 401(k)", 4.0, use_percent=True, start="2016-12-01",
                                matchMethod="P", matchAmount=50.0),
                prism_deduction("UNIF", "V", "F", "Uniforms", 12.5, limit=25.0, maximum=300.0, basis="L"),
                prism_deduction("GARN", "G", "G", "Child Support", 180.0, maximum=900.0, basis="M"),
                prism_deduction("DUES", "V", "F", "Union Dues", 8.0, maximum=100.0, basis="Q"),
            ])
        else:
            responses[employee_id] = prism_deductions_response([
                prism_deduction("MED", "V", "F", "Medical", amount, start="2024-01-01")])
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_deductions": responses,
        "get_employee_list": employee_list,
    })


# PrismHR payroll: one completed regular batch and one regular voucher per
# employee. Voucher status PRNT has no documented meaning and is reported once.

def prism_pay_group(group_id, start, end):
    return {"payGroupId": group_id, "payPeriodStartDate": start, "payPeriodEndDate": end,
            "weeksWorked": 1, "deductPeriod": "1"}


def prism_batch(batch_id, pay_date, batch_type, status, groups):
    return {"batchId": batch_id, "payDate": pay_date, "batchType": batch_type, "batchStatus": status,
            "payGroup": groups}


def prism_earning(code, pay_class, class_description, hours, rate):
    return {"payCode": code, "payClass": pay_class, "payClassDescription": class_description, "chargeDate": "",
            "hoursUnits": hours, "hoursWorked": hours, "unitRate": rate, "payAmount": round(hours * rate, 2),
            "department": "OPS", "location": "HQ", "jobCode": "", "shift": ""}


def prism_employee_tax(code, description, taxable, amount):
    return {"empTaxDeductCode": code, "empTaxDeductCodeDesc": description, "empTaxableAmount": taxable,
            "empTaxAmount": amount, "empOverLimitAmount": 0.0}


def prism_company_tax(code, description, taxable, amount):
    return {"comTaxEntity": "US", "comTaxDeductCode": code, "comTaxDeductCodeDesc": description,
            "comExemptAmount": 0.0, "comShelteredAmount": 0.0, "comTaxableAmount": taxable, "comTaxType": "F",
            "comTaxAmount": amount, "comOvrLimit": 0.0, "comTaxRate": 0.0145}


def prism_voucher_deduction(code, deduction_type, description, amount):
    return {"deductCode": code, "deductDescription": description, "deductAmount": amount,
            "deductType": deduction_type, "deductUnionId": "", "planId": ""}


def prism_voucher(voucher_id, employee_id, batch_id, pay_date, period, voucher_type="R", status="PRNT",
                  gross=0.0, net=0.0, **extra):
    voucher = {"voucherId": voucher_id, "status": status, "type": voucher_type, "voidDate": "", "checkNumber": "",
               "payDate": pay_date, "employeeId": employee_id, "payPeriod": "W", "payPeriodStart": period[0],
               "payPeriodEnd": period[1], "payGroup": "WFRI", "dateProcessed": pay_date, "totalEarnings": gross,
               "employeeTax": [], "netPay": net, "voidVoucherId": "", "fitTaxableAmount": gross,
               "earnAmount": gross, "otherEarnAmount": 0.0, "wcHomeClass": "8810", "wcState": "IL",
               "workerComp": [], "earning": [], "otherEarningsDetail": [], "fsaMatch": [], "companyTax": [],
               "batchId": batch_id, "deduction": [], "otherDeduction": [], "benefit": [], "bankAccount": "PAYROLL",
               "checkNum": None, "checkAmt": 0.0, "payStubType": "S", "checkAccountACH": "", "directDeposit": [],
               "employerContributions": [], "retirement": None, "glAcctDistribution": None,
               "taxFilingStatus": [], "wcInformation": None, "fromArrears": [], "toArrears": [],
               "importBatchNo": ""}
    voucher.update(extra)
    return voucher


def prism_voucher_page(vouchers):
    return {"errorCode": "0", "errorMessage": "", "extension": None, "payrollVoucher": vouchers,
            "total": len(vouchers), "startpage": 0, "count": len(vouchers)}


def build_prismhr_payroll(seed: int):
    ids = build_prismhr(seed)["responses"]["get_employee_list"]["employeeList"]["employeeId"]
    week1 = ("2025-12-27", "2026-01-02")
    batches = [prism_batch("202601", "2026-01-09", "R", "COMP", [prism_pay_group("WFRI", *week1)])]
    vouchers = []
    for offset, employee_id in enumerate(ids):
        gross, tax = 1000.0, 80.0
        extra = {}
        if offset == 0:
            extra = {
                "checkNumber": "1001", "checkAmt": gross - tax, "voidDate": "2026-01-20",
                "companyTax": [prism_company_tax("00-15", "Medicare - Employer", gross, 14.5)],
                "deduction": [prism_voucher_deduction("401k", "K", "401k", 50.0)],
                "employerContributions": [{"code": "MED", "description": "Medical", "amount": 189.17}],
                "directDeposit": [{"transitNum": "991234567", "accountNum": "000123456789",
                                   "status": "A", "amount": gross - tax}],
            }
        vouchers.append(prism_voucher(
            f"V100{offset + 1:03d}", employee_id, "202601", "2026-01-09", week1,
            voucher_type="R", status="PRNT", gross=gross, net=gross - tax,
            earning=[prism_earning("REG", "E", "Earnings", 40, 25.0)],
            employeeTax=[prism_employee_tax("00-10", "Federal Income Tax", gross, tax)],
            **extra))
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_batch_list_by_date": {"errorCode": "0", "errorMessage": "", "extension": None, "batchList": batches},
        "get_payroll_voucher_for_batch": {"202601": [prism_voucher_page(vouchers)]},
        "get_batch_info": {"202601": {"errorCode": "0", "errorMessage": "", "extension": None, "batchControl": {
            "batchStatus": "COMP", "batchId": "202601", "payDate": "2026-01-09",
            "batchDescription": "202601 - 01-09-26 WFRI", "batchType": "R", "processor": "synthetic",
            "deliveryMethod": "PICKUP"}}},
    })


# Company cases: an unmasked federalIdNumber; the seven live-only clientMaster
# fields (spec_live_mismatch); an obsolete and a remote location; pay group
# SEMI with no schedule row; the live singular key clientPayrollSchedule
# (spec_live_mismatch).

def prism_location(location_id, name, line1, city, state, zipcode, obsolete_date=None, remote=False):
    return {"id": location_id, "locationName": name, "geoCode": "", "addressLine1": line1, "addressLine2": "",
            "zipCode": zipcode, "zipSuffix": "", "city": city, "county": "", "state": state,
            "workCompState": state, "latitude": "", "longitude": "", "obsoleteDate": obsolete_date,
            "locationObsolete": obsolete_date is not None, "locationContact": [], "remoteLocation": remote}


def prism_schedule(group_id, description, period, period_description):
    return {"groupId": group_id, "groupDesc": description, "scheduleId": "", "scheduleDesc": "",
            "weekEndOnDay": "", "printFaxBack": False, "payPeriod": period, "payPeriodDesc": period_description,
            "payDay": "", "skipWeekends": False, "callInDays": "", "deliverDays": "", "thirdPartyCode": "",
            "payPeriodEnd": "", "periodEndType": "", "periodEndTypeDesc": "", "periodEndType2": None,
            "periodEndType2Desc": ""}


def build_prismhr_company(seed: int):
    pool = Pool(seed, "prismhr-company")
    office = SCRANTON
    master = {
        "id": PRISM_CLIENT_ID, "clientName": "Dunder Mifflin", "legalName": "Dunder Mifflin Paper Company, Inc.",
        "serviceType": "PEO", "categoryCode": "", "costCenter": "", "statusClass": "A", "status": "A",
        "statusDate": "2019-04-01", "corporationType": "M", "addressLine1": office["line1"], "addressLine2": "Suite 200",
        "city": office["city"], "stateCode": office["state"], "zipCode": office["zip"], "zipSuffix": "1234",
        "mainPhone": pool.phone(), "mainPhoneExt": "101", "fax": "", "websiteUrl": "https://dundermifflin.example",
        "emailAddress": "payroll@dundermifflin.example", "businessDescription": "Paper and office supplies", "sicCode": "7363",
        "naicsCode": "561320", "federalIdNumber": "99-0000132", "employerId": "", "payrollDate": "",
        "eVerify": True, "externalPtoUsed": False, "notificationEmailList": [],
        "payrollFinalizationNotification": "N", "positionRatesUsed": "N", "reverseWireAccount": "",
        "taxesToSuppress": [], "checksum": "synthetic",
    }
    locations = [prism_location(str(number), f"Site {number}", f"{pool.rng.randint(100, 9899)} Commerce Way",
                                *pool.rng.choice(CITIES)) for number in (1, 2, 3)]
    locations.append(prism_location("OLD", "Closed Warehouse", "1 Dock St", "Springfield", "IL", "62704",
                                    obsolete_date="2024-06-30"))
    locations.append(prism_location("REM", "Remote Workers", "", "", "IL", "", remote=True))
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_client_master": {"errorCode": "0", "errorMessage": "", "extension": None, "clientMaster": master},
        "get_client_codes": {"errorCode": "0", "errorMessage": "", "extension": None, "clientCodes": {
            "clientId": PRISM_CLIENT_ID, "locationCode": locations,
            "payGroups": [{"payGroupCode": "WFRI", "description": "Weekly Paid Friday"},
                          {"payGroupCode": "M", "description": "MONTHLY"},
                          {"payGroupCode": "SEMI", "description": "Semi-monthly"}]}},
        "get_payroll_schedule": {"errorCode": "0", "errorMessage": "", "extension": None, "clientPayrollSchedule": [
            prism_schedule("M", "MONTHLY", "M", "Monthly (PayDay {1-28}{EOM})"),
            prism_schedule("WFRI", "Weekly Paid Friday", "W", "Weekly (PayDay {MON-SUN})")]},
    })


# --- isolved -----------------------------------------------------------------
# Eight Stamford employees. employmentCategoryCode FT, pay frequency 12 and the
# citizenship text are each reported once, on the first employee. The detail,
# personal and name-address overlays fill Phyllis and Creed.

ISOLVED_CLIENT_ID, ISOLVED_LEGAL_ID = "4046", "5806"
ISOLVED_BASE = f"https://myisolved.example/rest/api/clients/{ISOLVED_CLIENT_ID}/legals/{ISOLVED_LEGAL_ID}/employees"


def isolved_links(employee_id):
    base = f"{ISOLVED_BASE}/{employee_id}"
    return [{"href": base, "rel": "self"}, {"href": f"{base}/checks", "rel": "Checks"},
            {"href": f"{base}/taxWithholding", "rel": "EmployeeTaxWithholding"}]


def isolved_employee(pool: Pool, employee_id: int, number: int, status: str, pay_type: str,
                     gender: str, ssn: str, marital=None, manager=None,
                     terminated: str = None, rehired: str = None):
    first, last = pool.name()
    home = pool.address()
    hire = pool.date(2016, 2025)
    hourly = pool.money(15, 60, 4)
    annual = round(hourly * 2080, 2)
    record = {
        "id": employee_id,
        "acaEmploymentStatus": "ACA Full Time",
        "annualSalary": annual,
        "birthDate": f"{pool.date(1958, 2001)}T00:00:00",
        "emailAddress": pool.email(first, last),
        "employeeNumber": str(number),
        "employmentCategoryCode": "FT",
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
        "jobTitle": pool.rng.choice(["Regional Manager", "Sales Representative", "Accountant",
                                    "Receptionist", "Warehouse Associate"]),
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
        "normalHours": 173.33,
        "originalHireDate": f"{hire}T00:00:00",
        "payFrequency": 12,
        "payGroup": "Monthly",
        "payType": pay_type,
        "perPaySalary": round(annual / 12, 2),
        "personal": {
            "id": 1245000 + number, "faxNumber": "(801) 555-0142" if number == 2 else None,  # None live
            "homePhone": pool.phone() if number % 2 else None, "mobilePhone": pool.phone(),
            "officePhone": None, "personalEmailAddress": None, "preferredPronouns": None,
            "links": [{"href": None, "rel": "self"}, {"href": None, "method": "PUT", "rel": "EmployeePersonalUpdate"}],
        },
        "previousPunchLabors": None, "protectedVeteran": False, "reciprocityRule": "",
        "salaryEffectiveDate": f"{hire}T00:00:00",
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
    pool = Pool(seed, "isolved", STAMFORD_ROSTER)
    manager = isolved_employee(pool, 859201, 1, "Active", "Salary", "Male",
                               marital="Married", ssn=pool.ssn())
    records = [manager]
    for number in range(2, 9):
        kwargs = {"ssn": pool.ssn(), "manager": manager}
        status, pay_type = "Active", "Hourly" if number % 2 == 0 else "Salary"
        if number == 8:
            status = "Terminated"
            kwargs.update(terminated="2024-03-29", rehired="2023-01-09")
        records.append(isolved_employee(
            pool, 859200 + number, number, status, pay_type,
            "Male" if number % 2 == 0 else "Female", **kwargs))
    detail = dict(records[0])
    detail["organizations"] = [
        {"id": -1, "displayOrder": 1, "organizationId": 9943, "title": "Location", "value": "10",
         "valueDescription": "Stamford"},
        {"id": -2, "displayOrder": 2, "organizationId": 9944, "title": "Department", "value": "100",
         "valueDescription": "Management"},
    ]
    detail["payRates"] = []
    detail["taxes"] = {
        "federal": {"id": 1556268, "additionalAmount": None, "filingStatus": "FDM", "isBlocked": False,
                    "multipleJobsOrSpouseWorks": False, "primaryExemptions": 0, "taxCategoryId": "FEDWT",
                    "taxState": "", "links": []},
        "nonResidentCity": None, "nonResidentState": None, "residentCity": None,
        "residentState": {"id": 1556269, "filingStatus": "CTM", "isBlocked": False, "primaryExemptions": 0,
                          "taxCategoryId": "STATEWT", "taxDescription": "CONNECTICUT WH", "taxState": "CT", "links": []},
    }
    personal = dict(records[1]["personal"])
    personal["officePhone"] = pool.phone()
    personal["personalEmailAddress"] = "personal.two@example.test"
    name_address = {k: v for k, v in records[1]["nameAddress"].items() if k != "links"}
    name_address["id"] = 0
    name_address["preferredName"] = records[1]["nameAddress"]["firstName"]
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": [isolved_page(records[:3], 1, 2, len(records)), isolved_page(records[3:], 2, 2, len(records))],
        "employee_detail": {str(records[0]["id"]): detail},
        "personal": {str(records[1]["id"]): personal},
        "name_address": {str(records[1]["id"]): name_address},
    })


# isolved direct deposits: one checking deposit per employee. Andy's status
# Pending is not on the allowlist (unmapped_label). The other seven are Active.

def isolved_deposit(pool: Pool, deposit_id: int, sequence, status="Active", amount=None, percent=None,
                    account_type="Checking"):
    return {"id": deposit_id, "accountNumber": pool.account(pool.rng.randint(6, 12)),
            "accountType": account_type, "amount": amount, "bankName": pool.bank(), "description": None,
            "frequency": "Every Pay", "percent": percent, "routingNumber": pool.routing(),
            "sequenceNumber": sequence, "status": status}


def build_isolved_direct_deposits(seed: int):
    employees = build_isolved(seed)["responses"]["employees"]
    ids = [str(r["id"]) for page in employees for r in page["results"]]
    pool = Pool(seed, "isolved-direct-deposit")
    deposits = {}
    for offset, employee_id in enumerate(ids):
        status = "Pending" if offset == len(ids) - 1 else "Active"
        lines = [isolved_deposit(pool, 640200 + offset, 1, status=status, amount=pool.money(100, 500),
                                 account_type="Checking")]
        if offset == 0:
            lines.append(isolved_deposit(pool, 640300, 2, percent=10.0, account_type="Checking"))
        deposits[employee_id] = lines
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": employees,
        "direct_deposits": deposits,
    })


# isolved deductions: one medical deduction per employee. Andy's stop date is
# not a real day (invalid_date). The other seven have a start date only.

def isolved_pay_item(employee, item_id, kind, code, name, params=(), start=None, stop=None, **extra):
    base = f"{ISOLVED_BASE}/{employee['id']}"
    item = {"id": item_id, "calcParams": [{"paramType": t, "paramValue": v} for t, v in params],
            "employeeId": employee["id"], "employeeNumber": employee["employeeNumber"],
            "firstName": employee["nameAddress"]["firstName"], "lastName": employee["nameAddress"]["lastName"],
            "payItemCode": code, "payItemId": item_id, "payItemName": name, "payItemType": kind,
            "referenceNumber": None, "scheduleOverride": None,
            "startDate": f"{start}T00:00:00" if start else None, "stopDate": f"{stop}T00:00:00" if stop else None,
            "links": [{"href": base, "rel": "parent"},
                      {"href": f"{base}/payItems", "method": "POST", "rel": "Update EE Pay Item"}]}
    item.update(extra)
    return item


def build_isolved_deductions(seed: int):
    employees = build_isolved(seed)["responses"]["employees"]
    people = [r for page in employees for r in page["results"]]
    pool = Pool(seed, "isolved-deduction")
    pay_items = {}
    for offset, person in enumerate(people):
        lines = [isolved_pay_item(person, 780000 + offset, "Deduction", "030", "Medical Pre-tax",
                                  [("Amount", pool.money(40, 120))], start="2024-01-01",
                                  stop="2025-02-30" if offset == len(people) - 1 else None)]
        if offset == len(people) - 1:
            lines.append(isolved_pay_item(person, 780100, "Deduction", "32", "401K",
                                          [("Percent", 6.0)], start="2023-04-01", stop="2026-12-31"))
        pay_items[str(person["id"])] = lines
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": employees,
        "pay_items": pay_items,
    })


# isolved payroll: one completed regular run and one adjustment check per
# employee. Andy's check has no detail (missing_section). The other seven do.

ISOLVED_PAY_GROUP = "7627"


def isolved_datetime(value):
    return f"{value}T00:00:00" if value else None


def isolved_run(run_id, pay_date, number, run_type, status, period=(None, None), pay_of_month=""):
    return {"id": run_id, "impoundDate": isolved_datetime(pay_date), "inputMethod": "Time Entry",
            "payDate": isolved_datetime(pay_date), "payOfTheMonth": pay_of_month, "payPeriod": 26,
            "payrollRunType": run_type, "periodBeginDate": isolved_datetime(period[0]),
            "periodEndDate": isolved_datetime(period[1]), "processApprovedBy": None, "processedBy": "synthetic",
            "regularCheckAutoPay": False, "runDate": isolved_datetime(pay_date), "runNumber": number,
            "runTime": "09:00:00", "scheduledPayDate": isolved_datetime(pay_date),
            "scheduledRunDate": isolved_datetime(pay_date), "status": status, "submittedBy": None,
            "submittedDate": None, "submittedTime": None, "suppressPayStubEmailAlert": False}


def isolved_item(item_id, code, description, dollars, **extra):
    item = {"id": item_id, "checkDollars": dollars, "currentDollars": dollars, "ftdDollars": 0.0,
            "itemCode": code, "itemDescription": description, "mtdDollars": dollars, "ptdDollars": dollars,
            "qtdDollars": dollars, "sequence": 1, "ytdDollars": dollars, "links": []}
    item.update(extra)
    return item


def isolved_earning(item_id, code, description, hours, dollars, memo=False):
    return isolved_item(item_id, code, description, dollars, checkHours=hours, checkUnits=0.0,
                        isMemoEarning=memo, labors=None)


def isolved_tax(item_id, description, employee_side, dollars, wages):
    return isolved_item(item_id, None, description, dollars, isEmployeeTax=employee_side,
                        checkTaxableWages=wages)


def isolved_benefit(title, employee_deduction, employer_contribution):
    return {"benefitDescription": f"{title} plan", "benefitTitle": title, "checkEligibleWages": 1500.0,
            "checkEmployeeCatchUp": 0.0, "checkEmployeeDeduction": employee_deduction,
            "checkEmployerContribution": employer_contribution, "checkMatchEligibleWages": 0.0,
            "ytdEmployeeDeduction": employee_deduction, "ytdEmployerContribution": employer_contribution}


def isolved_check(pool: Pool, person, check_id, number, check_date, run_number, check_type, gross, net,
                  check_amount=0.0, deposit_amount=0.0, period=(None, None), **extra):
    address = person["nameAddress"]
    check = {"id": check_id, "accruals": None, "benefits": None, "checkAmount": check_amount,
             "checkDate": isolved_datetime(check_date), "checkNumber": number, "checkSequence": 1,
             "checkTypeDescription": check_type, "deductions": [], "directDepositAmount": deposit_amount,
             "directDeposits": None, "earnings": [], "employeeAddress1": address["address1"],
             "employeeAddress2": None, "employeeCity": address["city"], "employeeFederalAddlAmountOrPercent": "0",
             "employeeFederalExemptions": 0, "employeeFederalFilingStatus": "Single", "employeeId": person["id"],
             "employeeName": f"{address['lastName']}, {address['firstName']}",
             "employeeNumber": person["employeeNumber"], "employeeOrganizations": None,
             "employeeSSN": pool.ssn(), "employeeState": address["state"],
             "employeeStateAddlAmountOrPercent": "0", "employeeStateExemptions": 0,
             "employeeStateFilingStatus": "Single", "employeeZipCode": address["zipCode"], "garnishments": None,
             "grossPay": gross, "grossWages": gross, "isRemoteWorker": False,
             "legalCompanyName": "Synthetic Legal Co", "netPay": net, "payrollRunNumber": run_number,
             "payrollRunType": "Regular Payroll", "periodBeginDate": isolved_datetime(period[0]),
             "periodEndDate": isolved_datetime(period[1]), "reissueCheckDate": None, "reissueCheckNumber": None,
             "taxCategories": [{"taxCategoryId": "FEDWT", "description": "FEDERAL WH"}], "taxes": None,
             "vertexResidentGeoCode": "UT0350270", "vertexSchoolDistrictCode": 0, "vertexWorkGeoCode": "UT0350270",
             "voucherNumber": f"V{check_id}", "links": []}
    check.update(extra)
    return check


def isolved_check_detail(check, taxes=(), benefits=()):
    detail = dict(check)
    detail.update(taxes=list(taxes), benefits=list(benefits), employeeOrganizations=[])
    return detail


def build_isolved_payroll(seed: int):
    employees = build_isolved(seed)["responses"]["employees"]
    people = [r for page in employees for r in page["results"]]
    pool = Pool(seed, "isolved-payroll")
    period = ("2025-12-22", "2026-01-04")
    runs = [isolved_run(4100001, "2026-01-09", 1, "Regular Payroll", "Completed Payroll Run", period,
                        "1st Payroll of Month")]
    checks, details = {}, {}
    for offset, person in enumerate(people):
        gross, tax = 1000.0, 80.0
        earnings = [isolved_earning(3000 + offset, "01", "Regular", 80.0, gross)]
        extra = {}
        taxes = [isolved_tax(4000 + offset, "FEDERAL WH", True, tax, gross)]
        if offset == 0:
            earnings.append(isolved_earning(3001, "001", "401k Match", 0.0, 45.0, memo=True))
            extra["deductions"] = [isolved_item(3002, "030", "Medical Pre-tax", 40.0)]
            extra["directDeposits"] = [{"id": 3003, "account": "000987654321", "depositAmount": gross - tax,
                                        "itemDescription": "Checking", "links": []}]
            taxes.append(isolved_tax(4001, "SOC SEC ER", False, 62.0, gross))
            benefits = [isolved_benefit("401(k)", 40.0, 45.0)]
        else:
            benefits = []
        check = isolved_check(
            pool, person, 21010001 + offset, 6000 + offset, "2026-01-09", 1, "Adjustment", gross, gross - tax,
            deposit_amount=gross - tax, period=period, earnings=earnings, **extra)
        checks[str(person["id"])] = [isolved_page([check], 1, 1, 1)]
        if offset != len(people) - 1:
            details[str(check["id"])] = isolved_check_detail(check, taxes=taxes, benefits=benefits)
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": employees,
        "payroll_run_history": {ISOLVED_PAY_GROUP: runs},
        "checks": checks,
        "check_detail": details,
    })


# Company cases: the includeDetails shape with dbaName and naicsCode absent, as
# live (dbaName: missing_section); active and inactive work locations and pay
# groups; an integer payFrequency (undocumented_code); services and workers'
# comp codes passed through to unmapped.

def isolved_work_location(location_id, code, description, line1, city, state, zipcode, inactive=False):
    return {"id": location_id, "address1": line1, "address2": None, "addressDescription": None, "city": city,
            "geoCode": "000000000", "includeWorkSiteTaxFiling": False, "isInactive": inactive,
            "isRemoteWorkersOnly": False, "minimumWageRule": None, "overrideTaxCode": None,
            "reportingUnitNumber": None, "schoolDistrictCode": None, "state": state, "taxDistrict": None,
            "timeZone": "Mountain Standard Time", "workLocationCode": code, "workLocationDescription": description,
            "zipCode": zipcode, "links": [{"href": f"{ISOLVED_BASE[:-len('/employees')]}/workLocations/{location_id}",
                                           "rel": "self"}]}


def isolved_legal_pay_group(group_id, name, frequency, inactive=False):
    return {"id": group_id, "enableiSolvedPayroll": True, "enableiSolvedTime": False,
            "inputMethod": "Web Submit and Process", "isInactive": inactive, "normalHours": 173.33,
            "payFrequency": frequency, "payGroupName": name, "payrollType": "Regular Payroll"}


def build_isolved_company(seed: int):
    pool = Pool(seed, "isolved-company")
    office = STAMFORD
    legal = {
        "id": int(ISOLVED_LEGAL_ID), "allowRemoteWorkers": False,
        "client": {"id": int(ISOLVED_CLIENT_ID), "clientCode": "SYN42", "clientName": "Dunder Mifflin",
                   "securityServiceGroup": {"id": 2, "name": "Demo"}, "links": []},
        "compensationPlans": None, "federalEIN": "990004046", "forceDirectDepositPrenote": False,
        "iSolvedTimeEnabled": False,
        "legalAddress": {"addressDescription": "Legal", "city": office["city"], "phoneNumber": pool.phone(),
                         "state": office["state"], "streetAddress1": office["line1"], "streetAddress2": None,
                         "zipCode": office["zip"]},
        "legalCode": "SYN42-1", "legalName": "Dunder Mifflin Stamford, Inc.",
        "payGroups": [isolved_legal_pay_group(int(ISOLVED_PAY_GROUP), "Monthly", 12),
                      isolved_legal_pay_group(int(ISOLVED_PAY_GROUP) + 1, "Old Weekly", 52, inactive=True)],
        "services": [{"code": "BASE", "startDate": "2018-08-13T00:00:00"},
                     {"code": "ACA", "startDate": "2024-06-12T00:00:00"}],
        "status": "Active",
        "workersComps": [{"code": "8810", "description": "Clerical", "state": "UT"}],
        "workLocations": [isolved_work_location(25721, "UT1", "SALT LAKE CITY, UT", "100 Main St", "Salt Lake City",
                                                "UT", "84101"),
                          isolved_work_location(25722, "UT2", "OGDEN, UT", "5 Depot Rd", "Ogden", "UT", "84401",
                                                inactive=True)],
        "links": [{"href": ISOLVED_BASE[:-len("/employees")], "rel": "self"}],
    }
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {"legal": legal})


# --- UKG Ready ---------------------------------------------------------------
# Eight Utica employees. The employee-type id and the pay-type id are each
# reported once, on Erin. ein_name on the detail response is reported once.

UKG_COMPANY_ID = "33704016"
UKG_BASE = f"https://secure.example-ukg.test/ta/rest/v2/companies/{UKG_COMPANY_ID}"
UKG_EMPLOYEE_TYPES = [(35330176, "FT Non-Exempt"), (35330178, "FT Exempt"), (35330177, "PT Hourly"),
                      (35330181, "Temp"), (35330179, "Consultant")]
UKG_PAY_TYPES = [(35043008, "Hourly"), (35043009, "Salaried")]
UKG_JOBS = [(8634524176, "Sales Representative"), (8634524184, "Accountant"),
            (8634524226, "Regional Manager")]


def ukg_links(aid, detail=False):
    base = f"{UKG_BASE}/employees/{aid}"
    links = {"self": base}
    if detail:
        links["country-fields"] = f"{base}/country-fields"  # live-only link
    links.update({"demographics": f"{base}/demographics", "badges": f"{base}/badges",
                  "pay-info": f"{base}/pay-info", "profiles": f"{base}/profiles"})
    return links


def ukg_employee(pool: Pool, aid: int, number: int, status: str, terminated: str = None,
                 rehired: str = None, managers=None, mailing: bool = False):
    first, last = pool.name()
    home = pool.address()
    hire = pool.date(2016, 2025)
    dates = {"hired": hire, "started": hire}
    if rehired:
        dates["re_hired"] = rehired
    if terminated:
        dates["terminated"] = terminated
    listed = {
        "id": aid, "employee_id": str(number), "username": pool.email(first, last).split("@", 1)[0],
        "first_name": first, "last_name": last, "primary_account_id": aid, "ein_name": "Dunder Mifflin Utica",
        "_links": ukg_links(aid), "status": status, "dates": dict(dates),
    }
    detail = {
        "id": aid, "employee_id": str(number), "username": listed["username"],
        "first_name": first, "last_name": last, "primary_account_id": aid,
        "ein_name": "Dunder Mifflin Utica",  # live-only on the detail response
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
        "primary_email": f"{listed['username']}@dundermifflin.example",
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


def ukg_pay_info(employee_type: int, pay_type: int, default_job: int):
    return {"standard_work_day": 28_800_000, "employee_type": {"id": employee_type}, "pay_type": {"id": pay_type},
            "default_job": {"id": default_job}, "ttoc": [], "payroll_classification": "REGULAR"}


def ukg_comp(aid: int, effective: str, amount: float, hourly: float, amount_period: str,
             time_ms: int = 7_488_000_000, time_period: str = "YEAR"):
    row_id = int(effective.replace("-", "") + str(aid))
    return {"id": row_id, "employee": {"account_id": aid}, "effective_from": effective, "amount": amount,
            "hourly_pay": hourly, "amount_period": amount_period, "time": time_ms, "time_period": time_period,
            "num_pp_in_year": 26, "_links": {"self": f"{UKG_BASE}/compensation/history/{row_id}"},
            "currency": "USD"}


def build_ukg(seed: int):
    pool = Pool(seed, "ukg-ready", UTICA_ROSTER)
    ids = [12935181566 + i for i in range(8)]
    people = []
    for number, aid in enumerate(ids, start=1):
        if number == 8:
            people.append(ukg_employee(pool, aid, number, "Terminated", terminated="2024-06-28",
                                       rehired="2022-02-14", managers=[ids[0]]))
        else:
            people.append(ukg_employee(pool, aid, number, "Active",
                                       managers=None if number == 1 else [ids[0]],
                                       mailing=number == 2))
    jobs = (8634524226, 8634524176, 8634524184)
    responses = {
        "employees": {"employees": [listed for listed, _ in people]},
        "employee": {str(aid): detail for aid, (_, detail) in zip(ids, people)},
        "demographics": {},
        "pay_info": {},
        "tax_info": {},
        "compensation_history": {},
        "lookup_employee_types": {"items": [{"id": i, "name": n} for i, n in UKG_EMPLOYEE_TYPES]},
        "lookup_pay_types": {"items": [{"id": i, "name": n} for i, n in UKG_PAY_TYPES]},
        "lookup_eins": {"items": [{"id": 35419520, "ein_name": "Dunder Mifflin Utica", "ein_tax_id": "12-3456789",
                                   "ein_country_id": "USA"}]},
        "lookup_jobs": {"items": [{"id": i, "name": n, "visible": True} for i, n in UKG_JOBS]},
    }
    for offset, aid in enumerate(ids):
        key = str(aid)
        responses["demographics"][key] = ukg_demographics(pool, "MALE" if offset % 2 == 0 else "FEMALE")
        amount = pool.money(60_000, 140_000)
        responses["pay_info"][key] = ukg_pay_info(35330178, 35043009, default_job=jobs[offset % 3])
        if offset == 1:
            responses["compensation_history"][key] = {"compensations": [
                ukg_comp(aid, "2024-01-01", round(amount / 26, 2), round(amount / 2080, 4), "PAY_PERIOD",
                         time_ms=288_000_000, time_period="PAY_PERIOD")]}
        else:
            responses["compensation_history"][key] = {"compensations": [
                ukg_comp(aid, "2024-01-01", amount, round(amount / 2080, 4), "YEAR")]}
        responses["tax_info"][key] = {
            "employee-tax-type": {"W2": True, "_1099": False, "DRAW": False},
            "pension-box-type": "SYSTEM_RULES", "third-party-sick": "COMPANY_DEFAULT"}
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, responses)


# UKG Ready direct deposits: one flat checking deposit per employee. Charles's
# start date is not a real day (invalid_date). The other seven start on 2024-01-01.

UKG_CALC_NAMES = {"FULL": "Entire/Remainder", "FLAT_AMOUNT": "Flat $ Amount", "NET_PAY": "% Of Net Pay",
                  "GROSS_EARNING": "% Of Gross Earnings", "DIRECT_DEPOSIT_PER_OF_REMAINDER": "% Of Remainder"}


def ukg_deposit(pool: Pool, deposit_id: int, sequence: int, calc: str, active_from: str, amount=None,
                percentage=None):
    base = f"{UKG_BASE}/direct-deposits/{deposit_id}"
    line = {"id": deposit_id, "sequence": sequence, "type": "DIRECT_DEPOSIT", "active_from": active_from,
            "active_to": "2099-12-31", "active": True}
    if amount is not None:
        line["amount"] = amount
    if percentage is not None:
        line["percentage"] = percentage
    line["calc_method"] = {"display_name": UKG_CALC_NAMES[calc], "type": calc}
    line.update({"account_type": "CHECKING", "account_number": pool.account(pool.rng.randint(6, 11)),
                 "routing_number": pool.routing(), "routing_type": "ABA", "pre_note_status": "READY_TO_SEND"})
    line.update({
        "arrearage_function": "UNKNOWN", "payroll_frequency": {"type": "EVERY_PAY"},
        "used_in_pay_statement": False, "is_paypal": False, "visible": True,
        "_documents_count": 0, "_notes_count": 0,
        "_links": {"self": base, "edit": base, "delete": base,
                   "notes": f"{UKG_BASE}/notes?token=synthetic{deposit_id}",
                   "add_note": f"{UKG_BASE}/notes?token=synthetic{deposit_id}"},
    })
    return line


def ukg_deposits_response(lines):
    add = f"{UKG_BASE}/direct-deposits"
    return {"deposits": lines, "_links": {"add": add, "reserve_live_check": add, "cancel_pre_note": add},
            "_routing_type": "ABA"}


def build_ukg_direct_deposits(seed: int):
    employees = build_ukg(seed)["responses"]["employees"]
    ids = [str(e["id"]) for e in employees["employees"]]
    pool = Pool(seed, "ukg-ready-direct-deposit")
    deposits = {}
    for offset, account_id in enumerate(ids):
        started = "2025-02-30" if offset == len(ids) - 1 else "2024-01-01"
        lines = [ukg_deposit(pool, 47481000 + offset, 1, "FLAT_AMOUNT", started, amount=pool.money(100, 500))]
        if offset == 0:
            lines.append(ukg_deposit(pool, 47482000, 2, "NET_PAY", "2024-01-01", percentage=10.0))
        deposits[account_id] = ukg_deposits_response(lines)
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "employees": employees,
        "direct_deposits": deposits,
    })


# UKG Ready deductions: one flat medical deduction per employee. The method
# type has no enum, so FLAT_AMOUNT is reported once, on Erin's line.

UKG_FREQUENCY_NAMES = {"EVERY_SCHEDULED_PAY": "Every Scheduled Pay", "EVERY_PAY": "Every Pay",
                       "BENEFIT_PLAN": "Benefit Plan", "EVERY_SCHEDULED_MONTH_ODD_PAY": "Every Scheduled Month Odd Pay",
                       "HOLIDAY_TABLE": "Holiday Table", "WEEKLY": "Weekly"}
UKG_DEDUCTION_METHODS = {"EARNING_LIST": "% Of Earnings List", "FLAT_AMOUNT": "Flat $ Amount"}


def ukg_deduction_line(deduction_id, code, name, sequence):
    return {"id": deduction_id, "deduction": {"name": name, "code": code}, "effective_from": "2024-01-01",
            "effective_to": "9999-12-31", "sequence": sequence,
            "_links": {"self": f"{UKG_BASE}/employees/deductions/{deduction_id}"}}


def ukg_deduction_detail(line, frequency, method, amount=None, percent=None, annual_max=None, er_annual_max=None,
                         vendor=None, max_amount=None):
    detail = {key: line[key] for key in ("id", "deduction", "effective_from", "effective_to", "sequence")}
    if annual_max is not None:
        detail["annual_max_amount"] = annual_max
    if er_annual_max is not None:
        detail["er_annual_max_amount"] = er_annual_max
        detail["er_frequency"] = {"display_name": UKG_FREQUENCY_NAMES[frequency], "type": frequency}
    detail["memo"] = f"Synthetic memo {line['id']}"
    if vendor is not None:
        detail["vendor"] = vendor
    detail["cost_centers"] = [{"index": 0, "value": {"id": 393472, "display_name": "WorkFromHome"}}]
    detail["ee_frequency"] = {"display_name": UKG_FREQUENCY_NAMES[frequency], "type": frequency}
    calc = {"method": {"display_name": UKG_DEDUCTION_METHODS[method], "type": method}}
    if amount is not None:
        calc["amount"] = amount
    if percent is not None:
        calc["percent"] = percent
    detail["ee_calc_method"] = calc
    detail["ee_min_calc_method"] = {"amount": 0, "percent": 0}
    if max_amount is not None:
        detail["ee_max_calc_method"] = {"amount": max_amount, "percent": 0}
    return detail


def build_ukg_deductions(seed: int):
    employees = build_ukg(seed)["responses"]["employees"]
    ids = [str(e["id"]) for e in employees["employees"]]
    pool = Pool(seed, "ukg-ready-deduction")
    lines, details = {}, []
    for offset, account_id in enumerate(ids):
        line = ukg_deduction_line(198000 + offset, "Medical", "Medical", 1)
        lines[account_id] = [line]
        if offset == 0:
            details.append(ukg_deduction_detail(
                line, "EVERY_PAY", "FLAT_AMOUNT", amount=pool.money(40, 120), annual_max=23000,
                er_annual_max=5000, vendor={"id": 65792, "name": "Retirement Vendor"}, max_amount=500))
            percent_line = ukg_deduction_line(198100, "401k", "401k", 2)
            lines[account_id].append(percent_line)
            details.append(ukg_deduction_detail(percent_line, "EVERY_PAY", "FLAT_AMOUNT", percent=6))
        else:
            details.append(ukg_deduction_detail(line, "EVERY_PAY", "FLAT_AMOUNT", amount=pool.money(40, 120)))
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "employees": employees,
        "deductions": {aid: {"deductions": items} for aid, items in lines.items()},
        "deduction_detail": {str(detail["id"]): detail for detail in details},
    })


# UKG Ready payroll: one finalized regular payroll and one statement per
# employee. Charles's statement type Gross Up is reported once (unmapped_label).
# No statement carries gross or net totals. calcUpto and emptyEarning are
# reported once.

UKG_PAYROLL = f"{UKG_BASE}/payrolls"
UKG_EIN = {"id": 35419520, "ein_name": "Dunder Mifflin Utica", "ein_tax_id": "12-3456789"}


def ukg_payroll(payroll_id, name, status, pay_date, start, end, type_id=641, type_name="Regular"):
    return {"id": payroll_id, "name": name, "start_date": start, "end_date": end, "pay_date": pay_date,
            "type": {"id": type_id, "display_name": type_name}, "status": status, "ein": dict(UKG_EIN),
            "billable": True, "direct_deposit_date": pay_date, "sch_submit_date_time": None,
            "invoice_generator_id": None, "adjustment_grab_YTD_from_payroll_id": None,
            "dflt_pay_statement_type_id": 36656000, "dflt_pay_stub_note": "",
            "_links": {"self": f"{UKG_PAYROLL}/{payroll_id}"}}


def ukg_statement(statement_id, aid, payroll_id, status, pay_date, start, end, type_id=36656000,
                  type_name="Regular"):
    return {"employee": {"account_id": aid}, "id": statement_id, "pay_date": pay_date, "status": status,
            "type": {"id": type_id, "display_name": type_name}, "pay_period_start": start,
            "pay_period_end": end, "calcUpto": None, "emptyEarning": False,
            "_links": {"self": f"{UKG_PAYROLL}/{payroll_id}/pay-statements/{statement_id}"}}


def ukg_earning(line_id, code, name, hours_ms, rate, amount):
    return {"id": line_id, "type_name": "Earning", "batch": {"id": 1, "display_name": "Auto"},
            "hours": hours_ms, "base_rate": rate, "quantity": 0, "ee_amount": amount,
            "cost_centers": [], "earning": {"name": name, "external_id": "", "code": code, "id": line_id + 100}}


def ukg_statement_deduction(line_id, code, name, ee=None, er=None):
    line = {"id": line_id, "type_name": "Deduction (Auto)", "batch": {"id": 1, "display_name": "Auto"},
            "quantity": 0, "base_rate": 0, "vendor": None, "cost_centers": [],
            "deduction": {"name": name, "external_id": "", "code": code},
            "ee_gross_wage": 2075.0, "ee_subject_wage": 2075.0, "ee_gross_subject_wage": 2075.0}
    if ee is not None:
        line["ee_amount"] = ee
    if er is not None:
        line["er_amount"] = er
    return line


def ukg_statement_tax(line_id, code, name, ee, er, wage):
    return {"id": line_id, "type_name": "Tax", "batch": {"id": 1, "display_name": "Auto"},
            "ee_amount": ee, "er_amount": er, "ee_gross_wage": 2075.0, "ee_subject_wage": wage,
            "ee_gross_subject_wage": wage, "er_gross_wage": 2075.0, "er_subject_wage": wage,
            "er_gross_subject_wage": wage, "company_tax": {"code": code, "name": name, "abbrev": code}}


def ukg_detail(statement, earnings=(), deductions=(), taxes=(), payments=()):
    detail = {k: v for k, v in statement.items() if k not in ("calcUpto", "emptyEarning", "_links")}
    detail.update(earnings=list(earnings), deductions=list(deductions), taxes=list(taxes),
                  messages=[], payments=list(payments))
    return detail


def build_ukg_payroll(seed: int):
    ids = [r["id"] for r in build_ukg(seed)["responses"]["employees"]["employees"]]
    period = ("2025-12-21", "2026-01-03")
    payrolls = [
        ukg_payroll(4332470001, "Primary-EIN Regular Bi-Weekly 01/09/2026", "FINALIZED", "2026-01-09", *period),
    ]
    statements, details = [], []
    for offset, aid in enumerate(ids):
        type_name = "Gross Up" if offset == len(ids) - 1 else "Regular"
        type_id = 36656002 if type_name == "Gross Up" else 36656000
        statement = ukg_statement(85950001 + offset, aid, 4332470001, "FINALIZED", "2026-01-09", *period,
                                  type_id=type_id, type_name=type_name)
        statements.append(statement)
        deductions = []
        payments = []
        if offset == len(ids) - 1:
            deductions = [ukg_statement_deduction(860100, "401k", "401k", ee=50.0, er=25.0)]
            payments = [{"id": 860200, "hours": 0, "quantity": 0, "ee_amount": 920.0,
                         "type_name": "Direct Deposit", "batch": {"id": 1, "display_name": "Auto"}}]
        details.append(ukg_detail(
            statement,
            earnings=[ukg_earning(860000 + offset, "REG", "Regular", 288_000_000, 25.0, 1000.0)],
            deductions=deductions,
            taxes=[ukg_statement_tax(870000 + offset, "FIT", "Federal Income Tax", 80.0, 0.0, 1000.0)],
            payments=payments))

    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "payrolls": {"payrolls": payrolls},
        "pay_statements": {"4332470001": {"pay_statements": statements}},
        "pay_statement_detail": {str(detail["id"]): detail for detail in details},
        "lookup_eins": {"items": [dict(UKG_EIN, ein_country_id="USA")]},
    })


# Company cases: one EIN (the two-EIN case is a test variant); a profile per
# period_type, every_n_weeks with 2 and 3 weeks, the out-of-enum "fortnightly"
# (out_of_schema_value), and one profile with effective_to.

def ukg_profile(profile_id, name, active, period_type, params=None, effective_from="2018-01-21",
                effective_to=None, description=None):
    profile = {"id": profile_id, "name": name, "active": active, "effective_from": effective_from,
               "period_type": {"type": period_type, "params": params or {}}}
    if effective_to:
        profile["effective_to"] = effective_to
    if description:
        profile["description"] = description
    return profile


def build_ukg_company(seed: int):
    profiles = [
        ukg_profile(36562688, "Primary-EIN Regular Bi-Weekly", True, "every_n_weeks",
                    {"start_date": "2017-10-29", "num_weeks": 2}, description="Dunder Mifflin Utica payroll"),
        ukg_profile(36562692, "Weekly", False, "weekly", {"week_day": "SUNDAY"}, effective_from="2013-12-15"),
        ukg_profile(36562698, "Semi-Monthly", False, "semi_monthly", {"starting_on_first": 1, "starting_on_sec": 16},
                    effective_from="2019-01-01"),
        ukg_profile(36562689, "Monthly", False, "monthly", {"start_day": 1}, effective_from="2018-01-01"),
        ukg_profile(36562700, "Every Three Weeks", False, "every_n_weeks",
                    {"start_date": "2017-10-29", "num_weeks": 3}),
        ukg_profile(36562701, "Quarterly", False, "quarterly", {"start_date": "2018-01-01"}),
        ukg_profile(36562702, "Monthly Second Friday", False, "monthly_weekday", {"week_num": 2, "week_day": "FRIDAY"}),
        ukg_profile(36562703, "Every Ten Days", False, "every_n_days", {"start_date": "2018-01-01", "num_days": 10}),
        ukg_profile(36562699, "Test", False, "user_defined", effective_from="2023-05-01", effective_to="2023-10-01"),
        ukg_profile(36562704, "Fortnightly", False, "fortnightly"),
    ]
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "lookup_eins": {"items": [dict(UKG_EIN, ein_country_id="USA", ein_currency_code="USD")]},
        "lookup_pay_period_profiles": {"items": profiles},
    })


BUILDERS = {
    "prismhr": {"company": build_prismhr_company, "employee": build_prismhr,
                "direct-deposit": build_prismhr_direct_deposits, "deduction": build_prismhr_deductions,
                "payroll": build_prismhr_payroll},
    "isolved": {"company": build_isolved_company, "employee": build_isolved,
                "direct-deposit": build_isolved_direct_deposits, "deduction": build_isolved_deductions,
                "payroll": build_isolved_payroll},
    "ukg-ready": {"company": build_ukg_company, "employee": build_ukg,
                  "direct-deposit": build_ukg_direct_deposits, "deduction": build_ukg_deductions,
                  "payroll": build_ukg_payroll},
}
# Bundle file name and golden-output suffix per entity.
ENTITY_FILES = {"company": ("company-bundle.json", "company"),
                "employee": ("employee-bundle.json", "employees"),
                "direct-deposit": ("direct-deposit-bundle.json", "direct-deposits"),
                "deduction": ("deduction-bundle.json", "deductions"),
                "payroll": ("payroll-bundle.json", "payroll")}


def dumps(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def generate(seed: int = DEFAULT_SEED) -> dict:
    """Return {relative path: file text} for every fixture file."""
    files = {}
    for provider, builders in BUILDERS.items():
        for entity, builder in builders.items():
            bundle_name, suffix = ENTITY_FILES[entity]
            raw = builder(seed)
            files[f"{provider}/{bundle_name}"] = dumps(raw)
            output = ADAPTERS[provider].NORMALIZERS[entity](parse_bundle(raw, entity=entity))
            files[f"expected/{provider}-{suffix}.json"] = dumps(output.to_dict())
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
