import { CELL_STATES, CELL_STATE_LABEL } from "@/lib/cell-state";
import { cellStyle } from "./coverage-cell";

export function CoverageLegend() {
  return (
    <ul className="flex flex-wrap gap-3 text-xs text-neutral-600">
      {CELL_STATES.map((state) => (
        <li key={state} className="flex items-center gap-1.5">
          <span className="inline-block size-4 rounded border" style={cellStyle(state, "#404040", "#e5e5e5")} />
          {CELL_STATE_LABEL[state]}
        </li>
      ))}
    </ul>
  );
}
