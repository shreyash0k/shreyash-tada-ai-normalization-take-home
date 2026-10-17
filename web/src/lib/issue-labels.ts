import type { IssueCode, IssueGroup, RecordKind, TreeIssue } from "./issues";

export const ISSUE_TITLE: Record<IssueCode, string> = {
  undocumented_code: "Unknown code",
  unmapped_label: "Unrecognized label",
  invalid_date: "Invalid date",
  invalid_number: "Invalid number",
  missing_section: "Missing data",
  missing_lookup: "Missing lookup",
  spec_live_mismatch: "Differs from the API spec",
  masked_value: "Masked value",
  out_of_schema_value: "Unexpected value",
  multiple_current_rates: "Several current rates",
  inconsistent_allocation: "Inconsistent amounts",
  broken_link: "Broken link",
  unknown: "Other issue",
};

const RECORD_NOUN: Record<RecordKind, string> = {
  company: "Company",
  run: "Pay run",
  pg: "Pay group",
  employee: "Employee record",
  dd: "Direct deposit",
  ded: "Deduction",
  chk: "Paycheck",
};

const GENERIC_SEGMENTS = new Set(["id", "type"]);

export function recordLabel(record: RecordKind | null, recordId: string | null): string {
  if (record === null) return "Provider response";
  return recordId === null ? RECORD_NOUN[record] : `${RECORD_NOUN[record]} ${recordId}`;
}

export function pathField(sourcePath: string): string {
  const segments = sourcePath.replace(/\[[^\]]*\]/g, "").split(".");
  while (segments.length > 1 && GENERIC_SEGMENTS.has(segments[segments.length - 1])) segments.pop();
  return segments[segments.length - 1]
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .trim()
    .toLowerCase();
}

export function rawText(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function sentence(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

export function resultLabel(action: string): string {
  const text = action.toLowerCase();
  if (text.includes("unknown")) return "unknown";
  if (text.includes("unmapped")) return "unmapped";
  if (text.includes("set null") || text.includes("left empty")) return "null";
  if (text.includes("emitted") || text.includes("skipped")) return "none";
  if (text.startsWith("read the live shape")) return "read";
  const clause = action.split(";")[0];
  return clause;
}

const COMPANY_RECORDS = new Set(["run", "pg"]);

function identity(subtitle: string): { provider: string; id: string } {
  const parts = subtitle.split(" · ")[0].split(":");
  const provider = parts[0] ?? "";
  if (parts.length >= 3 && !COMPANY_RECORDS.has(parts[2])) return { provider, id: parts[2] };
  if (parts.length === 4 && COMPANY_RECORDS.has(parts[2])) return { provider, id: parts[3] };
  if (parts.length >= 2) return { provider, id: parts[1] };
  return { provider, id: "" };
}

export function issueReport(name: string, subtitle: string, issue: TreeIssue): string {
  const { provider, id } = identity(subtitle);
  const lines = [`name: ${name}`, `provider: ${provider}`];
  if (id) lines.push(`id: ${id}`);
  lines.push(
    "",
    `field: ${issue.source_path}`,
    `got: ${rawText(issue.raw_value) ?? "absent"}`,
    `expected: ${issue.expected ?? ""}`,
    `result: ${resultLabel(issue.action)}`,
    "",
  );
  return lines.join("\n");
}

export function issueCount(count: number): string {
  return `${count} ${count === 1 ? "issue" : "issues"}`;
}

export function groupByRecord(issues: TreeIssue[]): IssueGroup[] {
  const groups = new Map<string, TreeIssue[]>();
  for (const issue of issues) {
    const heading = recordLabel(issue.record, issue.record_id);
    groups.set(heading, [...(groups.get(heading) ?? []), issue]);
  }
  return [...groups].map(([heading, grouped]) => ({ heading, issues: grouped }));
}

const GROUP_KIND = ["Company", "Pay group", "Pay run"];

function groupKind(heading: string | null): { rank: number; id: string } | null {
  if (heading === null) return null;
  for (let rank = 0; rank < GROUP_KIND.length; rank++) {
    const kind = GROUP_KIND[rank];
    if (heading === kind) return { rank, id: "" };
    const prefix = `${kind} `;
    if (heading.startsWith(prefix)) return { rank, id: heading.slice(prefix.length) };
  }
  return null;
}

export function orderedGroups(groups: IssueGroup[]): IssueGroup[] {
  const named: { group: IssueGroup; rank: number; id: string }[] = [];
  const rest: IssueGroup[] = [];
  for (const group of groups) {
    const kind = groupKind(group.heading);
    if (kind) named.push({ group, rank: kind.rank, id: kind.id });
    else rest.push(group);
  }
  named.sort((a, b) => a.rank - b.rank || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return [...named.map(({ group }) => group), ...rest];
}
