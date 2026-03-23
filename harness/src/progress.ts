import { theme } from "./theme.js";

export interface PipelineStage {
  name: string;
  toolName?: string;
  status: "pending" | "active" | "complete" | "error";
}

export interface RunProgress {
  runId: string;
  stages: PipelineStage[];
  designsComplete: number;
  designsTotal: number;
  status: "pending" | "running" | "screening" | "complete" | "error";
}

const STATUS_ICONS = {
  pending: "○",
  active: "●",
  complete: "✓",
  error: "✗",
};

function stageColor(status: PipelineStage["status"]): (s: string) => string {
  switch (status) {
    case "active": return theme.warning;
    case "complete": return theme.success;
    case "error": return theme.error;
    default: return theme.dim;
  }
}

export function renderProgress(run: RunProgress): string {
  const lines: string[] = [];
  lines.push(theme.body(`Design Run: ${run.runId}`));
  lines.push("");

  for (const stage of run.stages) {
    const icon = STATUS_ICONS[stage.status];
    const color = stageColor(stage.status);
    const toolLabel = stage.toolName ? theme.dim(stage.toolName) : "";
    lines.push(`  ${color(icon)} ${color(stage.name.padEnd(28))} ${toolLabel}`);
  }

  lines.push("");
  lines.push(`${theme.primary("Progress:")} ${run.designsComplete}/${run.designsTotal} designs`);
  lines.push(`${theme.body("Status:")} ${run.status === "running" ? theme.primary(run.status) : theme.body(run.status)}`);

  return lines.join("\n");
}

export function createDefaultStages(tool: string): PipelineStage[] {
  if (tool === "boltzgen") {
    return [
      { name: "Design", toolName: "BoltzGen", status: "pending" },
      { name: "Inverse Fold", toolName: "AntiFold", status: "pending" },
      { name: "Refold", toolName: "Protenix-v1", status: "pending" },
      { name: "Analysis", toolName: "ipSAE + Metrics", status: "pending" },
      { name: "Filter & Rank", toolName: "Quality Filter", status: "pending" },
    ];
  }
  if (tool === "pxdesign") {
    return [
      { name: "Design", toolName: "PXDesign", status: "pending" },
      { name: "AF2 Screening", toolName: "AlphaFold2", status: "pending" },
      { name: "Protenix Validation", toolName: "Protenix-v1", status: "pending" },
      { name: "Ranking", toolName: "Composite Score", status: "pending" },
      { name: "Complete", toolName: "Ready for review", status: "pending" },
    ];
  }
  return [
    { name: "Preparing input", toolName: "Config", status: "pending" },
    { name: "Running prediction", toolName: "Protenix-v1", status: "pending" },
    { name: "Computing confidence", toolName: "pLDDT + pTM", status: "pending" },
    { name: "Complete", toolName: "Ready for review", status: "pending" },
  ];
}
