import { readFileSync, existsSync, readdirSync } from "fs";
import { resolve, join } from "path";

/**
 * Pipeline stages for design runs.
 * Order matters: stages progress linearly from generation to ranking.
 */
export const PIPELINE_STAGES = [
  { id: "generation", label: "Generating designs", weight: 0.4 },
  { id: "folding", label: "Structure prediction", weight: 0.25 },
  { id: "scoring", label: "Scoring", weight: 0.15 },
  { id: "screening", label: "Screening liabilities", weight: 0.1 },
  { id: "ranking", label: "Ranking candidates", weight: 0.1 },
] as const;

export type StageId = (typeof PIPELINE_STAGES)[number]["id"];

export type StageStatus = "pending" | "running" | "complete" | "failed";

export interface StageInfo {
  id: StageId;
  label: string;
  status: StageStatus;
  progress?: number; // 0-1 within the stage
  message?: string;
}

export interface RunManifest {
  runId: string;
  campaignDir: string;
  outputDir: string;
  tool: "boltzgen" | "pxdesign" | "protenix";
  provider: "tamarind" | "levitate" | "local" | "ssh";
  totalDesigns: number;
  startedAt: number;
  stages: StageInfo[];
  currentStage: StageId;
  designsGenerated: number;
  designsScored: number;
  elapsedMs: number;
  estimatedRemainingMs?: number;
}

/**
 * Poll a run directory for progress and return an updated manifest.
 */
export function pollRunStatus(manifest: RunManifest): RunManifest {
  const now = Date.now();
  const updated: RunManifest = {
    ...manifest,
    elapsedMs: now - manifest.startedAt,
  };

  const outputDir = manifest.outputDir;
  if (!existsSync(outputDir)) return updated;

  // Count generated designs (CIF/PDB files in output)
  const designFiles = countFilesByExtension(outputDir, [
    ".cif",
    ".pdb",
    ".mmcif",
  ]);
  updated.designsGenerated = designFiles;

  // Count scored designs (CSV rows or score JSON files)
  const scoreFiles = countFilesByExtension(outputDir, [".csv", ".scores.json"]);
  updated.designsScored = scoreFiles;

  // Determine current stage based on output
  updated.stages = PIPELINE_STAGES.map((stage) => {
    const info: StageInfo = {
      id: stage.id,
      label: stage.label,
      status: "pending",
    };

    switch (stage.id) {
      case "generation": {
        if (designFiles >= manifest.totalDesigns) {
          info.status = "complete";
          info.progress = 1;
        } else if (designFiles > 0) {
          info.status = "running";
          info.progress = designFiles / manifest.totalDesigns;
          info.message = `${designFiles}/${manifest.totalDesigns}`;
        }
        break;
      }
      case "folding": {
        const foldDir = join(outputDir, "structures");
        if (existsSync(foldDir)) {
          const foldedCount = countFilesByExtension(foldDir, [
            ".cif",
            ".pdb",
          ]);
          if (foldedCount >= designFiles && designFiles > 0) {
            info.status = "complete";
            info.progress = 1;
          } else if (foldedCount > 0) {
            info.status = "running";
            info.progress = designFiles > 0 ? foldedCount / designFiles : 0;
            info.message = `${foldedCount}/${designFiles}`;
          }
        }
        break;
      }
      case "scoring": {
        if (scoreFiles >= designFiles && designFiles > 0) {
          info.status = "complete";
          info.progress = 1;
        } else if (scoreFiles > 0) {
          info.status = "running";
          info.progress = designFiles > 0 ? scoreFiles / designFiles : 0;
        }
        break;
      }
      case "screening": {
        const screenPath = join(outputDir, "screening_results.csv");
        if (existsSync(screenPath)) {
          info.status = "complete";
          info.progress = 1;
        }
        break;
      }
      case "ranking": {
        const rankedDir = join(outputDir, "final_ranked_designs");
        const summaryPath = join(outputDir, "summary.csv");
        if (
          (existsSync(rankedDir) && readdirSync(rankedDir).length > 0) ||
          existsSync(summaryPath)
        ) {
          info.status = "complete";
          info.progress = 1;
        }
        break;
      }
    }

    return info;
  });

  // Determine current stage (first non-complete)
  const currentStage = updated.stages.find((s) => s.status !== "complete");
  if (currentStage) {
    updated.currentStage = currentStage.id;
    if (currentStage.status === "pending") {
      currentStage.status = "running";
    }
  } else {
    updated.currentStage = "ranking";
  }

  // Estimate remaining time based on generation rate
  if (
    updated.currentStage === "generation" &&
    updated.designsGenerated > 0 &&
    updated.elapsedMs > 0
  ) {
    const rate = updated.designsGenerated / updated.elapsedMs;
    const remaining = manifest.totalDesigns - updated.designsGenerated;
    // Apply stage weights: generation is 40% of total time
    const generationRemaining = remaining / rate;
    updated.estimatedRemainingMs = generationRemaining / 0.4;
  }

  // Check for error markers
  const logPath = resolve(outputDir, "..", "proteus_ab.log");
  if (existsSync(logPath)) {
    const logContent = readFileSync(logPath, "utf-8");
    if (
      logContent.includes("Error") ||
      logContent.includes("CUDA out of memory") ||
      logContent.includes("RuntimeError")
    ) {
      const failedStage = updated.stages.find(
        (s) => s.status === "running",
      );
      if (failedStage) {
        failedStage.status = "failed";
        failedStage.message = "Error detected in pipeline log";
      }
    }
  }

  return updated;
}

/**
 * Create an initial manifest for a new run.
 */
export function createManifest(opts: {
  runId: string;
  campaignDir: string;
  outputDir: string;
  tool: RunManifest["tool"];
  provider: RunManifest["provider"];
  totalDesigns: number;
}): RunManifest {
  return {
    ...opts,
    startedAt: Date.now(),
    stages: PIPELINE_STAGES.map((stage) => ({
      id: stage.id,
      label: stage.label,
      status: "pending" as StageStatus,
    })),
    currentStage: "generation",
    designsGenerated: 0,
    designsScored: 0,
    elapsedMs: 0,
  };
}

/**
 * Format elapsed time as human-readable string.
 */
export function formatElapsed(ms: number): string {
  if (ms < 1000) return "<1s";
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

/**
 * Count files with given extensions recursively in a directory.
 */
function countFilesByExtension(dir: string, extensions: string[]): number {
  try {
    const allFiles = readdirSync(dir, { recursive: true }) as string[];
    return allFiles.filter((f) =>
      extensions.some((ext) => f.endsWith(ext)),
    ).length;
  } catch {
    return 0;
  }
}
