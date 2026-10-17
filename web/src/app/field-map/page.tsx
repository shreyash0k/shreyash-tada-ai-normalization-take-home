import type { Metadata } from "next";
import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { coverage } from "@/lib/data";
import { EMPLOYEE_SECTIONS } from "@/lib/sections";

export const metadata: Metadata = { title: "Employee field coverage" };

export default function EmployeeFieldMap() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Employee field coverage</h1>
      <div className="mt-6">
        <CoverageGrid providers={coverage.employee} sectionTitles={EMPLOYEE_SECTIONS} />
      </div>
    </div>
  );
}
