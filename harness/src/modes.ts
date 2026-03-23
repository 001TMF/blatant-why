export type ProteusMode = "vhh" | "scfv" | "denovo";

export interface ModeConfig {
  name: string;
  displayName: string;
  description: string;
  defaultTool: string;
  protocol: string;
  skills: string[];
}

export const MODES: Record<ProteusMode, ModeConfig> = {
  vhh: {
    name: "vhh",
    displayName: "VHH Nanobody Designer",
    description: "Design single-domain nanobodies using BoltzGen",
    defaultTool: "boltzgen",
    protocol: "nanobody-anything",
    skills: ["proteus-design-workflow", "proteus-scoring", "proteus-epitope-analysis", "proteus-screening", "proteus-database"],
  },
  scfv: {
    name: "scfv",
    displayName: "scFv Antibody Designer",
    description: "Design scFv antibodies from Fab templates via BoltzGen",
    defaultTool: "boltzgen",
    protocol: "antibody-anything",
    skills: ["proteus-design-workflow", "proteus-scoring", "proteus-epitope-analysis", "proteus-screening", "proteus-database"],
  },
  denovo: {
    name: "denovo",
    displayName: "De Novo Protein Designer",
    description: "Design novel miniprotein binders using BoltzGen",
    defaultTool: "boltzgen",
    protocol: "protein-anything",
    skills: ["proteus-design-workflow", "proteus-scoring", "proteus-epitope-analysis", "proteus-screening"],
  },
};

export function cycleMode(current: ProteusMode): ProteusMode {
  const order: ProteusMode[] = ["vhh", "scfv", "denovo"];
  const idx = order.indexOf(current);
  return order[(idx + 1) % order.length];
}

export function getModeConfig(mode: ProteusMode): ModeConfig {
  return MODES[mode];
}
