import type { Metadata } from "next";
import { CoverageGrid } from "@/components/coverage/coverage-grid";
import { coverage } from "@/lib/data";
import { DEPOSIT_SECTIONS } from "@/lib/sections";

export const metadata: Metadata = { title: "Direct deposit field coverage" };

export default function DirectDeposits() {
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Direct deposit field coverage</h1>
      <div className="mt-6">
        <CoverageGrid providers={coverage["direct-deposit"]} sectionTitles={DEPOSIT_SECTIONS} />
      </div>
    </div>
  );
}
