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


# PrismHR direct deposits: getEmployee with options=DirectDeposit for the same
# employees. Injected cases: P with a limit, FS prenote, PN, an unmasked
# account number (the rest are masked, as live), B carrying an amount and F
# without one (inconsistent_allocation), undocumented method "Z"
# (undocumented_code), an empty header (no setup, as live), and a record with
# directDeposit null (missing_section).

def prism_ach_line(pool: Pool, method: str, amount=None, account_type="C", status="D",
                   limit=None, override="RVS", masked=True):
    digits = pool.rng.randint(7, 11)
    return {"transitNum": pool.routing(), "accountNum": "*" * digits if masked else pool.account(digits),
            "accountType": account_type, "method": method, "amount": amount, "limit": limit,
            "status": status, "bankName": pool.bank().upper(), "voucherTypeOverride": override}


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


def prism_dd_header(pool: Pool, lines, status="A", voucher_type="RVS"):
    return {"achStatus": status, "voucherType": voucher_type, "suppressAccountPrint": False,
            "achVoucher": lines, "directDepositChecksum": str(pool.rng.randint(1_000_000, 9_999_999))}


def build_prismhr_direct_deposits(seed: int):
    employees = [r for response in build_prismhr(seed)["responses"]["get_employee"] for r in response["employee"]]
    pool = Pool(seed, "prismhr-direct-deposit")
    headers = [
        prism_dd_header(pool, [prism_ach_line(pool, "F", 250.0, account_type="S", masked=False),
                               prism_ach_line(pool, "B")]),
        prism_dd_header(pool, [prism_ach_line(pool, "P", 20.0, limit=500.0), prism_ach_line(pool, "B")]),
        prism_dd_header(pool, [prism_ach_line(pool, "FS", 100.0, status="P", override="R"),
                               prism_ach_line(pool, "PN", 10.0, account_type="S", override="")]),
        prism_dd_header(pool, [prism_ach_line(pool, "B", 75.0),  # B must not carry an amount
                               prism_ach_line(pool, "F", None, account_type="S")]),  # F needs one
        prism_dd_header(pool, [prism_ach_line(pool, "Z", 40.0, account_type="IP", status="I")], status="I"),
        prism_dd_header(pool, [], status="", voucher_type=""),  # no setup, as live
        None,  # section missing
    ]
    for header in headers:
        if header is not None and not header["achVoucher"]:
            header["directDepositChecksum"] = "0"
    records = [prism_dd_record(employee, header) for employee, header in zip(employees, headers)]
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_employee_direct_deposit": [prism_response(records[:4]), prism_response(records[4:])],
    })


# PrismHR deductions: one getDeductions response per employee ID. Benefit-plan
# lines carry only ten fields and no dates, as live. Injected cases: every
# maximum basis, a match of each method, usePercent "T" (spec prose) and an
# invalid usePercent (out_of_schema_value), undocumented deductionType,
# deductionMethod and basis (undocumented_code), a maximum without a basis
# (inconsistent_allocation), an invalid startDate (invalid_date), an empty
# deduction list (as live), an employee with no response (missing_section) and
# an unlisted employee whose response carries an errorCode (missing_section).

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


def prism_benefit_deduction(code, description, plan, amount=0.0):
    return {"deductionCode": code, "deductionType": "V", "deductionMethod": "F", "description": description,
            "usePercent": False, "amount": amount, "period": "1234", "loanOrGarnishId": "",
            "benefitPlanId": plan, "lastDedPerAdj": amount}


def prism_deductions_response(lines, error_code="0", error_message=""):
    return {"employeeDeductions": {"deduction": lines} if error_code == "0" else None,
            "errorCode": error_code, "errorMessage": error_message, "extension": None}


