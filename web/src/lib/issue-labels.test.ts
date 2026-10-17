import { describe, expect, it } from "vitest";
import {
  groupByRecord,
  ISSUE_TITLE,
  issueCount,
  orderedGroups,
  pathField,
  rawText,
  recordLabel,
  resultLabel,
  sentence,
} from "./issue-labels";
import { issueTree, providerIssues, type TreeIssue } from "./issues";

describe("issue titles", () => {
  it("gives every code in the export a title", () => {
    for (const provider of issueTree)
      for (const issue of providerIssues(provider)) expect(ISSUE_TITLE[issue.code]?.length).toBeGreaterThan(0);
  });
});

describe("recordLabel", () => {
  it.each([
    [null, null, "Provider response"],
    ["company", null, "Company"],
    ["run", "202604", "Pay run 202604"],
    ["pg", "7627", "Pay group 7627"],
    ["employee", null, "Employee record"],
    ["dd", "0", "Direct deposit 0"],
    ["ded", "1", "Deduction 1"],
    ["chk", "V000101", "Paycheck V000101"],
  ] as const)("%s %s", (record, id, label) => {
    expect(recordLabel(record, id)).toBe(label);
  });
});

describe("pathField", () => {
  it.each([
    ["person.birthDate", "birth date"],
    ["employeeDeductions.deduction[1].startDate", "start date"],
    ["payroll_run_history['7627'][2].payrollRunType", "payroll run type"],
    ["pay_info.pay_type.id", "pay type"],
    ["lookup_pay_period_profiles.items[9].period_type.type", "period type"],
    ["_links.country-fields", "country fields"],
    ["responses", "responses"],
  ])("%s", (path, label) => {
    expect(pathField(path)).toBe(label);
  });
});

describe("value text", () => {
  it("formats raw values", () => {
    expect(rawText(null)).toBeNull();
    expect(rawText(undefined)).toBeNull();
    expect(rawText("2001-02-30")).toBe("2001-02-30");
    expect(rawText(75)).toBe("75");
    expect(rawText(["eVerify", "taxesToSuppress"])).toBe("eVerify, taxesToSuppress");
    expect(rawText({ a: 1 })).toBe('{"a":1}');
  });

  it("capitalises the action", () => {
    expect(sentence("set null")).toBe("Set null");
    expect(sentence("")).toBe("");
  });

  it("counts issues", () => {
    expect(issueCount(1)).toBe("1 issue");
    expect(issueCount(14)).toBe("14 issues");
  });
});

describe("resultLabel", () => {
  it.each([
    ["set null", "null"],
    ["company name set null", "null"],
    ["kept raw value; canonical value set to unknown", "unknown"],
    ["kept in unmapped", "unmapped"],
    ["no deduction lines emitted", "none"],
    ["pay item skipped", "none"],
    ["read the live shape", "read"],
    ["kept the job code; title null", "kept the job code"],
  ])("%s", (action, label) => {
    expect(resultLabel(action)).toBe(label);
  });
});

describe("groupByRecord", () => {
  it("groups by record in first-seen order", () => {
    const base = {
      code: "missing_section",
      severity: "warning",
      source_path: "x",
      raw_value: null,
      action: "a",
      expected: null,
    } as const;
    const issues: TreeIssue[] = [
      { ...base, record: "run", record_id: "1" },
      { ...base, record: "company", record_id: null },
      { ...base, record: "run", record_id: "1" },
    ];
    expect(groupByRecord(issues).map((g) => [g.heading, g.issues.length])).toEqual([
      ["Pay run 1", 2],
      ["Company", 1],
    ]);
  });
});

describe("orderedGroups", () => {
  it("sorts company, pay group, then pay run by id", () => {
    const headings = ["Pay run 202604", "Pay run 202605", "Company", "Pay run 202603", "Pay group 7628", "Pay group 7627"];
    const groups = headings.map((heading) => ({ heading, issues: [] }));
    expect(orderedGroups(groups).map((group) => group.heading)).toEqual([
      "Company",
      "Pay group 7627",
      "Pay group 7628",
      "Pay run 202603",
      "Pay run 202604",
      "Pay run 202605",
    ]);
  });
});
