import type { IssueGroup } from "@/lib/issues";
import { issueCount } from "@/lib/issue-labels";
import { IssueDialog } from "./issue-dialog";

export function LeftoverLink({
  label,
  title,
  subtitle,
  groups,
}: {
  label: string;
  title: string;
  subtitle: string;
  groups: IssueGroup[];
}) {
  const count = groups.reduce((total, group) => total + group.issues.length, 0);
  if (count === 0) return null;
  return (
    <div className="mt-10 text-center">
      <IssueDialog
        title={title}
        subtitle={subtitle}
        groups={groups}
        triggerClassName="cursor-pointer text-sm text-neutral-600 underline decoration-neutral-300 underline-offset-4 hover:text-neutral-900 hover:decoration-neutral-900"
      >
        {issueCount(count)} {label}
      </IssueDialog>
    </div>
  );
}