def build_prismhr_deductions(seed: int):
    employee_list = build_prismhr(seed)["responses"]["get_employee_list"]
    ids = employee_list["employeeList"]["employeeId"]
    pool = Pool(seed, "prismhr-deduction")
    responses = {
        ids[0]: prism_deductions_response([
            prism_benefit_deduction("MED", "Medical", "BCBSPPO1000", pool.money(40, 120)),
            prism_benefit_deduction("LIFE", "Life Insurance", "LIFESAL"),
            prism_deduction("401k", "K", "K", "401k", 5.0, use_percent=True, start="2016-12-01",
                            maximum=23000.0, basis="A"),
        ]),
        ids[1]: prism_deductions_response([
            prism_deduction("UNIF", "V", "F", "Uniforms", 12.5, limit=25.0, maximum=300.0, basis="L",
                            stopDate="2026-12-31", cutbackPayeeCode="UNIFCO"),
            prism_deduction("401KR", "KR", "PG", "Roth 401(k)", 4.0, use_percent=True, matchMethod="P",
                            matchAmount=50.0, matchDescription="Roth match"),
        ]),
        ids[2]: prism_deductions_response([
            prism_deduction("GARN", "G", "G", "Child Support", 180.0, loanOrGarnishId="G-1",
                            maximum=900.0, basis="M", cutbackPayeeCode="SDU"),
            prism_deduction("LOAN", "L", "F", "Employee Loan", 50.0, loanOrGarnishId="L-7",
                            matchMethod="F", matchAmount=10.0),
        ]),
        ids[3]: prism_deductions_response([
            prism_deduction("PARK", "Z", "ZZ", "Parking", 30.0, maximum=90.0, basis="Q"),  # undocumented
            prism_deduction("DUES", "V", "PPR", "Union Dues", 1.5, use_percent="T",  # spec prose T/F
                            maximum=100.0, basis="W"),  # undocumented basis
        ]),
        ids[4]: prism_deductions_response([]),  # no deductions, as live
        ids[5]: prism_deductions_response([
            prism_deduction("GYM", "V", "F", "Gym", 20.0, maximum=240.0),  # maximum with an empty basis
            prism_deduction("CHAR", "V", "F", "Charity", 5.0, use_percent="yes",  # not a boolean
                            start="2025-02-30"),  # invalid date
        ]),
        # ids[6] has no response -> missing_section
        "X00099": prism_deductions_response([], error_code="1", error_message="Employee not found"),
    }
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_deductions": responses,
        "get_employee_list": employee_list,
    })


# PrismHR payroll. Injected cases: batch types R, M, S and V; one batch status
# per group plus an undocumented one (HOLD); a batch with two pay groups, one
# with none and one with an empty payGroupId; voucher pages under the live key
# payrollVoucher and the spec key payrollVouchers; an arrears voucher with empty
# arrays; a voided voucher; pay classes E, R, F and an undocumented one; other
# earnings and other deductions; a direct deposit; the live-only hsaPeoMatch and
# isManualCheck; an undocumented voucher status on every voucher (reported once)
# and a second one; an error page; a voucher whose batch is not listed.

def prism_pay_group(group_id, start, end):
    return {"payGroupId": group_id, "payPeriodStartDate": start, "payPeriodEndDate": end,
            "weeksWorked": 1, "deductPeriod": "1"}


def prism_batch(batch_id, pay_date, batch_type, status, groups):
    return {"batchId": batch_id, "payDate": pay_date, "batchType": batch_type, "batchStatus": status,
            "payGroup": groups}


