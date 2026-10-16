import type { CoverageEntry } from "./data";

export type CellState = "filled" | "partial" | "empty_in_sample" | "not_mapped_yet" | "not_offered";

export const CELL_STATES: CellState[] = ["filled", "partial", "empty_in_sample", "not_mapped_yet", "not_offered"];

export const CELL_STATE_LABEL: Record<CellState, string> = {
  filled: "Filled",
  partial: "Partly filled",
  empty_in_sample: "Empty in sample",
  not_mapped_yet: "Not mapped yet",
  not_offered: "Not offered",
};

export function cellState(entry: Pick<CoverageEntry, "status" | "filled" | "total">): CellState {
  if (entry.status === "not_offered") return "not_offered";
  if (entry.status === "not_mapped_yet") return "not_mapped_yet";
  if (entry.filled === 0) return "empty_in_sample";
  return entry.filled >= entry.total ? "filled" : "partial";
}
