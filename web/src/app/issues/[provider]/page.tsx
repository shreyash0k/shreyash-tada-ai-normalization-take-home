import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { IssuesHeader } from "@/components/issues/issues-header";
import { LeftoverLink } from "@/components/issues/leftover-link";
import { Tile } from "@/components/issues/tile";
import { issueCount } from "@/lib/issue-labels";
import { byConcern, companyIssues, findProvider, issueTree, providerIssues } from "@/lib/issues";
import { PROVIDER_STYLE } from "@/lib/providers";

export const metadata: Metadata = { title: "Issues" };
export const dynamicParams = false;

export function generateStaticParams() {
  return issueTree.map((provider) => ({ provider: provider.id }));
}

export default async function ProviderIssues({ params }: { params: Promise<{ provider: string }> }) {
  const provider = findProvider((await params).provider);
  if (!provider) notFound();
  const { accent, logo } = PROVIDER_STYLE[provider.id];
  const companies = byConcern(provider.companies, companyIssues, (company) => company.name);
  return (
    <div>
      <IssuesHeader crumbs={[{ label: "All providers", href: "/issues" }, { label: provider.name }]} />
      <div className="mb-10 flex justify-center">
        <Tile name={provider.name} issues={providerIssues(provider)} accent={accent} logo={logo} size="large" />
      </div>
      <div className="flex flex-wrap justify-center gap-7">
        {companies.map((company) => (
          <Tile
            key={company.id}
            name={company.name}
            detail={company.key}
            issues={companyIssues(company)}
            accent={accent}
            href={`/issues/${provider.id}/${company.id}`}
          />
        ))}
      </div>
      <LeftoverLink
        label="not tied to a client"
        title={`${provider.name}: not tied to a client`}
        subtitle={`${provider.id} · ${issueCount(provider.issues.length)}`}
        groups={[{ heading: null, issues: provider.issues }]}
      />
    </div>
  );
}