def prism_earning(code, pay_class, class_description, hours, rate, amount=None):
    return {"payCode": code, "payClass": pay_class, "payClassDescription": class_description, "chargeDate": "",
            "hoursUnits": hours, "hoursWorked": hours, "unitRate": rate,
            "payAmount": round(hours * rate, 2) if amount is None else amount,
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


def prism_voucher_page(vouchers, key="payrollVoucher"):
    return {"errorCode": "0", "errorMessage": "", "extension": None, key: vouchers,
            "total": len(vouchers), "startpage": 0, "count": len(vouchers)}


def build_prismhr_payroll(seed: int):
    ids = build_prismhr(seed)["responses"]["get_employee_list"]["employeeList"]["employeeId"]
    week1, week2 = ("2025-12-27", "2026-01-02"), ("2026-01-03", "2026-01-09")
    batches = [
        prism_batch("202601", "2026-01-09", "R", "COMP", [prism_pay_group("WFRI", *week1)]),
        prism_batch("202602", "2026-01-16", "R", "POSTCOMP", [prism_pay_group("WFRI", *week2)]),
        prism_batch("202603", "2026-01-20", "M", "INITFAIL", []),
        prism_batch("202604", "2026-01-23", "S", "TS.READY", [prism_pay_group("WFRI", "2026-01-10", "2026-01-16"),
                                                              prism_pay_group("SEMI", "2026-01-01", "2026-01-15")]),
        prism_batch("202605", "2026-01-30", "V", "HOLD", [prism_pay_group("", "2026-01-17", "2026-01-23")]),
    ]
    first = prism_voucher(
        "V000101", ids[0], "202601", "2026-01-09", week1, gross=1076.41, net=891.38, checkNumber="1001",
        checkAmt=891.38, hsaPeoMatch=0.0, isManualCheck=False,
        earning=[prism_earning("REG", "E", "Earnings", 40, 25.0), prism_earning("OT", "E", "Earnings", 2, 37.5)],
        otherEarningsDetail=[{"otherEarnCode": "FRINGE", "otherEarnsDesc": "Fringe Benefit", "otherEarnAmount": 1.41}],
        employeeTax=[prism_employee_tax("00-10", "Federal Income Tax", 986.41, 80.0),
                     prism_employee_tax("00-11", "Medicare", 1036.41, 15.03)],
        companyTax=[prism_company_tax("00-15", "Medicare - Employer", 1036.41, 15.03)],
        deduction=[prism_voucher_deduction("401k", "K", "401k", 50.0),
                   prism_voucher_deduction("MED", "C", "Medical", 40.0)],
        employerContributions=[{"code": "MED", "description": "Medical", "amount": 189.17},
                               {"code": "EAP", "description": "Employee Assistance", "amount": 0.0}],
        benefit=[{"planId": "MED", "premiumAmt": 229.17, "empContrib": 189.17, "empDeduct": 40.0,
                  "coveragePeriod": "M", "adjRef": "", "premiumCost": 229.17}],
    )
    second = prism_voucher(
        "V000102", ids[1], "202601", "2026-01-09", week1, gross=297.0, net=242.0,
        earning=[prism_earning("VAC", "E", "Earnings", 8, 30.0),
                 prism_earning("EXP", "R", "Expense Reimbursement", 1, 45.0),
                 prism_earning("MILES", "Q", "Mileage", 1, 12.0)],  # undocumented pay class
        employeeTax=[prism_employee_tax("00-10", "Federal Income Tax", 252.0, 20.0)],
        deduction=[prism_voucher_deduction("CLUB", "ZZ", "Social Club", 10.0)],  # undocumented type
        otherDeduction=[{"otherDeductCode": "UNIF", "otherDeductDescription": "Uniforms", "otherDeductAmount": 25.0,
                         "otherDeductOneTimeSwitch": "N"}],
        directDeposit=[{"transitNum": "991234567", "accountNum": "000123456789", "status": "A", "amount": 242.0}],
    )
    arrears = prism_voucher("V000103", ids[2], "202601", "2026-01-09", week1, voucher_type="A")
    voided = prism_voucher(
        "V000201", ids[0], "202602", "2026-01-16", week2, voucher_type="S", gross=500.0, net=500.0,
        checkNumber="1002", checkAmt=500.0, voidDate="2026-01-20", voidVoucherId="V000202",
        earning=[prism_earning("BON", "E", "Earnings", 0, 0.0, amount=500.0)],
    )
    orphan = prism_voucher("V000901", ids[3], "202699", "2026-02-06", ("2026-01-24", "2026-01-30"),
                           voucher_type="J", status="PEND")
    return bundle("prismhr", {"client_id": PRISM_CLIENT_ID}, {
        "get_batch_list_by_date": {"errorCode": "0", "errorMessage": "", "extension": None, "batchList": batches},
        "get_payroll_voucher_for_batch": {
            "202601": [prism_voucher_page([first, second]), prism_voucher_page([arrears], key="payrollVouchers")],
            "202602": [prism_voucher_page([voided])],
            "202603": [{"errorCode": "1", "errorMessage": "No vouchers found for batch", "extension": None}],
            "202699": [prism_voucher_page([orphan])],
        },
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
    office = pool.address()
    master = {
        "id": PRISM_CLIENT_ID, "clientName": "Synthetic Demo Staffing", "legalName": "Synthetic Demo Staffing LLP",
        "serviceType": "PEO", "categoryCode": "", "costCenter": "", "statusClass": "A", "status": "A",
        "statusDate": "2019-04-01", "corporationType": "M", "addressLine1": office["line1"], "addressLine2": "Suite 200",
        "city": office["city"], "stateCode": office["state"], "zipCode": office["zip"], "zipSuffix": "1234",
        "mainPhone": pool.phone(), "mainPhoneExt": "101", "fax": "", "websiteUrl": "https://staffing.example",
        "emailAddress": "payroll@staffing.example", "businessDescription": "Temporary staffing", "sicCode": "7363",
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


# isolved direct deposits: one /directdeposits array per employee id.
# Injected cases: inactive lines without a sequence (one with neither amount
# nor percent: inconsistent_allocation), off-allowlist "Savings" and
# "Pending" (unmapped_label), both amount and percent set and a sequence 0
# line with an amount (inconsistent_allocation), an empty array (the live
# 404), and an employee with no entry (missing_section).

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
    deposits = {
        ids[0]: [isolved_deposit(pool, 640101, 0)],
        ids[1]: [isolved_deposit(pool, 640102, 1, amount=200.0), isolved_deposit(pool, 640103, 0)],
        ids[2]: [isolved_deposit(pool, 640104, None, status="Inactive"),  # neither amount nor percent
                 isolved_deposit(pool, 640105, None, status="Inactive", amount=500.0)],
        ids[3]: [isolved_deposit(pool, 640106, 1, percent=25.0, account_type="Savings"),
                 isolved_deposit(pool, 640107, 2, status="Pending", amount=50.0, percent=10.0),
                 isolved_deposit(pool, 640108, 0, amount=10.0)],
        ids[4]: [],  # live answers 404 for an employee with no deposits
        # ids[5] has no entry -> missing_section
    }
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": employees,
        "direct_deposits": deposits,
    })


# isolved deductions: one /payItems array per employee id, mixing Deduction,
# Earning and Memo Calc items as live. Injected cases: Amount and Percent
# parameters, an "Amount2" and a "Rate" parameter (unmapped_label, once each),
# a deduction with no code (as live), the live-only "balance" field
# (spec_live_mismatch), an invalid stopDate (invalid_date), an unknown
# payItemType (unmapped_label, skipped), an empty array (the 404) and an
# employee with no entry (missing_section).

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

    def common(person, first_id):
        return [isolved_pay_item(person, first_id, "Earning", "13", "Bonus", [("Amount", 0.0)]),
                isolved_pay_item(person, first_id + 1, "Memo Calc", "001", "401k Match", [])]

    pay_items = {
        str(people[0]["id"]): common(people[0], 770101) + [
            isolved_pay_item(people[0], 770103, "Deduction", "030", "Medical Pre-tax",
                             [("Amount", pool.money(60, 140))], start="2024-01-01"),
            isolved_pay_item(people[0], 770104, "Deduction", "32", "401K", [("Amount", 0.0), ("Percent", 6.0)],
                             start="2023-04-01"),
        ],
        str(people[1]["id"]): common(people[1], 770201) + [
            isolved_pay_item(people[1], 770203, "Deduction", "011W", "United Way",
                             [("Amount", 10.0), ("Amount2", 0.0), ("Percent", 0.0)],
                             start="2025-01-01", stop="2025-12-31", balance=0.0),  # live-only field
            isolved_pay_item(people[1], 770204, "Deduction", None, "FSA Medical pos", [("Amount", 41.67)]),
        ],
        str(people[2]["id"]): common(people[2], 770301) + [
            isolved_pay_item(people[2], 770303, "Deduction", "006", "401K Loan", [], start="2022-06-01",
                             stop="2025-02-30"),  # invalid date
            isolved_pay_item(people[2], 770304, "Benefit", "HSA", "HSA Pre-tax", [("Amount", 50.0)]),  # unknown type
        ],
        str(people[3]["id"]): [],  # live answers 404 for an employee with no pay items
        # people[4] has no entry -> missing_section
        str(people[5]["id"]): common(people[5], 770601) + [
            isolved_pay_item(people[5], 770603, "Deduction", "008", "Vision Pre-tax", [("Rate", 1.25), ("Amount", 0.0)]),
        ],
    }
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": employees,
        "pay_items": pay_items,
    })


