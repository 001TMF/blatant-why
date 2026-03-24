import {
  appendFileSync,
  readFileSync,
  existsSync,
  mkdirSync,
  writeFileSync,
} from "fs";
import { resolve, dirname } from "path";

export type LogEntryType =
  | "user"
  | "assistant"
  | "tool_call"
  | "tool_result"
  | "decision"
  | "error"
  | "system";

export interface LogEntry {
  timestamp: string;
  type: LogEntryType;
  content: string;
  metadata?: Record<string, unknown>;
}

/**
 * JSONL conversation logger for campaign audit trails.
 * Each line is a self-contained JSON object, safe for streaming writes.
 */
export class ConversationLog {
  private logPath: string;

  constructor(campaignDir: string, filename: string = "conversation.jsonl") {
    this.logPath = resolve(campaignDir, filename);
    mkdirSync(dirname(this.logPath), { recursive: true });
  }

  private append(entry: LogEntry): void {
    appendFileSync(this.logPath, JSON.stringify(entry) + "\n");
  }

  /** Log a user message. */
  logUser(content: string): void {
    this.append({
      timestamp: new Date().toISOString(),
      type: "user",
      content,
    });
  }

  /** Log an assistant response. */
  logAssistant(content: string): void {
    this.append({
      timestamp: new Date().toISOString(),
      type: "assistant",
      content,
    });
  }

  /** Log a tool invocation. */
  logTool(
    toolName: string,
    input: Record<string, unknown>,
    output: string,
    durationMs?: number,
  ): void {
    this.append({
      timestamp: new Date().toISOString(),
      type: "tool_call",
      content: `${toolName}: ${output.substring(0, 500)}`,
      metadata: {
        toolName,
        input,
        durationMs,
        outputLength: output.length,
      },
    });
  }

  /** Log a decision point (campaign gate, approval, etc). */
  logDecision(
    decision: string,
    rationale: string,
    outcome: "approved" | "rejected" | "deferred",
  ): void {
    this.append({
      timestamp: new Date().toISOString(),
      type: "decision",
      content: decision,
      metadata: { rationale, outcome },
    });
  }

  /** Log an error. */
  logError(error: string, context?: Record<string, unknown>): void {
    this.append({
      timestamp: new Date().toISOString(),
      type: "error",
      content: error,
      metadata: context,
    });
  }

  /** Log a system event (phase transitions, etc). */
  logSystem(content: string, metadata?: Record<string, unknown>): void {
    this.append({
      timestamp: new Date().toISOString(),
      type: "system",
      content,
      metadata,
    });
  }

  /** Read all entries from the log file. */
  readAll(): LogEntry[] {
    if (!existsSync(this.logPath)) return [];
    const lines = readFileSync(this.logPath, "utf-8")
      .split("\n")
      .filter(Boolean);
    const entries: LogEntry[] = [];
    for (const line of lines) {
      try {
        entries.push(JSON.parse(line) as LogEntry);
      } catch {
        // Skip malformed lines
      }
    }
    return entries;
  }

  /** Export the conversation as a Markdown document. */
  exportMarkdown(): string {
    const entries = this.readAll();
    if (entries.length === 0) return "# Campaign Conversation Log\n\n*No entries.*\n";

    const lines: string[] = ["# Campaign Conversation Log\n"];
    const startTime = entries[0].timestamp;
    lines.push(`*Started: ${startTime}*\n`);

    for (const entry of entries) {
      const time = entry.timestamp.split("T")[1]?.split(".")[0] ?? "";
      switch (entry.type) {
        case "user":
          lines.push(`## User (${time})\n`);
          lines.push(entry.content + "\n");
          break;
        case "assistant":
          lines.push(`## Proteus (${time})\n`);
          lines.push(entry.content + "\n");
          break;
        case "tool_call": {
          const tool = (entry.metadata?.toolName as string) ?? "unknown";
          const dur = entry.metadata?.durationMs
            ? ` (${entry.metadata.durationMs}ms)`
            : "";
          lines.push(`> **Tool**: \`${tool}\`${dur}\n`);
          break;
        }
        case "decision": {
          const outcome = (entry.metadata?.outcome as string) ?? "";
          lines.push(
            `### Decision: ${entry.content} [${outcome.toUpperCase()}]\n`,
          );
          if (entry.metadata?.rationale) {
            lines.push(`*Rationale: ${entry.metadata.rationale}*\n`);
          }
          break;
        }
        case "error":
          lines.push(`> **Error** (${time}): ${entry.content}\n`);
          break;
        case "system":
          lines.push(`---\n*${entry.content}*\n`);
          break;
      }
    }

    return lines.join("\n");
  }

  /** Export the conversation as CSV. */
  exportCSV(): string {
    const entries = this.readAll();
    const header = "timestamp,type,content\n";
    const rows = entries.map((e) => {
      const content = e.content
        .replace(/"/g, '""')
        .replace(/\n/g, " ")
        .substring(0, 500);
      return `"${e.timestamp}","${e.type}","${content}"`;
    });
    return header + rows.join("\n") + "\n";
  }

  /** Write the markdown export to a file. */
  saveMarkdown(outputPath: string): void {
    mkdirSync(dirname(outputPath), { recursive: true });
    writeFileSync(outputPath, this.exportMarkdown());
  }

  /** Write the CSV export to a file. */
  saveCSV(outputPath: string): void {
    mkdirSync(dirname(outputPath), { recursive: true });
    writeFileSync(outputPath, this.exportCSV());
  }

  /** Get entry count by type. */
  stats(): Record<LogEntryType, number> {
    const entries = this.readAll();
    const counts: Record<string, number> = {};
    for (const e of entries) {
      counts[e.type] = (counts[e.type] ?? 0) + 1;
    }
    return counts as Record<LogEntryType, number>;
  }
}
