import { appendFileSync, mkdirSync, existsSync, readFileSync } from "fs";
import { resolve } from "path";

export interface LogEntry {
  timestamp: string;
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  metadata?: Record<string, unknown>;
}

export class ConversationLogger {
  private logPath: string;

  constructor(campaignDir?: string) {
    const baseDir = campaignDir ?? ".proteus";
    mkdirSync(baseDir, { recursive: true });
    const date = new Date().toISOString().slice(0, 10);
    this.logPath = resolve(baseDir, `conversation_${date}.jsonl`);
  }

  log(entry: Omit<LogEntry, "timestamp">): void {
    const full: LogEntry = { ...entry, timestamp: new Date().toISOString() };
    appendFileSync(this.logPath, JSON.stringify(full) + "\n");
  }

  logUser(content: string): void {
    this.log({ role: "user", content });
  }

  logAssistant(content: string): void {
    this.log({ role: "assistant", content });
  }

  logTool(name: string, result?: string): void {
    this.log({ role: "tool", content: name, metadata: result ? { result } : undefined });
  }

  logDecision(decision: string, reasoning: string, alternatives?: string[]): void {
    this.log({
      role: "system",
      content: `DECISION: ${decision}`,
      metadata: { reasoning, alternatives },
    });
  }

  exportMarkdown(): string {
    if (!existsSync(this.logPath)) return "No conversation log found.";
    const lines = readFileSync(this.logPath, "utf-8").split("\n").filter(Boolean);
    const md: string[] = ["# Proteus Conversation Log\n"];
    for (const line of lines) {
      try {
        const entry: LogEntry = JSON.parse(line);
        const time = entry.timestamp.slice(11, 19);
        if (entry.role === "user") {
          md.push(`### [${time}] User\n${entry.content}\n`);
        } else if (entry.role === "assistant") {
          md.push(`### [${time}] Proteus\n${entry.content}\n`);
        } else if (entry.role === "tool") {
          md.push(`> Tool: ${entry.content}\n`);
        } else if (entry.role === "system") {
          md.push(`**${entry.content}**\n> Reasoning: ${(entry.metadata as Record<string, unknown>)?.reasoning ?? "\u2014"}\n`);
        }
      } catch {
        /* skip malformed */
      }
    }
    return md.join("\n");
  }

  exportCSV(): string {
    if (!existsSync(this.logPath)) return "";
    const lines = readFileSync(this.logPath, "utf-8").split("\n").filter(Boolean);
    const rows = ["timestamp,role,content"];
    for (const line of lines) {
      try {
        const e: LogEntry = JSON.parse(line);
        rows.push(`${e.timestamp},${e.role},"${e.content.replace(/"/g, '""').slice(0, 500)}"`);
      } catch {
        /* skip malformed */
      }
    }
    return rows.join("\n");
  }

  getLogPath(): string {
    return this.logPath;
  }
}
