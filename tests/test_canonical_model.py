"""Canonical model: strict construction, serialization, and schema agreement."""
import dataclasses
import typing
import unittest
from datetime import date
from decimal import Decimal

from _fixtures import ENTITIES, PROVIDERS, expected_output, schema
from normalization.canonical import (
    AccountType,
    Address,
    AddressKind,
    Allocation,
    AllocationMethod,
    Calculation,
    CalculationMethod,
    CodedValue,
    Company,
    CompanySource,
    CompanyStatus,
    Compensation,
    Contact,
    ContributionLine,
    DateRange,
    Deduction,
    DeductionLine,
    DeductionSource,
    DepositSource,
    DirectDeposit,
    EarningLine,
    Employee,
    Employment,
    EmploymentStatus,
    Gender,
    Issue,
    IssueCode,
    Job,
    Limits,
    Money,
    NormalizedOutput,
    Paycheck,
    PaycheckSource,
    Payee,
    PayGroup,
    PaymentLine,
    PaymentMethod,
    PayRun,
    PayRunSource,
    PayType,
    Person,
    Severity,
    SourceRef,
    TaxId,
    TaxLine,
    WorkLocation,
)
from normalization.canonical import common, company, deduction, direct_deposit, employee, issues, payroll
from normalization.canonical.schema_check import validate


def minimal_employee(**overrides) -> Employee:
    fields = dict(
        key="prismhr:132:A1", company_key="prismhr:132",
        source=SourceRef(provider="prismhr", company_id="132", employee_id="A1"),
        person=Person(), contact=Contact(), employment=Employment(), job=Job(),
        compensation=Compensation(),
    )
    fields.update(overrides)
    return Employee(**fields)