# isolved payroll: the run history of one pay group, paged /checks per employee
# and /checks/{id} detail for some checks. Injected cases: a run type and a run
# status off the allowlists (unmapped_label), two runs sharing a pay date and
# run number (the check that would join them gets no run), a check that joins
# no run, checks with and without detail (missing_section), memo earnings, a
# garnishment, benefits with and without an employer contribution, a
# non-boolean isEmployeeTax (out_of_schema_value), check and direct deposit
# payments, a reissued check, a check type off the allowlist, an employee with
# an empty page and one missing from the map (missing_section).

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
    runs = [
        isolved_run(4100001, "2026-01-09", 1, "Regular Payroll", "Completed Payroll Run", period,
                    "1st Payroll of Month"),
        isolved_run(4100002, "2026-01-23", 0, "Regular Payroll", "Payroll Not Processed"),
        isolved_run(4100003, "2026-01-09", 2, "Data Conversion", "Completed Payroll Run"),  # off-allowlist type
        isolved_run(4100004, "2026-02-06", 1, "Regular Payroll", "Payroll Voided"),  # off-allowlist status
        isolved_run(4100005, "2026-02-06", 1, "Regular Payroll", "Completed Payroll Run"),  # same slot as 4100004
    ]
    first = isolved_check(
        pool, people[0], 21000101, 5001, "2026-01-09", 1, "Adjustment", 1500.0, 1164.67,
        deposit_amount=1164.67, period=period,
        earnings=[isolved_earning(1, "01", "Regular", 80.0, 1450.0),
                  isolved_earning(2, "14", "Commission", 0.0, 50.0),
                  isolved_earning(3, "001", "401k Match", 0.0, 45.0, memo=True)],
        deductions=[isolved_item(4, "030", "Medical Pre-tax", 90.33), isolved_item(5, "32", "401K", 75.0)],
        garnishments=[isolved_item(6, "GARN", "Child Support", 50.0)],
        directDeposits=[{"id": 7, "account": "000987654321", "depositAmount": 1164.67,
                         "itemDescription": "Checking", "links": []}],
    )
    reissued = isolved_check(
        pool, people[0], 21000102, 5002, "2026-01-23", 0, "Adjustment", 1080.0, 1080.0, check_amount=1080.0,
        reissueCheckDate="2026-01-27T00:00:00", reissueCheckNumber=5010,
        earnings=[isolved_earning(8, "01", "Regular", 80.0, 1080.0)],
    )
    manual = isolved_check(pool, people[1], 21000201, 5101, "2026-02-06", 1, "Manual Check", 400.0, 360.32,
                           check_amount=360.32, earnings=[isolved_earning(9, "01", "Regular", 16.0, 400.0)])
    unjoined = isolved_check(pool, people[2], 21000301, 5201, "2026-03-06", 9, "Adjustment", 190.0, 190.0,
                             deposit_amount=190.0)
    converted = isolved_check(pool, people[5], 21000601, 5601, "2026-01-09", 2, "Adjustment", 300.0, 300.0,
                              check_amount=300.0, earnings=[isolved_earning(10, "01", "Regular", 12.0, 300.0)])
    checks = {
        str(people[0]["id"]): [isolved_page([first, reissued], 1, 1, 2)],
        str(people[1]["id"]): [isolved_page([manual], 1, 1, 1)],
        str(people[2]["id"]): [isolved_page([unjoined], 1, 1, 1)],
        str(people[3]["id"]): [isolved_page([], 1, 1, 0)],  # no checks
        # people[4] has no entry -> missing_section
        str(people[5]["id"]): [isolved_page([converted], 1, 1, 1)],
    }
    details = {
        str(first["id"]): isolved_check_detail(
            first,
            taxes=[isolved_tax(11, "FEDERAL WH", True, 120.0, 1334.67),
                   isolved_tax(12, "SOC SEC ER", False, 93.0, 1500.0)],
            benefits=[isolved_benefit("401(k)", 75.0, 45.0), isolved_benefit("Leave Accrual", 0.0, 0.0)]),
        str(manual["id"]): isolved_check_detail(
            manual, taxes=[isolved_tax(13, "FEDERAL WH", "yes", 39.68, 400.0)]),  # not a boolean
        str(converted["id"]): isolved_check_detail(converted),
    }
    return bundle("isolved", {"client_id": ISOLVED_CLIENT_ID, "legal_id": ISOLVED_LEGAL_ID}, {
        "employees": employees,
        "payroll_run_history": {ISOLVED_PAY_GROUP: runs},
        "checks": checks,
        "check_detail": details,
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


# UKG Ready direct deposits: one /direct-deposits response per account id.
# Injected cases: every calc_method type, an inactive line, a short account
# number (invalid_number), account_type MONEY_MARKET (out_of_schema_value),
# invalid active_from (invalid_date), a RESERVE_LIVE_CHECK line with no bank
# fields, FLAT_AMOUNT without an amount (inconsistent_allocation), an empty
# deposits list, and an employee with no response (missing_section).

UKG_CALC_NAMES = {"FULL": "Entire/Remainder", "FLAT_AMOUNT": "Flat $ Amount", "NET_PAY": "% Of Net Pay",
                  "GROSS_EARNING": "% Of Gross Earnings", "DIRECT_DEPOSIT_PER_OF_REMAINDER": "% Of Remainder"}


def ukg_deposit(pool: Pool, deposit_id: int, sequence: int, calc: str, amount=None, percentage=None,
                account_type="CHECKING", active=True, active_from="2020-08-06", active_to="2099-12-31",
                pre_note="READY_TO_SEND", kind="DIRECT_DEPOSIT", account_digits=None, bank=True):
    base = f"{UKG_BASE}/direct-deposits/{deposit_id}"
    line = {"id": deposit_id, "sequence": sequence, "type": kind, "active_from": active_from,
            "active_to": active_to, "active": active}
    if amount is not None:
        line["amount"] = amount
    if percentage is not None:
        line["percentage"] = percentage
    line["calc_method"] = {"display_name": UKG_CALC_NAMES[calc], "type": calc}
    if bank:
        line.update({"account_type": account_type,
                     "account_number": pool.account(account_digits or pool.rng.randint(6, 11)),
                     "routing_number": pool.routing(), "routing_type": "ABA", "pre_note_status": pre_note})
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
    deposits = {
        ids[0]: ukg_deposits_response([ukg_deposit(pool, 47480101, 1, "FULL", active_from="1900-12-31")]),
        ids[1]: ukg_deposits_response([
            ukg_deposit(pool, 47480102, 1, "FLAT_AMOUNT", amount=1000.0, pre_note="CANCELED"),
            ukg_deposit(pool, 47480103, 2, "NET_PAY", percentage=15.0, account_type="SAVINGS"),
            ukg_deposit(pool, 47480104, 3, "FULL", pre_note="COMPLETE_EXPIRED"),
        ]),
        ids[2]: ukg_deposits_response([
            ukg_deposit(pool, 47480105, 1, "FULL", active=False, active_from="1900-12-31",
                        active_to="2017-07-13", pre_note="CANCELED", account_digits=3),  # short number
            ukg_deposit(pool, 47480106, 2, "GROSS_EARNING", percentage=10.0),
        ]),
        ids[3]: ukg_deposits_response([
            ukg_deposit(pool, 47480107, 1, "DIRECT_DEPOSIT_PER_OF_REMAINDER", percentage=50.0,
                        account_type="MONEY_MARKET", active_from="2025-02-30"),
            ukg_deposit(pool, 47480108, 2, "FULL", kind="RESERVE_LIVE_CHECK", bank=False),
        ]),
        # ids[4] has no response -> missing_section
        ids[5]: ukg_deposits_response([
            ukg_deposit(pool, 47480109, 1, "FLAT_AMOUNT"),  # amount missing
            ukg_deposit(pool, 47480110, 2, "FULL"),
        ]),
    }
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "employees": employees,
        "direct_deposits": deposits,
    })


