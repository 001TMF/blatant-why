import { readFileSync, existsSync, readdirSync } from "fs";
import { exec } from "child_process";
import { resolve, join } from "path";
import type { MonitorEvent, MonitorCallback } from "./types.js";

export interface CloudJob {
  jobName: string;
  provider: string;
  submittedAt: number;
  status: "pending" | "running" | "complete" | "failed";
}

export class CampaignMonitor {
  private interval: ReturnType<typeof setInterval> | null = null;
  private pollMs: number;
  private campaignDir: string;
  private callbacks: MonitorCallback[] = [];
  private lastFileCount: Map<string, number> = new Map();
  private lastProgressTime: Map<string, number> = new Map();
  private stallThresholdMs = 600000; // 10 minutes
  private cloudJobs: Map<string, CloudJob> = new Map();

  constructor(campaignDir: string, pollMs: number = 5000) {
    this.campaignDir = campaignDir;
    this.pollMs = pollMs;
  }

  /** Register a callback for monitor events. */
  onEvent(callback: MonitorCallback): void {
    this.callbacks.push(callback);
  }

  private emit(event: MonitorEvent): void {
    for (const cb of this.callbacks) {
      cb(event);
    }
  }

  /** Start polling for campaign progress. */
  start(): void {
    if (this.interval) return;
    this.interval = setInterval(() => this.tick(), this.pollMs);
    this.tick(); // immediate first check
  }

  /** Stop polling. */
  stop(): void {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  private tick(): void {
    try {
      const state = this.readState();
      if (!state) return;

      // Find active rounds and runs
      const rounds = (state.rounds as any[]) ?? [];
      for (const round of rounds) {
        const runs = round.runs ?? [];
        for (const run of runs) {
          if (run.status === "running") {
            this.checkRun(run);
          }
        }
      }
    } catch {
      // Silent fail on tick errors
    }
  }

  private checkRun(run: any): void {
    const outputDir = run.output_dir;
    if (!outputDir || !existsSync(outputDir)) return;

    // Count output files
    const fileCount = this.countFiles(outputDir);
    const prevCount = this.lastFileCount.get(run.run_id) ?? 0;

    if (fileCount > prevCount) {
      // Progress detected
      this.lastFileCount.set(run.run_id, fileCount);
      this.lastProgressTime.set(run.run_id, Date.now());

      this.emit({
        type: "progress",
        runId: run.run_id,
        message: `${fileCount} files generated (${run.designs_generated ?? "?"} designs)`,
        data: { fileCount, designsGenerated: run.designs_generated },
      });
    } else {
      // Check for stall
      const lastProgress =
        this.lastProgressTime.get(run.run_id) ?? Date.now();
      if (Date.now() - lastProgress > this.stallThresholdMs) {
        this.emit({
          type: "stall",
          runId: run.run_id,
          message: `No new output for ${Math.round((Date.now() - lastProgress) / 60000)} minutes`,
        });
      }
    }

    // Check for completion markers
    if (this.checkCompletion(outputDir)) {
      const completeMessage = `Run complete: ${fileCount} files`;
      this.emit({
        type: "complete",
        runId: run.run_id,
        message: completeMessage,
        data: { fileCount },
      });
      this.notifyCompletion(run.run_id, completeMessage);
    }

    // Check for error markers
    const logPath = resolve(outputDir, "..", "proteus_ab.log");
    if (existsSync(logPath)) {
      const log = readFileSync(logPath, "utf-8");
      if (
        log.includes("Error") ||
        log.includes("CUDA out of memory") ||
        log.includes("RuntimeError")
      ) {
        this.emit({
          type: "error",
          runId: run.run_id,
          message: "Error detected in pipeline log",
          data: { logTail: log.slice(-500) },
        });
      }
    }
  }

  private checkCompletion(outputDir: string): boolean {
    // Check for final_ranked_designs/ directory with CSV files
    const finalDir = join(outputDir, "final_ranked_designs");
    if (existsSync(finalDir)) {
      const csvFiles = readdirSync(finalDir).filter((f) => f.endsWith(".csv"));
      return csvFiles.length > 0;
    }
    // Check for summary.csv (PXDesign)
    const summaryPath = join(outputDir, "summary.csv");
    return existsSync(summaryPath);
  }

  private countFiles(dir: string): number {
    try {
      return readdirSync(dir, { recursive: true }).length;
    } catch {
      return 0;
    }
  }

  /** Send a desktop notification when a job completes. */
  private notifyCompletion(runId: string, message: string): void {
    // Terminal bell
    process.stdout.write("\x07");

    // Try native notification (Linux notify-send, macOS osascript)
    const title = "Proteus — Job Complete";
    const isLinux = process.platform === "linux";
    const isMac = process.platform === "darwin";

    if (isLinux) {
      exec(`notify-send "${title}" "${message}" 2>/dev/null`);
    } else if (isMac) {
      exec(
        `osascript -e 'display notification "${message}" with title "${title}"' 2>/dev/null`,
      );
    }
  }

  /** Track a cloud job that was submitted by an agent. */
  trackCloudJob(jobName: string, provider: string): void {
    this.cloudJobs.set(jobName, {
      jobName,
      provider,
      submittedAt: Date.now(),
      status: "pending",
    });
  }

  /** Update the status of a tracked cloud job. */
  updateCloudJob(jobName: string, status: CloudJob["status"]): void {
    const job = this.cloudJobs.get(jobName);
    if (job) {
      job.status = status;
      if (status === "complete" || status === "failed") {
        this.emit({
          type: status === "complete" ? "complete" : "error",
          runId: jobName,
          message: `Cloud job ${jobName} (${job.provider}): ${status}`,
          data: {
            provider: job.provider,
            elapsedMs: Date.now() - job.submittedAt,
          },
        });
      }
    }
  }

  /** Get all tracked cloud jobs, optionally filtered by status. */
  getCloudJobs(statusFilter?: CloudJob["status"]): CloudJob[] {
    const jobs = Array.from(this.cloudJobs.values());
    if (statusFilter) {
      return jobs.filter((j) => j.status === statusFilter);
    }
    return jobs;
  }

  private readState(): Record<string, any> | null {
    const statePath = resolve(this.campaignDir, "campaign_log.json");
    try {
      return JSON.parse(readFileSync(statePath, "utf-8"));
    } catch {
      return null;
    }
  }
}
