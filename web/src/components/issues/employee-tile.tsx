import type { EmployeeNode } from "@/lib/issues";
import { issueCount } from "@/lib/issue-labels";
import { IssueDialog } from "./issue-dialog";
import { TileContent, tileClass } from "./tile";

export function EmployeeTile({ employee, accent }: { employee: EmployeeNode; accent: string }) {
  return (
    <IssueDialog
      title={employee.name}
      subtitle={`${employee.key} · ${issueCount(employee.issues.length)}`}
      groups={[{ heading: null, issues: employee.issues }]}
      emptyText="Nothing was flagged for this employee."
      triggerClassName={tileClass("normal", true)}
      triggerStyle={{ borderTopColor: accent }}
    >
      <TileContent name={employee.name} detail={employee.id} issues={employee.issues} />
    </IssueDialog>
  );
}
