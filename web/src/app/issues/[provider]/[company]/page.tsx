import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { EmployeeTile } from "@/components/issues/employee-tile";
import { IssuesHeader } from "@/components/issues/issues-header";
import { LeftoverLink } from "@/components/issues/leftover-link";
import { Tile } from "@/components/issues/tile";
import { groupByRecord, orderedGroups } from "@/lib/issue-labels";
import { byConcern, companyIssues, findCompany, findProvider, issueTree } from "@/lib/issues";
import { PROVIDER_STYLE } from "@/lib/providers";

export const metadata: Metadata = { title: "Issues" };
export const dynamicParams = false;

export function generateStaticParams() {
  return issueTree.flatMap((provider) =>
    provider.companies.map((company) => ({ provider: provider.id, company: company.id })),
  );
}

export default async function CompanyIssues({ params }: { params: Promise<{ provider: string; company: string }> }) {
  const ids = await params;
  const provider = findProvider(ids.provider);
  const company = provider && findCompany(provider, ids.company);
  if (!provider || !company) notFound();
  const { accent } = PROVIDER_STYLE[provider.id];
  const employees = byConcern(company.employees, (employee) => employee.issues, (employee) => employee.name);
  return (
    <div>
      <IssuesHeader
        crumbs={[
          { label: "All providers", href: "/issues" },
          { label: provider.name, href: `/issues/${provider.id}` },
          { label: company.name },
        ]}
      />
      <div className="mb-10 flex justify-center">
        <Tile name={company.name} detail={company.key} issues={companyIssues(company)} accent={accent} size="large" />
      </div>
      <div className="flex flex-wrap justify-center gap-7">
        {employees.map((employee) => (
          <EmployeeTile key={employee.key} employee={employee} accent={accent} />
        ))}
      </div>
      <LeftoverLink
        label="not tied to an employee"
        title={`${company.name}: not tied to an employee`}
        subtitle={company.key}
        groups={[
          ...orderedGroups(groupByRecord(company.issues)),
          ...company.unknown_employees.map((employee) => ({
            heading: `Not in employee list: ${employee.id}`,
            issues: employee.issues,
          })),
        ]}
      />
    </div>
  );
}
