"use client";

import type { CSSProperties } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { CoverageEntry, FieldStatus, ProviderCoverage } from "@/lib/data";
import { shortSource } from "@/lib/labels";
import { PROVIDER_STYLE } from "@/lib/providers";
import { STATUS_LABEL } from "@/lib/status";

export function cellStyle(status: FieldStatus, accent: string, soft: string): CSSProperties {
  switch (status) {
    case "mapped":
      return { backgroundColor: soft, borderColor: soft, color: accent };
    case "not_mapped_yet":
      return { backgroundColor: "#faf6f0", borderColor: "#eadfce", color: "#7a5528" };
    case "not_offered":
      return { backgroundColor: "#fafafa", borderColor: "#e4e4e7", color: "#5c5c5c" };
  }
}

export function CoverageCell({ entry, provider }: { entry: CoverageEntry; provider: ProviderCoverage }) {
  const { accent, soft } = PROVIDER_STYLE[provider.id];
  const label = entry.status === "mapped" && entry.source ? shortSource(entry.source) : STATUS_LABEL[entry.status];
  return (
    <Tooltip>
      <TooltipTrigger
        className="flex h-9 w-full min-w-0 items-center rounded-md border px-3 text-xs font-medium"
        style={cellStyle(entry.status, accent, soft)}
        aria-label={`${provider.name}, ${entry.field}: ${STATUS_LABEL[entry.status]}`}
      >
        <span className={`min-w-0 truncate ${entry.status === "mapped" ? "font-mono" : ""}`}>{label}</span>
      </TooltipTrigger>
      <TooltipContent className="max-w-sm text-left">
        <div className="space-y-1.5">
          <p className="font-medium">{provider.name}: {STATUS_LABEL[entry.status]}</p>
          {entry.source && <p><span className="opacity-70">Source:</span> <code>{entry.source}</code></p>}
          {entry.reason && <p>{entry.reason}</p>}
          <p className="break-all font-mono text-[10px] opacity-70">{entry.evidence}</p>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
