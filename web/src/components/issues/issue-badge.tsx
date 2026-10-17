import type { TreeIssue } from "@/lib/issues";

const BASE =
  "absolute -right-3 -top-3 flex h-8 min-w-8 items-center justify-center rounded-full border-[3px] border-neutral-50 bg-red-600 px-2 text-sm font-semibold text-white";

export function IssueBadge({ issues }: { issues: TreeIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <span className={BASE}>
      {issues.length}
      <span className="sr-only"> {issues.length === 1 ? "issue" : "issues"}</span>
    </span>
  );
}
