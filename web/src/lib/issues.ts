import raw from "../data/issues.json";
import type { ProviderId } from "./providers";

export type Severity = "error" | "warning" | "info" | "unknown";

export type IssueCode =
  | "undocumented_code"
  | "unmapped_label"
  | "invalid_date"
  | "invalid_number"
  | "missing_section"
  | "missing_lookup"
  | "spec_live_mismatch"
  | "masked_value"
  | "out_of_schema_value"
  | "multiple_current_rates"
  | "inconsistent_allocation"
  | "unknown";

export type RecordKind = "company" | "run" | "pg" | "employee" | "dd" | "ded" | "chk";

export type TreeIssue = {
  code: IssueCode;
  severity: Severity;
  source_path: string;
  raw_value: unknown;
  action: string;
  expected: string | null;
  record: RecordKind | null;
  record_id: string | null;
};

export type EmployeeNode = { key: string; id: string; name: string; issues: TreeIssue[] };
export type UnknownEmployee = { key: string; id: string; issues: TreeIssue[] };

export type CompanyNode = {
  id: string;
  key: string;
  name: string;
  issues: TreeIssue[];
  unknown_employees: UnknownEmployee[];
  employees: EmployeeNode[];
};

export type ProviderNode = { id: ProviderId; name: string; issues: TreeIssue[]; companies: CompanyNode[] };

export type IssueGroup = { heading: string | null; issues: TreeIssue[] };

type IssueData = { export_version: number; providers: ProviderNode[] };

export const issueTree: ProviderNode[] = (raw as unknown as IssueData).providers;

export function companyIssues(company: CompanyNode): TreeIssue[] {
  return [
    ...company.issues,
    ...company.unknown_employees.flatMap((employee) => employee.issues),
    ...company.employees.flatMap((employee) => employee.issues),
  ];
}

export function providerIssues(provider: ProviderNode): TreeIssue[] {
  return [...provider.issues, ...provider.companies.flatMap(companyIssues)];
}

export function byConcern<T>(items: T[], issuesOf: (item: T) => TreeIssue[], nameOf: (item: T) => string): T[] {
  return [...items].sort(
    (a, b) =>
      issuesOf(b).length - issuesOf(a).length || (nameOf(a) < nameOf(b) ? -1 : nameOf(a) > nameOf(b) ? 1 : 0),
  );
}

export function findProvider(id: string): ProviderNode | undefined {
  return issueTree.find((provider) => provider.id === id);
}

export function findCompany(provider: ProviderNode, id: string): CompanyNode | undefined {
  return provider.companies.find((company) => company.id === id);
}
