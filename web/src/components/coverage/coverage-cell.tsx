"use client";

import type { CSSProperties } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CELL_STATE_LABEL, cellState, type CellState } from "@/lib/cell-state";
import type { CoverageEntry, ProviderCoverage } from "@/lib/data";
import { PROVIDER_STYLE } from "@/lib/providers";

const COUNTED: CellState[] = ["filled", "partial", "empty_in_sample"];

export function cellStyle(state: CellState, accent: string, soft: string): CSSProperties {
  switch (state) {
    case "filled":
      return { backgroundColor: accent, borderColor: accent, color: "white" };
    case "partial":
      return { backgroundColor: soft, borderColor: soft, color: accent };
    case "empty_in_sample":
      return { backgroundColor: "white", borderColor: accent, borderStyle: "dashed", color: accent };
    case "not_mapped_yet":
      return { backgroundColor: "#fffbeb", borderColor: "#f59e0b", color: "#b45309" };
    case "not_offered":
      return {
        backgroundImage: "repeating-linear-gradient(135deg, #f5f5f5 0 6px, #e5e5e5 6px 7px)",
        borderColor: "#e5e5e5",
        color: "#737373",
      };
  }
}

export function CoverageCell({ entry, provider }: { entry: CoverageEntry; provider: ProviderCoverage }) {
  const state = cellState(entry);
  const { accent, soft } = PROVIDER_STYLE[provider.id];
  return (
    <Tooltip>
      <TooltipTrigger
        className="flex h-9 w-full items-center justify-between gap-2 rounded-md border px-3 text-xs font-medium"
        style={cellStyle(state, accent, soft)}
      >
        <span>{CELL_STATE_LABEL[state]}</span>
        {COUNTED.includes(state) && <span className="tabular-nums">{entry.filled}/{entry.total}</span>}
      </TooltipTrigger>
      <TooltipContent className="max-w-sm text-left">
        <div className="space-y-1.5">
          <p className="font-medium">{provider.name}: {CELL_STATE_LABEL[state]}</p>
          {entry.source && <p><span className="opacity-70">Source:</span> <code>{entry.source}</code></p>}
          {entry.reason && <p>{entry.reason}</p>}
          {entry.sample_gap && <p className="opacity-80">{entry.sample_gap}</p>}
          <p className="break-all font-mono text-[10px] opacity-70">{entry.evidence}</p>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
