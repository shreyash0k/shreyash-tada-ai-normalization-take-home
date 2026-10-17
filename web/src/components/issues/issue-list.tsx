"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import type { TreeIssue } from "@/lib/issues";
import { issueReport, rawText, resultLabel } from "@/lib/issue-labels";

const CELL = "px-3 py-2 align-top";

function FieldPath({ path }: { path: string }) {
  const parts = path.split(/([._[\]])/);
  return (
    <span className="font-mono font-medium">
      {parts.map((part, index) =>
        part === "." || part === "_" || part === "[" || part === "]" ? (
          <span key={index}>
            {part}
            <wbr />
          </span>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </span>
  );
}

function CopyIssue({ text, field }: { text: string; field: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={copied ? `Copied ${field}` : `Copy ${field}`}
      className="rounded-md p-1.5 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-800"
      onClick={() => {
        navigator.clipboard.writeText(text).then(
          () => setCopied(true),
          () => setCopied(false),
        );
        window.setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
    </button>
  );
}

export function IssueList({
  issues,
  title,
  subtitle,
}: {
  issues: TreeIssue[];
  title: string;
  subtitle: string;
}) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <table className="w-full table-fixed border-collapse text-[13px]">
        <thead>
          <tr className="bg-neutral-50 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
            <th className={`${CELL} w-[32%]`}>Field</th>
            <th className={`${CELL} w-[18%]`}>Got</th>
            <th className={`${CELL} w-[26%]`}>Expected</th>
            <th className={`${CELL} w-[18%]`}>Result</th>
            <th className="w-10 px-1 py-2">
              <span className="sr-only">Copy</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue, index) => {
            const raw = rawText(issue.raw_value);
            return (
              <tr key={index} className="border-t">
                <td className={CELL}>
                  <FieldPath path={issue.source_path} />
                </td>
                {raw === null ? (
                  <td className={`${CELL} text-neutral-500`}>absent</td>
                ) : (
                  <td className={`${CELL} break-words font-mono`}>{raw}</td>
                )}
                <td className={`${CELL} break-words text-neutral-600`}>{issue.expected}</td>
                <td className={`${CELL} break-words font-mono text-xs font-semibold text-neutral-700`}>
                  {resultLabel(issue.action)}
                </td>
                <td className="px-1 py-1 text-center align-top">
                  <CopyIssue
                    field={issue.source_path}
                    text={issueReport(title, subtitle, issue)}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
