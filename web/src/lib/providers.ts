export type ProviderId = "prismhr" | "isolved" | "ukg-ready";

export const PROVIDER_STYLE: Record<ProviderId, { accent: string; soft: string; logo: string }> = {
  prismhr: { accent: "#323c78", soft: "#e8eaf6", logo: "/logos/prismhr.svg" },
  isolved: { accent: "#8e3456", soft: "#f8e7ef", logo: "/logos/isolved.svg" },
  "ukg-ready": { accent: "#1a5f58", soft: "#e5f2f0", logo: "/logos/ukg-ready.svg" },
};
