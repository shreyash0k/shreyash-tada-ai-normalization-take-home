"use client";

import { useMemo, useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cellState } from "@/lib/cell-state";
import type { CoverageEntry, ProviderCoverage } from "@/lib/data";
import { fieldLabel } from "@/lib/labels";
import { PROVIDER_STYLE } from "@/lib/providers";
import { CoverageCell } from "./coverage-cell";
import { CoverageLegend } from "./coverage-legend";

const SECTION_TITLES: Record<string, string> = {
  person: "Person",
  contact: "Contact",
  employment: "Employment",
  job: "Job",
  compensation: "Compensation",
};

type Row = { field: string; section: string; cells: CoverageEntry[] };

export function CoverageGrid({ providers }: { providers: ProviderCoverage[] }) {
  const [gapsOnly, setGapsOnly] = useState(false);
  const rows = useMemo<Row[]>(() => {
    const lookups = providers.map((provider) => new Map(provider.coverage.map((entry) => [entry.field, entry])));
    return providers[0].coverage.map(({ field, section }) => ({
      field,
      section,
      cells: lookups.map((lookup) => lookup.get(field) as CoverageEntry),
    }));
  }, [providers]);
  const visible = gapsOnly ? rows.filter((row) => row.cells.some((cell) => cellState(cell) !== "filled")) : rows;
  const sections = Object.keys(SECTION_TITLES).filter((section) => visible.some((row) => row.section === section));

  return (
    <TooltipProvider delay={100}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <CoverageLegend />
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          <input
            type="checkbox"
            checked={gapsOnly}
            onChange={(event) => setGapsOnly(event.target.checked)}
            className="size-4 accent-neutral-900"
          />
          Show gaps only
        </label>
      </div>
      <div className="overflow-x-auto rounded-xl border bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-neutral-50">
              <th className="w-72 px-4 py-3 text-left align-bottom font-medium text-neutral-500">Canonical field</th>
              {providers.map((provider) => <ProviderHeader key={provider.id} provider={provider} />)}
            </tr>
          </thead>
          {sections.map((section) => (
            <tbody key={section}>
              <tr>
                <th
                  colSpan={providers.length + 1}
                  className="bg-neutral-50/70 px-4 py-2 text-left text-xs font-semibold uppercase tracking-wide text-neutral-500"
                >
                  {SECTION_TITLES[section]}
                </th>
              </tr>
              {visible.filter((row) => row.section === section).map((row) => (
                <tr key={row.field} className="border-t">
                  <td className="px-4 py-2">
                    <div className="font-medium text-neutral-800">{fieldLabel(row.field)}</div>
                    <div className="font-mono text-xs text-neutral-400">{row.field}</div>
                  </td>
                  {row.cells.map((cell, index) => (
                    <td key={providers[index].id} className="px-2 py-2">
                      <CoverageCell entry={cell} provider={providers[index]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </TooltipProvider>
  );
}

function ProviderHeader({ provider }: { provider: ProviderCoverage }) {
  const { accent } = PROVIDER_STYLE[provider.id];
  const { employees, fields_offered: offered, fields_mapped: mapped, fields_total: total } = provider.summary;
  return (
    <th className="min-w-48 px-2 py-3 text-left align-bottom font-medium">
      <div className="flex items-center gap-2">
        <span className="size-2.5 rounded-full" style={{ backgroundColor: accent }} />
        {provider.name}
      </div>
      <div className="mt-0.5 text-xs font-normal text-neutral-500">{employees} synthetic employees</div>
      <Bar label="offered" value={offered} total={total} color={accent} opacity={0.35} />
      <Bar label="mapped" value={mapped} total={total} color={accent} opacity={1} />
    </th>
  );
}

function Bar({ label, value, total, color, opacity }:
  { label: string; value: number; total: number; color: string; opacity: number }) {
  return (
    <div className="mt-2">
      <div className="flex justify-between text-[11px] font-normal text-neutral-500">
        <span>{label}</span>
        <span className="tabular-nums">{value}/{total}</span>
      </div>
      <div className="h-1.5 rounded-full bg-neutral-100">
        <div className="h-1.5 rounded-full" style={{ width: `${(value / total) * 100}%`, backgroundColor: color, opacity }} />
      </div>
    </div>
  );
}
