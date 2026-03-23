import { readdirSync, existsSync, statSync, readFileSync } from "fs";
import { join } from "path";

export interface RunManifest {
  runId: string;
  outputDir: string;
  total: number;
  tool: "proteus-ab" | "proteus-prot" | "proteus-fold";
  target?: string;
  pdb?: string;
  chain?: string;
  pid?: number;
  startTime: number;
}

export interface RunStatus {
  stage: number;       // 1-5
  stageName: string;
  stagesTotal: number;
  designsComplete: number;
  designsTotal: number;
  elapsed: number;     // seconds since start
  complete: boolean;
  error: boolean;
}

const AB_STAGES = ["Design", "Inverse Fold", "Refold", "Analysis", "Filter & Rank"];
const AB_TOOLS = ["BoltzGen", "AntiFold", "Protenix-v1", "ipSAE + Metrics", "Quality Filter"];

const PROT_STAGES = ["Design", "AF2 Screening", "Protenix Validation", "Ranking", "Complete"];
const PROT_TOOLS = ["PXDesign", "AlphaFold2", "Protenix-v1", "Composite Score", "Ready for review"];

const FOLD_STAGES = ["Preparing input", "Running prediction", "Computing confidence", "Complete"];
const FOLD_TOOLS = ["Config", "Protenix-v1", "pLDDT + pTM", "Ready for review"];

function countFiles(dir: string, ext: string): number {
  if (!existsSync(dir)) return 0;
  try {
    return readdirSync(dir).filter(f => f.endsWith(ext)).length;
  } catch {
    return 0;
  }
}

function hasFiles(dir: string): boolean {
  if (!existsSync(dir)) return false;
  try {
    return readdirSync(dir).length > 0;
  } catch {
    return false;
  }
}

function isProcessRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export function pollProteusAb(manifest: RunManifest): RunStatus {
  const { outputDir, total, startTime } = manifest;
  const elapsed = Math.floor((Date.now() - startTime) / 1000);

  const designDir = join(outputDir, "intermediate_designs");
  const ifDir = join(outputDir, "intermediate_designs_inverse_folded");
  const finalDir = join(outputDir, "final_ranked_designs");

  // Check from last stage backward
  // Stage 5: Final CSV exists
  if (hasFiles(finalDir)) {
    return { stage: 5, stageName: "Filter & Rank", stagesTotal: 5, designsComplete: total, designsTotal: total, elapsed, complete: true, error: false };
  }

  // Stage 3-4: Check for refold outputs (NPZ files in various locations)
  // Look for fold_out_npz in the design directories
  const refoldDir1 = join(designDir, "fold_out_npz");
  const refoldDir2 = join(ifDir, "fold_out_npz");
  const refoldCount = Math.max(countFiles(refoldDir1, ".npz"), countFiles(refoldDir2, ".npz"));
  if (refoldCount > 0) {
    if (refoldCount >= total) {
      return { stage: 4, stageName: "Analysis", stagesTotal: 5, designsComplete: refoldCount, designsTotal: total, elapsed, complete: false, error: false };
    }
    return { stage: 3, stageName: "Refold", stagesTotal: 5, designsComplete: refoldCount, designsTotal: total, elapsed, complete: false, error: false };
  }

  // Stage 2: Inverse folded files
  const ifCount = countFiles(ifDir, ".cif");
  if (ifCount > 0) {
    if (ifCount >= total) {
      return { stage: 3, stageName: "Refold", stagesTotal: 5, designsComplete: 0, designsTotal: total, elapsed, complete: false, error: false };
    }
    return { stage: 2, stageName: "Inverse Fold", stagesTotal: 5, designsComplete: ifCount, designsTotal: total, elapsed, complete: false, error: false };
  }

  // Stage 1: Design backbone files
  const designCount = countFiles(designDir, ".cif");
  if (designCount > 0) {
    if (designCount >= total) {
      return { stage: 2, stageName: "Inverse Fold", stagesTotal: 5, designsComplete: 0, designsTotal: total, elapsed, complete: false, error: false };
    }
    return { stage: 1, stageName: "Design", stagesTotal: 5, designsComplete: designCount, designsTotal: total, elapsed, complete: false, error: false };
  }

  // Stage 0: Not started or just beginning
  // Check if process is still running
  if (manifest.pid && !isProcessRunning(manifest.pid)) {
    return { stage: 0, stageName: "Design", stagesTotal: 5, designsComplete: 0, designsTotal: total, elapsed, complete: false, error: true };
  }

  return { stage: 1, stageName: "Design", stagesTotal: 5, designsComplete: 0, designsTotal: total, elapsed, complete: false, error: false };
}

