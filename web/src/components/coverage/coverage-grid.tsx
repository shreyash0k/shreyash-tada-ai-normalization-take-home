"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import { TooltipProvider } from "@/components/ui/tooltip";
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
  const visible = gapsOnly ? rows.filter((row) => row.cells.some((cell) => cell.status !== "mapped")) : rows;
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
        <table className="w-full table-fixed text-sm">
          <colgroup>
            <col className="w-64" />
            {providers.map((provider) => <col key={provider.id} />)}
          </colgroup>
          <thead>
            <tr className="border-b bg-neutral-50">
              <th className="px-4 py-3 text-left align-middle font-medium text-neutral-500">Canonical field</th>
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
  const { logo } = PROVIDER_STYLE[provider.id];
  return (
    <th className="px-3 py-4 align-middle font-medium">
      <Image
        src={logo}
        alt={provider.name}
        width={140}
        height={32}
        className="mx-auto h-7 w-auto max-w-full object-contain"
      />
    </th>
  );
}
