"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cellStyle } from "./coverage-cell";
import { STATUSES, STATUS_DESCRIPTION, STATUS_LABEL } from "@/lib/status";

export function CoverageLegend() {
  return (
    <ul className="flex flex-wrap gap-3 text-xs text-neutral-600">
      {STATUSES.map((status) => (
        <li key={status}>
          <Tooltip>
            <TooltipTrigger className="flex items-center gap-1.5">
              <span className="inline-block size-4 rounded border" style={cellStyle(status, "#3f3f46", "#ececee")} />
              {STATUS_LABEL[status]}
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-left">{STATUS_DESCRIPTION[status]}</TooltipContent>
          </Tooltip>
        </li>
      ))}
    </ul>
  );
}
