import { appendFileSync, readFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";

export interface CostEvent {
  timestamp: string;
  source: "local_gpu" | "tamarind" | "levitate" | "adaptyv" | "claude_api";
  operation: string;
  gpuMinutes?: number;
  costUsd: number;
  runId?: string;
}

export class CostTracker {
  private logPath: string;

  constructor(campaignDir: string) {
    this.logPath = resolve(campaignDir, "cost-log.json");
  }

  /** Append a cost event to the NDJSON log. */
  record(event: Omit<CostEvent, "timestamp">): void {
    mkdirSync(dirname(this.logPath), { recursive: true });
    const entry: CostEvent = {
      ...event,
      timestamp: new Date().toISOString(),
    };
    appendFileSync(this.logPath, JSON.stringify(entry) + "\n");
  }

  /** Sum all costs from the log, grouped by source. */
  getTotal(): { totalUsd: number; bySource: Record<string, number> } {
    if (!existsSync(this.logPath)) {
      return { totalUsd: 0, bySource: {} };
    }

    const lines = readFileSync(this.logPath, "utf-8")
      .split("\n")
      .filter(Boolean);

    let totalUsd = 0;
    const bySource: Record<string, number> = {};

    for (const line of lines) {
      try {
        const event: CostEvent = JSON.parse(line);
        totalUsd += event.costUsd;
        bySource[event.source] = (bySource[event.source] ?? 0) + event.costUsd;
      } catch {
        // Skip malformed lines
      }
    }

    return { totalUsd, bySource };
  }

  /** Format a human-readable cost summary. */
  formatSummary(): string {
    const { totalUsd, bySource } = this.getTotal();
    const lines = ["  Source           Cost"];
    for (const [source, cost] of Object.entries(bySource)) {
      lines.push(`  ${source.padEnd(17)}$${cost.toFixed(2)}`);
    }
    lines.push(`  ${"TOTAL".padEnd(17)}$${totalUsd.toFixed(2)}`);
    return lines.join("\n");
  }
}
