import raw from "../data/coverage.json";
import type { ProviderId } from "./providers";

export type FieldStatus = "mapped" | "not_mapped_yet" | "not_offered";

export type CoverageEntry = {
  field: string;
  section: string;
  status: FieldStatus;
  filled: number;
  total: number;
  source: string | null;
  evidence: string;
  reason: string | null;
  sample_gap: string | null;
};

export type ProviderSummary = {
  employees: number;
  fields_total: number;
  fields_offered: number;
  fields_mapped: number;
};

export type ProviderCoverage = {
  id: ProviderId;
  name: string;
  summary: ProviderSummary;
  coverage: CoverageEntry[];
};

export type CoverageData = { export_version: number; providers: ProviderCoverage[] };

export const providers: ProviderCoverage[] = (raw as unknown as CoverageData).providers;
