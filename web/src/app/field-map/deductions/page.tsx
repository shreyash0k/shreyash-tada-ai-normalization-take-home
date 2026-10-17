import type { Metadata } from "next";
import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { coverage } from "@/lib/data";
import { DEDUCTION_SECTIONS } from "@/lib/sections";

export const metadata: Metadata = { title: "Deduction field coverage" };

export default function Deductions() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Deduction field coverage</h1>
      <div className="mt-6">
        <CoverageGrid providers={coverage.deduction} sectionTitles={DEDUCTION_SECTIONS} />
      </div>
    </div>
  );
}