# UKG Ready deductions: one /deductions list per account id plus one
# /deductions/{id} detail per line. The live tenant answers "Unresolvable URL"
# for these calls, so shapes follow the cached reference pages only. Injected
# cases: an amount and a percent method, a method type seen twice
# (undocumented_code once), both amount and percent set
# (inconsistent_allocation), frequencies with no canonical counterpart
# (other) and one outside the schema enum (out_of_schema_value), a line with
# no detail (missing_section), an invalid effective_from (invalid_date), the
# open-ended 9999-12-31, an empty list and an employee with no response.

UKG_FREQUENCY_NAMES = {"EVERY_SCHEDULED_PAY": "Every Scheduled Pay", "EVERY_PAY": "Every Pay",
                       "BENEFIT_PLAN": "Benefit Plan", "EVERY_SCHEDULED_MONTH_ODD_PAY": "Every Scheduled Month Odd Pay",
                       "HOLIDAY_TABLE": "Holiday Table", "WEEKLY": "Weekly"}
UKG_DEDUCTION_METHODS = {"EARNING_LIST": "% Of Earnings List", "FLAT_AMOUNT": "Flat $ Amount"}


def ukg_deduction_line(deduction_id, code, name, sequence, effective_from="2024-01-01",
                       effective_to="9999-12-31"):
    return {"id": deduction_id, "deduction": {"name": name, "code": code}, "effective_from": effective_from,
            "effective_to": effective_to, "sequence": sequence,
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
    lines = {
        ids[0]: [ukg_deduction_line(197121, "401k", "401k", 1, effective_from="2017-04-12"),
                 ukg_deduction_line(197122, "Child Support", "Child Support", 2)],
        ids[1]: [ukg_deduction_line(197131, "Medical", "Medical", 1),
                 ukg_deduction_line(197132, "Union Dues", "Union Dues", 2, effective_to="2026-06-30")],
        ids[2]: [ukg_deduction_line(197141, "Gym", "Gym", 1),
                 ukg_deduction_line(197142, "Parking", "Parking", 2)],  # no detail captured
        ids[3]: [],
        # ids[4] has no response -> missing_section
        ids[5]: [ukg_deduction_line(197161, "Holiday Club", "Holiday Club", 1, effective_from="2025-13-01")],
    }
    details = [
        ukg_deduction_detail(lines[ids[0]][0], "EVERY_SCHEDULED_PAY", "EARNING_LIST", percent=6, annual_max=23000,
                             er_annual_max=5000, vendor={"id": 65792, "name": "Retirement Vendor"}, max_amount=500),
        ukg_deduction_detail(lines[ids[0]][1], "EVERY_PAY", "FLAT_AMOUNT", amount=150,
                             vendor={"id": 65793, "name": "State Disbursement Unit"}),
        ukg_deduction_detail(lines[ids[1]][0], "BENEFIT_PLAN", "FLAT_AMOUNT", amount=pool.rng.randint(60, 140)),
        ukg_deduction_detail(lines[ids[1]][1], "EVERY_SCHEDULED_MONTH_ODD_PAY", "FLAT_AMOUNT", amount=20),
        ukg_deduction_detail(lines[ids[2]][0], "WEEKLY", "FLAT_AMOUNT", amount=15, percent=2),  # both set
        ukg_deduction_detail(lines[ids[5]][0], "HOLIDAY_TABLE", "FLAT_AMOUNT", amount=25, vendor={"id": 65794}),
    ]
    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "employees": employees,
        "deductions": {aid: {"deductions": items} for aid, items in lines.items()},
        "deduction_detail": {str(detail["id"]): detail for detail in details},
    })


