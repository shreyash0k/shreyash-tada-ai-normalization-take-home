export type ProviderId = "prismhr" | "isolved" | "ukg-ready";

export const PROVIDER_STYLE: Record<ProviderId, { accent: string; soft: string; logo: string }> = {
  prismhr: { accent: "#3c539a", soft: "#e8ecf6", logo: "/logos/prismhr.svg" },
  isolved: { accent: "#e50082", soft: "#fde6f2", logo: "/logos/isolved.svg" },
  "ukg-ready": { accent: "#005151", soft: "#e0eded", logo: "/logos/ukg-ready.svg" },
};
