export type ProteusMode = "binder" | "antibody" | "structure";

export interface ModeConfig {
  name: string;
  displayName: string;
  description: string;
  defaultTool: string;
  skills: string[];
}

export const MODES: Record<ProteusMode, ModeConfig> = {
  binder: {
    name: "binder",
    displayName: "Binder Designer",
    description: "De novo protein binder design with PXDesign",
    defaultTool: "proteus-prot",
    skills: ["proteus-design-workflow", "proteus-scoring", "proteus-epitope-analysis", "proteus-screening"],
  },
  antibody: {
    name: "antibody",
    displayName: "Antibody Designer",
    description: "Antibody/nanobody design with BoltzGen + Protenix",
    defaultTool: "proteus-ab",
    skills: ["proteus-design-workflow", "proteus-scoring", "proteus-epitope-analysis", "proteus-screening", "proteus-database"],
  },
  structure: {
    name: "structure",
    displayName: "Structure Predictor",
    description: "AF3-class structure prediction with Protenix v1",
    defaultTool: "proteus-fold",
    skills: ["proteus-design-workflow", "proteus-scoring"],
  },
};

export function cycleMode(current: ProteusMode): ProteusMode {
  const order: ProteusMode[] = ["binder", "antibody", "structure"];
  const idx = order.indexOf(current);
  return order[(idx + 1) % order.length];
}

export function getModeConfig(mode: ProteusMode): ModeConfig {
  return MODES[mode];
}
