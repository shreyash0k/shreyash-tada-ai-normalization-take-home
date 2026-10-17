import type { Metadata } from "next";
import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { coverage } from "@/lib/data";
import { COMPANY_SECTIONS } from "@/lib/sections";

export const metadata: Metadata = { title: "Company field coverage" };

export default function Company() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Company field coverage</h1>
      <div className="mt-6">
        <CoverageGrid providers={coverage.company} sectionTitles={COMPANY_SECTIONS} />
      </div>
    </div>
  );
}
