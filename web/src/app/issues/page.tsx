import type { Metadata } from "next";
import { IssuesHeader } from "@/components/issues/issues-header";
import { Tile } from "@/components/issues/tile";
import { issueTree, providerIssues } from "@/lib/issues";
import { PROVIDER_STYLE } from "@/lib/providers";

export const metadata: Metadata = { title: "Issues" };

export default function Issues() {
  return (
    <div>
      <IssuesHeader />
      <div className="flex flex-wrap justify-center gap-7 pt-4">
        {issueTree.map((provider) => (
          <Tile
            key={provider.id}
            name={provider.name}
            issues={providerIssues(provider)}
            accent={PROVIDER_STYLE[provider.id].accent}
            logo={PROVIDER_STYLE[provider.id].logo}
            href={`/issues/${provider.id}`}
            size="large"
          />
        ))}
      </div>
    </div>
  );
}
