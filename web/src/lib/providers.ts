export type ProviderId = "prismhr" | "isolved" | "ukg-ready";

export const PROVIDER_STYLE: Record<ProviderId, { accent: string; soft: string }> = {
  prismhr: { accent: "#2563eb", soft: "#dbeafe" },
  isolved: { accent: "#059669", soft: "#d1fae5" },
  "ukg-ready": { accent: "#7c3aed", soft: "#ede9fe" },
};