# UKG Ready payroll: the /payrolls list, /pay-statements per payroll id and the
# statement detail per statement id. Injected cases: payroll statuses of each
# group plus one outside the enum (out_of_schema_value), a payroll type and a
# statement type off the allowlist (unmapped_label), a payroll with no
# statements entry and one with an empty list, a statement with no detail
# (missing_section), hours in milliseconds and one that is not a number
# (invalid_number), deductions with both amounts, the employee amount only,
# the employer amount only and a discarded one, both payment types and an
# unknown one, the live-only calcUpto and emptyEarning, and a statement whose
# payroll is not listed. No statement carries gross or net totals.

UKG_PAYROLL = f"{UKG_BASE}/payrolls"
UKG_EIN = {"id": 35419520, "ein_name": "Primary EIN", "ein_tax_id": "12-3456789"}


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


def ukg_statement_deduction(line_id, code, name, ee=None, er=None, type_name="Deduction (Auto)"):
    line = {"id": line_id, "type_name": type_name, "batch": {"id": 1, "display_name": "Auto"},
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


def ukg_detail(statement, earnings=(), deductions=(), taxes=(), payments=(), messages=()):
    detail = {k: v for k, v in statement.items() if k not in ("calcUpto", "emptyEarning", "_links")}
    detail.update(earnings=list(earnings), deductions=list(deductions), taxes=list(taxes),
                  messages=list(messages), payments=list(payments))
    return detail


def build_ukg_payroll(seed: int):
    ids = [r["id"] for r in build_ukg(seed)["responses"]["employees"]["employees"]]
    period = ("2025-12-21", "2026-01-03")
    payrolls = [
        ukg_payroll(4332470001, "Primary-EIN Regular Bi-Weekly 01/09/2026", "FINALIZED", "2026-01-09", *period),
        ukg_payroll(4332470002, "Correction 01/16/2026", "OPEN", "2026-01-16", *period, type_id=706,
                    type_name="Correction"),  # off-allowlist type
        ukg_payroll(4332470003, "Paused run", "PAUSED", "2026-01-23", "2026-01-04", "2026-01-17"),  # not in enum
        ukg_payroll(4332470004, "Failed close", "CLOSE_FAILED", "2026-02-06", "2026-01-18", "2026-01-31"),
    ]
    first = ukg_statement(85940001, ids[0], 4332470001, "FINALIZED", "2026-01-09", *period)
    gross_up = ukg_statement(85940002, ids[1], 4332470001, "OPEN", "2026-01-09", *period, type_id=36656002,
                             type_name="Gross Up")  # off-allowlist type
    no_detail = ukg_statement(85940003, ids[2], 4332470001, "CLOSED", "2026-01-09", *period)
    invalid = ukg_statement(85940004, ids[3], 4332470002, "INVALID", "2026-01-16", *period)
    orphan = ukg_statement(85940005, ids[4], 4332479999, "NEW", "2026-02-20", "2026-02-01", "2026-02-14")
    details = [
        ukg_detail(
            first,
            earnings=[ukg_earning(1, "REG", "Regular", 288_000_000, 25.0, 2000.0),
                      ukg_earning(2, "OT", "Overtime", 7_200_000, 37.5, 75.0)],
            deductions=[ukg_statement_deduction(3, "401k", "401k", ee=120.0, er=60.0),
                        ukg_statement_deduction(4, "S125_Med", "Medical", ee=45.5, er=0.0),
                        ukg_statement_deduction(5, "ER_HSA", "HSA Employer", ee=0.0, er=25.0),
                        ukg_statement_deduction(6, "401K Loan 1", "401K Loan 1", ee=30.0,
                                                type_name="Deduction (Discarded)")],
            taxes=[ukg_statement_tax(7, "FIT", "Federal Income Tax", 210.0, 0.0, 1954.5),
                   ukg_statement_tax(8, "SS", "Social Security", 128.65, 128.65, 2075.0)],
            payments=[{"id": 9, "hours": 0, "quantity": 0, "ee_amount": 1500.0, "type_name": "Direct Deposit",
                       "batch": {"id": 1, "display_name": "Auto"}},
                      {"id": 10, "hours": 0, "quantity": 0, "ee_amount": 40.85, "type_name": "Check",
                       "batch": {"id": 1, "display_name": "Auto"}}],
            messages=[{"id": 11, "type_name": "Message", "message": {"text": "Synthetic note", "severity": "INFO"},
                       "batch": {"id": 1, "display_name": "Auto"}}]),
        ukg_detail(
            gross_up,
            earnings=[ukg_earning(12, "REG", "Regular", "eight hours", 20.0, 160.0)],  # not a number
            payments=[{"id": 13, "hours": 0, "quantity": 0, "ee_amount": 160.0, "type_name": "Pay Card",
                       "batch": {"id": 1, "display_name": "Auto"}}]),
        ukg_detail(invalid),
        ukg_detail(orphan, earnings=[ukg_earning(14, "REG", "Regular", 144_000_000, 25.0, 1000.0)]),
    ]

    def listing(*statements):
        return {"pay_statements": list(statements)}

    return bundle("ukg-ready", {"company_id": UKG_COMPANY_ID}, {
        "payrolls": {"payrolls": payrolls},
        "pay_statements": {
            "4332470001": listing(first, gross_up, no_detail),
            "4332470002": listing(invalid),
            # 4332470003 has no entry -> missing_section
            "4332470004": listing(),
            "4332479999": listing(orphan),  # payroll not in the list
        },
        "pay_statement_detail": {str(detail["id"]): detail for detail in details},
        "lookup_eins": {"items": [dict(UKG_EIN, ein_country_id="USA")]},
    })


BUILDERS = {
    "prismhr": {"company": build_prismhr_company, "employee": build_prismhr,
                "direct-deposit": build_prismhr_direct_deposits, "deduction": build_prismhr_deductions,
                "payroll": build_prismhr_payroll},
    "isolved": {"employee": build_isolved, "direct-deposit": build_isolved_direct_deposits,
                "deduction": build_isolved_deductions, "payroll": build_isolved_payroll},
    "ukg-ready": {"employee": build_ukg, "direct-deposit": build_ukg_direct_deposits,
                  "deduction": build_ukg_deductions, "payroll": build_ukg_payroll},
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
