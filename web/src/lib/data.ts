import raw from "../data/coverage.json";
import type { ProviderId } from "./providers";

export type FieldStatus = "mapped" | "not_mapped_yet" | "not_offered";

export type EntityId = "employee" | "direct-deposit" | "deduction" | "payroll";

export type CoverageEntry = {
  field: string;
  section: string;
  status: FieldStatus;
  source: string | null;
  evidence: string;
  reason: string | null;
};

export type ProviderSummary = {
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

export type CoverageData = { export_version: number; entities: Record<EntityId, ProviderCoverage[]> };

export const coverage: Record<EntityId, ProviderCoverage[]> = (raw as unknown as CoverageData).entities;
