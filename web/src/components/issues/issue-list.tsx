import type { TreeIssue } from "@/lib/issues";
import { rawText, resultLabel } from "@/lib/issue-labels";

const COLUMNS = "grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto] items-baseline gap-x-4";

export function IssueList({ issues }: { issues: TreeIssue[] }) {
  return (
    <div>
      <div className={`${COLUMNS} px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-400`}>
        <span>Field</span>
        <span>Got</span>
        <span>Expected</span>
        <span>Result</span>
      </div>
      <ul className="space-y-1.5">
        {issues.map((issue, index) => {
          const raw = rawText(issue.raw_value);
          return (
            <li key={index} className={`${COLUMNS} rounded-lg border px-3 py-2 text-[13px]`}>
              <span className="break-all font-mono font-medium">{issue.source_path}</span>
              {raw === null ? (
                <span className="text-neutral-500">absent</span>
              ) : (
                <span className="break-all font-mono">{raw}</span>
              )}
              <span className="break-words text-neutral-600">{issue.expected}</span>
              <span className="font-mono text-xs font-semibold text-neutral-700">{resultLabel(issue.action)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
