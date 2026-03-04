import chalk from "chalk";
import { theme } from "./theme.js";

export interface PipelineStage {
  name: string;
  engine: string;
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
    case "active": return theme.primary;
    case "complete": return theme.success;
    case "error": return theme.error;
    default: return theme.dim;
  }
}

export function renderProgress(run: RunProgress): string {
  const lines: string[] = [];
  lines.push(theme.heading(`Design Run: ${run.runId}`));
  lines.push("");

  for (const stage of run.stages) {
    const icon = STATUS_ICONS[stage.status];
    const color = stageColor(stage.status);
    const arrow = stage.status === "active" ? theme.accent(" ← active") : "";
    lines.push(`  ${color(icon)} ${color(stage.name.padEnd(24))} ${theme.dim(stage.engine)}${arrow}`);
  }

  lines.push("");
  const pct = run.designsTotal > 0 ? Math.round((run.designsComplete / run.designsTotal) * 100) : 0;
  lines.push(`${theme.body("Progress:")} ${theme.primaryBold(`${run.designsComplete}/${run.designsTotal}`)} ${theme.dim(`(${pct}%)`)}`);
  lines.push(`${theme.body("Status:")} ${run.status === "running" ? theme.running(run.status) : theme.body(run.status)}`);

  return lines.join("\n");
}

export function createDefaultStages(tool: string): PipelineStage[] {
  if (tool === "proteus-prot" || tool === "proteus-ab") {
    return [
      { name: "Generating backbones", engine: tool === "proteus-prot" ? "PXDesign-d" : "BoltzGen", status: "pending" },
      { name: "Designing sequences", engine: tool === "proteus-prot" ? "ProteinMPNN" : "AntiFold", status: "pending" },
      { name: "Screening quality", engine: "ipSAE + p_bind + liabilities", status: "pending" },
      { name: "Evaluating structures", engine: "Protenix refolding", status: "pending" },
      { name: "Filtering & ranking", engine: "Composite score", status: "pending" },
      { name: "Design complete", engine: "Ready for review", status: "pending" },
    ];
  }
  return [
    { name: "Preparing input", engine: "Protenix v1", status: "pending" },
    { name: "Running prediction", engine: "Diffusion sampling", status: "pending" },
    { name: "Computing confidence", engine: "ipTM + pLDDT + PAE", status: "pending" },
    { name: "Prediction complete", engine: "Ready for review", status: "pending" },
  ];
}