export function pollPXDesign(manifest: RunManifest): RunStatus {
  const { outputDir, total, startTime } = manifest;
  const elapsed = Math.floor((Date.now() - startTime) / 1000);

  // Check for final summary.csv in design_outputs subdirectories
  if (existsSync(outputDir)) {
    const designOutputs = join(outputDir, "design_outputs");
    if (existsSync(designOutputs)) {
      try {
        const tasks = readdirSync(designOutputs);
        for (const task of tasks) {
          const summaryPath = join(designOutputs, task, "summary.csv");
          if (existsSync(summaryPath)) {
            return { stage: 5, stageName: "Complete", stagesTotal: 5, designsComplete: total, designsTotal: total, elapsed, complete: true, error: false };
          }
        }
        // Has design_outputs but no summary yet — ranking stage
        if (tasks.length > 0) {
          return { stage: 4, stageName: "Ranking", stagesTotal: 5, designsComplete: total, designsTotal: total, elapsed, complete: false, error: false };
        }
      } catch {
        /* ignore read errors */
      }
    }
  }

  // Count prediction CIF files across seed directories
  let cifCount = 0;
  if (existsSync(outputDir)) {
    try {
      // Traverse: outputDir/<task>/<sample>/seed_*/predictions/*.cif
      const items = readdirSync(outputDir);
      for (const task of items) {
        const taskDir = join(outputDir, task);
        if (!existsSync(taskDir) || !statSync(taskDir).isDirectory()) continue;
        const samples = readdirSync(taskDir);
        for (const sample of samples) {
          const sampleDir = join(taskDir, sample);
          if (!existsSync(sampleDir) || !statSync(sampleDir).isDirectory()) continue;
          const seeds = readdirSync(sampleDir).filter(s => s.startsWith("seed_"));
          for (const seed of seeds) {
            const predDir = join(sampleDir, seed, "predictions");
            cifCount += countFiles(predDir, ".cif");
          }
        }
      }
    } catch {
      /* ignore traversal errors */
    }
  }

  if (cifCount > 0) {
    if (cifCount >= total) {
      return { stage: 2, stageName: "AF2 Screening", stagesTotal: 5, designsComplete: cifCount, designsTotal: total, elapsed, complete: false, error: false };
    }
    return { stage: 1, stageName: "Design", stagesTotal: 5, designsComplete: cifCount, designsTotal: total, elapsed, complete: false, error: false };
  }

  return { stage: 1, stageName: "Design", stagesTotal: 5, designsComplete: 0, designsTotal: total, elapsed, complete: false, error: false };
}

export function pollRunStatus(manifest: RunManifest): RunStatus {
  switch (manifest.tool) {
    case "proteus-ab":
      return pollProteusAb(manifest);
    case "proteus-prot":
      return pollPXDesign(manifest);
    default:
      return { stage: 1, stageName: "Running", stagesTotal: 4, designsComplete: 0, designsTotal: manifest.total, elapsed: Math.floor((Date.now() - manifest.startTime) / 1000), complete: false, error: false };
  }
}

export function getStageNames(tool: string): string[] {
  switch (tool) {
    case "proteus-ab": return AB_STAGES;
    case "proteus-prot": return PROT_STAGES;
    default: return FOLD_STAGES;
  }
}

export function getToolNames(tool: string): string[] {
  switch (tool) {
    case "proteus-ab": return AB_TOOLS;
    case "proteus-prot": return PROT_TOOLS;
    default: return FOLD_TOOLS;
  }
}

export const MANIFEST_PATH = ".proteus/active-run.json";

export function hasProteusDir(projectDir: string): boolean {
  return existsSync(join(projectDir, ".proteus"));
}

export function readManifest(projectDir: string): RunManifest | null {
  const manifestPath = join(projectDir, MANIFEST_PATH);
  if (!existsSync(manifestPath)) return null;
  try {
    const raw = readFileSync(manifestPath, "utf-8");
    return JSON.parse(raw) as RunManifest;
  } catch {
    return null;
  }
}

export function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
