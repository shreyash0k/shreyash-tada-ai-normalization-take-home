import type { FieldStatus } from "./data";

export const STATUSES: FieldStatus[] = ["mapped", "not_mapped_yet", "not_offered"];

export const STATUS_LABEL: Record<FieldStatus, string> = {
  mapped: "Mapped",
  not_mapped_yet: "Not mapped yet",
  not_offered: "Not offered",
};

export const STATUS_DESCRIPTION: Record<FieldStatus, string> = {
  mapped: "The adapter reads this field from the provider field shown in the cell.",
  not_mapped_yet: "The provider has this data, but the adapter does not use it yet.",
  not_offered: "The provider has no such field for reading.",
};