class ConstructionChecks(unittest.TestCase):
    def test_wrong_scalar_type_is_rejected_without_coercion(self):
        with self.assertRaises(TypeError):
            Person(birth_date="2000-01-01")
        with self.assertRaises(TypeError):
            Money(amount="12.50")
        with self.assertRaises(TypeError):
            Compensation(standard_hours=40.0)

    def test_bool_is_not_accepted_where_int_is_declared(self):
        with self.assertRaises(TypeError):
            CodedValue(raw=True)

    def test_enum_member_must_belong_to_declared_enum(self):
        with self.assertRaises(TypeError):
            CodedValue(raw="A", value="active")
        CodedValue(raw="A", value=EmploymentStatus.ACTIVE)

    def test_nested_models_and_lists_are_checked(self):
        with self.assertRaises(TypeError):
            Contact(addresses=[{"kind": "home"}])
        with self.assertRaises(TypeError):
            minimal_employee(person={"first_name": "x"})

    def test_models_are_frozen(self):
        person = Person(first_name="Ada")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            person.first_name = "Grace"

    def test_every_canonical_enum_ends_with_unknown(self):
        for module in (common, company, direct_deposit, deduction, payroll, issues):
            for name in dir(module):
                member = getattr(module, name)
                if isinstance(member, type) and issubclass(member, common.CanonicalEnum) \
                        and member is not common.CanonicalEnum:
                    self.assertEqual(list(member)[-1].value, "unknown", name)

    def test_direct_deposit_fields_are_checked(self):
        source = DepositSource(provider="isolved", company_id="4046-5806", employee_id="1", deposit_id="9")
        record = DirectDeposit(key="isolved:4046-5806:1:dd:9", employee_key="isolved:4046-5806:1",
                               company_key="isolved:4046-5806", source=source,
                               account_type=CodedValue("Checking", None, AccountType.CHECKING),
                               allocation=Allocation(method=CodedValue(None, "amount", AllocationMethod.FIXED_AMOUNT),
                                                     amount=Money(Decimal("200.00"))),
                               priority=1, effective=DateRange(start=date(2020, 8, 6)))
        self.assertEqual(record.to_dict()["allocation"]["amount"], {"amount": "200.00", "currency": "USD"})
        with self.assertRaises(TypeError):
            Allocation(percent=25.0)
        with self.assertRaises(TypeError):
            DirectDeposit(key="k", employee_key="e", company_key="c", source=source, priority=True)

    def test_deduction_fields_are_checked(self):
        source = DeductionSource(provider="prismhr", company_id="132", employee_id="J1", deduction_id="0")
        record = Deduction(key="prismhr:132:J1:ded:0", employee_key="prismhr:132:J1", company_key="prismhr:132",
                           source=source, code=CodedValue("401k", "401k"),
                           calculation=Calculation(method=CodedValue("K", "Retirement Plan",
                                                                     CalculationMethod.RETIREMENT_PLAN_RULE),
                                                   percent=Decimal("5.0")),
                           limits=Limits(annual=Money(Decimal("23000"))), payee=Payee(id="FIDELITY"),
                           effective=DateRange(start=date(2016, 12, 1)))
        data = record.to_dict()
        self.assertEqual(data["calculation"]["percent"], "5.0")
        self.assertEqual(data["limits"]["annual"], {"amount": "23000", "currency": "USD"})
        self.assertIsNone(data["employer_match"])
        with self.assertRaises(TypeError):
            Calculation(amount=Decimal("5"))
        with self.assertRaises(TypeError):
            Limits(per_pay=100)

    def test_payroll_fields_are_checked(self):
        source = PaycheckSource(provider="ukg-ready", company_id="33704016", employee_id="1", paycheck_id="9")
        check = Paycheck(key="ukg-ready:33704016:1:chk:9", employee_key="ukg-ready:33704016:1",
                         company_key="ukg-ready:33704016", source=source, pay_date=date(2026, 1, 9),
                         earnings=[EarningLine(hours=Decimal("80.00"), amount=Money(Decimal("2000")))],
                         taxes=[TaxLine(employer_amount=Money(Decimal("128.65")))],
                         deductions=[DeductionLine(amount=Money(Decimal("45.5")))],
                         employer_contributions=[ContributionLine(amount=Money(Decimal("60")))],
                         payments=[PaymentLine(method=CodedValue("Check", None, PaymentMethod.CHECK))])
        data = check.to_dict()
        self.assertEqual(data["earnings"][0]["hours"], "80.00")
        self.assertIsNone(data["pay_run_key"])
        self.assertEqual(data["payments"][0]["method"]["value"], "check")
        with self.assertRaises(TypeError):
            EarningLine(hours=80)
        with self.assertRaises(TypeError):
            Paycheck(key="k", employee_key="e", company_key="c", source=source, earnings=[TaxLine()])
        run = PayRun(key="prismhr:132:run:20161", company_key="prismhr:132",
                     source=PayRunSource(provider="prismhr", company_id="132", pay_run_id="20161"))
        self.assertEqual(run.to_dict()["unmapped"], {})

    def test_company_fields_are_checked(self):
        source = CompanySource(provider="isolved", company_id="4046-5806")
        stub = Company(key="isolved:4046-5806", source=source).to_dict()
        self.assertEqual((stub["tax_ids"], stub["work_locations"], stub["pay_groups"], stub["unmapped"]),
                         ([], [], [], {}))
        self.assertIsNone(stub["status"])
        record = Company(
            key="isolved:4046-5806", source=source, legal_name="Example Co",
            status=CodedValue("Active", None, CompanyStatus.ACTIVE),
            address=Address(kind=AddressKind.LEGAL, line1="200 State St"),
            tax_ids=[TaxId(key="isolved:4046-5806:ein:568888888", tax_id="568888888")],
            work_locations=[WorkLocation(key="isolved:4046-5806:loc:25721", source_id="25721", active=True)],
            pay_groups=[PayGroup(key="isolved:4046-5806:pg:7627", source_id="7627",
                                 effective=DateRange(start=date(2018, 1, 21)))],
        )
        data = record.to_dict()
        self.assertEqual(data["address"]["kind"], "legal")
        self.assertEqual(data["status"]["value"], "active")
        self.assertEqual(data["pay_groups"][0]["effective"], {"start": "2018-01-21", "end": None})
        with self.assertRaises(TypeError):
            WorkLocation(key="k", source_id=1)
        with self.assertRaises(TypeError):
            Company(key="k", source=source, work_locations=[PayGroup(key="k", source_id="1")])
        with self.assertRaises(TypeError):
            Company(key="k", source=source, status_date="2016-12-01")


class SerializationChecks(unittest.TestCase):
    def test_to_dict_renders_dates_decimals_and_enums(self):
        record = minimal_employee(
            person=Person(birth_date=date(1990, 5, 17), gender=CodedValue("F", None, Gender.FEMALE)),
            compensation=Compensation(hourly_rate=Money(Decimal("12.5000")), standard_hours=Decimal("40.00"),
                                      pay_type=CodedValue("H", None, PayType.HOURLY)),
            contact=Contact(addresses=[Address(kind=AddressKind.HOME, line1="1 Main St")]),
        )
        data = record.to_dict()
        self.assertEqual(data["person"]["birth_date"], "1990-05-17")
        self.assertEqual(data["person"]["gender"], {"raw": "F", "label": None, "value": "female"})
        self.assertEqual(data["compensation"]["hourly_rate"], {"amount": "12.5000", "currency": "USD"})
        self.assertEqual(data["compensation"]["standard_hours"], "40.00")
        self.assertEqual(data["contact"]["addresses"][0]["kind"], "home")
        self.assertIsNone(data["employment"]["status"])

    def test_output_round_trips_through_json(self):
        import json
        output = NormalizedOutput(provider="prismhr",
                                  company=Company(key="prismhr:132",
                                                  source=CompanySource(provider="prismhr", company_id="132")),
                                  employees=[minimal_employee()],
                                  issues=[Issue(IssueCode.MASKED_VALUE, Severity.INFO, "a.b", "set null")])
        text = json.dumps(output.to_dict(), allow_nan=False)
        self.assertEqual(json.loads(text), output.to_dict())


