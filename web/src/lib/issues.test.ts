import { describe, expect, it } from "vitest";
import {
  byConcern,
  companyIssues,
  findCompany,
  findProvider,
  issueTree,
  providerIssues,
  type CompanyNode,
  type ProviderNode,
  type Severity,
  type TreeIssue,
} from "./issues";
import { PROVIDER_STYLE } from "./providers";

const issue = (severity: Severity): TreeIssue => ({
  code: "invalid_date",
  severity,
  source_path: "person.birthDate",
  raw_value: null,
  action: "set null",
  expected: null,
  record: "employee",
  record_id: null,
});

const company: CompanyNode = {
  id: "132",
  key: "prismhr:132",
  name: "Demo",
  issues: [issue("warning")],
  unknown_employees: [{ key: "prismhr:132:X00099", id: "X00099", issues: [issue("warning")] }],
  employees: [{ key: "prismhr:132:F00001", id: "F00001", name: "Finley", issues: [issue("error"), issue("info")] }],
};

describe("roll-ups", () => {
  it("counts everything under a client", () => {
    expect(companyIssues(company)).toHaveLength(4);
  });

  it("adds provider-wide issues to a provider", () => {
    const provider: ProviderNode = { id: "prismhr", name: "PrismHR", issues: [issue("info")], companies: [company] };
    expect(providerIssues(provider)).toHaveLength(5);
  });
});

describe("ordering", () => {
  it("sorts tiles by count, then by name", () => {
    const items = [
      { name: "Clean", issues: [] },
      { name: "Bravo", issues: [issue("warning")] },
      { name: "Alpha", issues: [issue("warning")] },
      { name: "Many", issues: [issue("warning"), issue("warning")] },
      { name: "Bad", issues: [issue("error")] },
    ];
    const sorted = byConcern(items, (item) => item.issues, (item) => item.name);
    expect(sorted.map((item) => item.name)).toEqual(["Many", "Alpha", "Bad", "Bravo", "Clean"]);
  });
});

describe("exported data", () => {
  it("has every provider the app styles", () => {
    expect(issueTree.map((p) => p.id)).toEqual(Object.keys(PROVIDER_STYLE));
  });

  it("finds providers and clients by id", () => {
    const prismhr = findProvider("prismhr");
    expect(prismhr?.name).toBe("PrismHR");
    expect(findCompany(prismhr!, "132")?.key).toBe("prismhr:132");
    expect(findProvider("nope")).toBeUndefined();
  });

  it("names every employee", () => {
    for (const provider of issueTree)
      for (const c of provider.companies) for (const e of c.employees) expect(e.name.length).toBeGreaterThan(0);
  });
});
