import type { Metadata } from "next";
import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { coverage } from "@/lib/data";
import { PAYROLL_SECTIONS } from "@/lib/sections";

export const metadata: Metadata = { title: "Payroll field coverage" };

export default function Payroll() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Payroll field coverage</h1>
      <div className="mt-6">
        <CoverageGrid providers={coverage.payroll} sectionTitles={PAYROLL_SECTIONS} />
      </div>
    </div>
  );
}