class SchemaAgreementChecks(unittest.TestCase):
    """Dataclass fields and the hand-written JSON Schema must not drift apart."""

    MODELS = {
        "NormalizedOutput": issues.NormalizedOutput, "Issue": issues.Issue,
        "Company": company.Company, "CompanySource": company.CompanySource,
        "TaxId": company.TaxId, "WorkLocation": company.WorkLocation, "PayGroup": company.PayGroup,
        "Employee": employee.Employee, "SourceRef": employee.SourceRef, "Person": employee.Person,
        "Contact": employee.Contact, "Employment": employee.Employment, "Job": employee.Job,
        "Compensation": employee.Compensation, "CodedValue": common.CodedValue,
        "Address": common.Address, "Phone": common.Phone, "Email": common.Email, "Money": common.Money,
        "DateRange": common.DateRange, "DirectDeposit": direct_deposit.DirectDeposit,
        "DepositSource": direct_deposit.DepositSource, "Allocation": direct_deposit.Allocation,
        "Deduction": deduction.Deduction, "DeductionSource": deduction.DeductionSource,
        "Calculation": deduction.Calculation, "Limits": deduction.Limits,
        "EmployerMatch": deduction.EmployerMatch, "Payee": deduction.Payee,
        "PayRun": payroll.PayRun, "PayRunSource": payroll.PayRunSource,
        "Paycheck": payroll.Paycheck, "PaycheckSource": payroll.PaycheckSource,
        "EarningLine": payroll.EarningLine, "TaxLine": payroll.TaxLine,
        "DeductionLine": payroll.DeductionLine, "ContributionLine": payroll.ContributionLine,
        "PaymentLine": payroll.PaymentLine,
    }

    def test_each_model_field_set_matches_schema_properties(self):
        defs = schema()["$defs"]
        for name, model in self.MODELS.items():
            with self.subTest(model=name):
                field_names = [f.name for f in dataclasses.fields(model)]
                self.assertEqual(sorted(defs[name]["properties"]), sorted(field_names))
                self.assertEqual(sorted(defs[name]["required"]), sorted(field_names))

    def test_optional_fields_are_nullable_in_schema(self):
        defs = schema()["$defs"]
        for name, model in self.MODELS.items():
            hints = typing.get_type_hints(model)
            for field in dataclasses.fields(model):
                optional = type(None) in typing.get_args(hints[field.name])
                prop = defs[name]["properties"][field.name]
                with self.subTest(model=name, field=field.name):
                    self.assertEqual(optional, _schema_allows_null(prop, defs),
                                     f"{name}.{field.name}: optional={optional} schema={prop}")

    def test_golden_outputs_validate_against_schema(self):
        for provider in PROVIDERS:
            for entity in ENTITIES:
                with self.subTest(provider=provider, entity=entity):
                    self.assertEqual(validate(expected_output(provider, entity), schema()), [])

    def test_schema_enums_match_canonical_enums(self):
        defs = schema()["$defs"]
        self.assertEqual(defs["Issue"]["properties"]["code"]["enum"], [member.value for member in IssueCode])

    def test_validator_reports_violations(self):
        output = expected_output("prismhr")
        output["employees"][0]["person"]["birth_date"] = "20000101"
        output["employees"][0]["extra"] = 1
        output["issues"][0]["severity"] = "fatal"
        errors = validate(output, schema())
        self.assertTrue(any("birth_date" in e for e in errors))
        self.assertTrue(any("extra" in e for e in errors))
        self.assertTrue(any("severity" in e for e in errors))


def _schema_allows_null(prop: dict, defs: dict) -> bool:
    if "$ref" in prop:
        return _schema_allows_null(defs[prop["$ref"].rsplit("/", 1)[-1]], defs)
    if "oneOf" in prop:
        return any(_schema_allows_null(alt, defs) for alt in prop["oneOf"])
    declared = prop.get("type")
    return declared == "null" or (isinstance(declared, list) and "null" in declared)


if __name__ == "__main__":
    unittest.main()
