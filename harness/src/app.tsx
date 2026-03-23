import React, { useState, useCallback, useRef, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import { execSync } from "child_process";
import { writeFileSync, mkdirSync, readFileSync, existsSync, readdirSync, statSync } from "fs";
import { resolve, basename } from "path";
import { renderBanner } from "./banner.js";
import { ProteusMode, cycleMode, getModeConfig } from "./modes.js";
import { theme } from "./theme.js";
import { Spinner } from "./components/Spinner.js";
import { MarkdownText } from "./components/MarkdownText.js";
import { ScrollableOutput } from "./components/ScrollableOutput.js";
import { AgentTeamStatus } from "./components/AgentTeamStatus.js";
import { CostSummary } from "./components/CostSummary.js";
import { LabApproval } from "./components/LabApproval.js";
import { useInputHistory } from "./hooks/useInputHistory.js";
import { useTerminalSize } from "./hooks/useTerminalSize.js";
import { useCampaignState } from "./hooks/useCampaignState.js";
import { handleSlashCommand, getCompletions } from "./slashCommands.js";
import { renderProgress, RunProgress } from "./progress.js";
import { renderResults, DesignResult } from "./results.js";
import { StreamEvent, AgentConfig } from "./agent.js";
import { PipelineWatch } from "./components/PipelineWatch.js";
import { readManifest, hasProteusDir, RunManifest } from "./watchRun.js";
import { ConversationLogger } from "./conversationLog.js";

type Message =
  | { type: "user"; text: string }
  | { type: "assistant"; text: string }
  | { type: "tool_use"; name: string }
  | { type: "progress"; data: RunProgress }
  | { type: "results"; data: DesignResult[] }
  | { type: "error"; text: string };

interface AppProps {
  queryFn: (input: string, sessionId?: string, abortController?: AbortController) => AsyncGenerator<StreamEvent>;
  initialMode: ProteusMode;
  configRef: AgentConfig;
}

// Internal Claude Code tools that should not be shown to the user
const HIDDEN_TOOLS = new Set([
  "TodoWrite", "TodoRead", "Task", "TaskCreate", "TaskUpdate", "TaskList",
  "Write", "Read", "Edit", "Glob", "Grep", "Bash", "BashOutput",
  "WebSearch", "WebFetch", "Agent", "EnterPlanMode", "ExitPlanMode",
  "AskUserQuestion", "NotebookEdit",
]);

// Map technical MCP tool names to human-readable descriptions
function humanizeToolName(name: string): string | null {
  // Hide internal tools
  if (HIDDEN_TOOLS.has(name)) return null;

  // Map known MCP tool prefixes to readable names
  const mappings: Record<string, string> = {
    "pdb_search": "Searching PDB",
    "pdb_fetch_structure": "Fetching PDB structure",
    "pdb_get_chains": "Analyzing chains",
    "pdb_interface_residues": "Analyzing interface",
    "pdb_download": "Downloading structure",
    "uniprot_search": "Searching UniProt",
    "uniprot_fetch_protein": "Fetching protein details",
    "uniprot_get_domains": "Analyzing domains",
    "uniprot_get_variants": "Checking variants",
    "sabdab_search": "Searching SAbDab",
    "screen_liabilities": "Screening liabilities",
    "screen_developability": "Screening developability",
    "screen_composite": "Running composite screen",
    "score_ipsae": "Computing ipSAE scores",
    
    "interpret_scores": "Interpreting scores",
  };

  if (mappings[name]) return mappings[name];

  // For unknown tools, show if they look like MCP tools (contain underscore)
  if (name.includes("_")) return name.replace(/_/g, " ");

  // Hide anything else that looks internal
  return null;
}

/**
 * Kill any child processes spawned by claude-code query.
 * Best-effort cleanup — errors are silently ignored.
 */
function killChildProcesses() {
  try {
    const pid = process.pid;
    execSync(`pkill -P ${pid} 2>/dev/null || true`, { stdio: "ignore" });
  } catch {
    // Ignore errors — best effort cleanup
  }
}

interface LastSession {
  sessionId: string;
  campaignDir?: string;
  timestamp: string;
}

interface CampaignEntry {
  name: string;
  status: string;
  lastUpdated: string;
  dir: string;
}

function getLastSessionPath(projectDir: string): string {
  return resolve(projectDir, ".proteus", "last-session.json");
}

function loadLastSession(projectDir: string): LastSession | null {
  const sessionPath = getLastSessionPath(projectDir);
  if (!existsSync(sessionPath)) return null;
  try {
    const data = JSON.parse(readFileSync(sessionPath, "utf-8")) as LastSession;
    // Only resume if less than 24 hours old
    const age = Date.now() - new Date(data.timestamp).getTime();
    if (age > 24 * 60 * 60 * 1000) return null;
    return data;
  } catch {
    return null;
  }
}

function saveLastSession(projectDir: string, sessionId: string, campaignDir?: string): void {
  try {
    const proteusDir = resolve(projectDir, ".proteus");
    mkdirSync(proteusDir, { recursive: true });
    const data: LastSession = {
      sessionId,
      ...(campaignDir ? { campaignDir } : {}),
      timestamp: new Date().toISOString(),
    };
    writeFileSync(getLastSessionPath(projectDir), JSON.stringify(data, null, 2));
  } catch {
    // Silent — best effort
  }
}

function listCampaigns(projectDir: string): CampaignEntry[] {
  const campaignsDir = resolve(projectDir, "campaigns");
  if (!existsSync(campaignsDir)) return [];

  const entries: CampaignEntry[] = [];
  try {
    const targets = readdirSync(campaignsDir);
    for (const target of targets) {
      const targetDir = resolve(campaignsDir, target);
      if (!statSync(targetDir).isDirectory()) continue;
      const runs = readdirSync(targetDir);
      for (const run of runs) {
        const runDir = resolve(targetDir, run);
        if (!statSync(runDir).isDirectory()) continue;
        const logPath = resolve(runDir, "campaign_log.json");
        if (existsSync(logPath)) {
          try {
            const log = JSON.parse(readFileSync(logPath, "utf-8"));
            entries.push({
              name: log.name ?? `${target}/${run}`,
              status: log.status ?? "unknown",
              lastUpdated: log.updated ?? statSync(logPath).mtime.toISOString(),
              dir: runDir,
            });
          } catch {
            entries.push({
              name: `${target}/${run}`,
              status: "unknown",
              lastUpdated: statSync(runDir).mtime.toISOString(),
              dir: runDir,
            });
          }
        }
      }
    }
  } catch {
    // Silent
  }
  // Sort by most recently updated first
  entries.sort((a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime());
  return entries;
}

export function App({ queryFn, initialMode, configRef }: AppProps) {
  const [mode, setMode] = useState<ProteusMode>(initialMode);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [watching, setWatching] = useState(false);
  const [activeRun, setActiveRun] = useState<RunManifest | null>(null);
  const [showLabApproval, setShowLabApproval] = useState(false);
  const [showCosts, setShowCosts] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const { currentInput, setCurrentInput, addToHistory } = useInputHistory();
  const modeConfig = getModeConfig(mode);
  const completions = getCompletions(currentInput);
  const { width: termWidth, height: termHeight } = useTerminalSize();
  const campaign = useCampaignState(configRef.projectDir);
  const contentHeight = Math.max(termHeight - 12, 5);

  // Check for previous session on startup
  useEffect(() => {
    const lastSession = loadLastSession(configRef.projectDir);
    if (lastSession) {
      setSessionId(lastSession.sessionId);
      setMessages((prev) => [
        ...prev,
        {
          type: "assistant",
          text: `Resumed previous session from ${new Date(lastSession.timestamp).toLocaleString()}.${lastSession.campaignDir ? ` Campaign: ${basename(lastSession.campaignDir)}` : ""}\nType /resume to switch campaigns or start fresh.`,
        },
      ]);
    }
  }, [configRef.projectDir]);

  // Persist session whenever sessionId changes
  useEffect(() => {
    if (sessionId) {
      saveLastSession(configRef.projectDir, sessionId, campaign.campaignDir ?? undefined);
    }
  }, [sessionId, campaign.campaignDir, configRef.projectDir]);

  // Conversation logger for audit trail
  const loggerRef = useRef<ConversationLogger>(
    new ConversationLogger(resolve(configRef.projectDir, ".proteus"))
  );

  // Track the last displayed text to prevent duplicates
  const lastDisplayedRef = useRef<string>("");
  const abortRef = useRef<AbortController | null>(null);
  const cancellingRef = useRef(false);
  const lastCtrlCRef = useRef<number>(0);

  useInput((input, key) => {
    // Double Ctrl+C within 1 second = exit
    if (input === 'c' && key.ctrl) {
      const now = Date.now();
      if (now - lastCtrlCRef.current < 1000) {
        // Double Ctrl+C — exit
        process.exit(0);
        return;
      }
      lastCtrlCRef.current = now;

      // Single Ctrl+C — cancel current operation
      if (abortRef.current) {
        abortRef.current.abort();
        cancellingRef.current = true;
        abortRef.current = null;
        setLoading(false);
        setActiveTool(null);
        setMessages((prev) => [
          ...prev,
          { type: "assistant", text: "Cancelled." },
        ]);

        // Force kill any child processes spawned by claude-code query
        killChildProcesses();

        // Safety: if the query generator doesn't finish within 2 seconds,
        // force-reset the cancelling flag so the user can type again
        setTimeout(() => {
          if (cancellingRef.current) {
            cancellingRef.current = false;
          }
        }, 2000);
      }
      // Also kill background pipeline if active
      if (activeRun?.pid) {
        try {
          process.kill(activeRun.pid, "SIGTERM");
          // Force kill after 1 second if still running
          setTimeout(() => {
            try { process.kill(activeRun.pid!, "SIGKILL"); } catch {}
          }, 1000);
        } catch {}
      }
      return;
    }

    // Escape — dismiss overlay panels, interrupt agent query, or exit watch mode
    if (key.escape) {
      if (showCosts) {
        setShowCosts(false);
        return;
      }
      if (showTeam) {
        setShowTeam(false);
        return;
      }
      if (watching) {
        setWatching(false);
        return;
      }
      if (abortRef.current) {
        abortRef.current.abort();
        cancellingRef.current = true;
        abortRef.current = null;
        setLoading(false);
        setActiveTool(null);
        setMessages((prev) => [
          ...prev,
          { type: "assistant", text: "Interrupted." },
        ]);
      }
      return;
    }

    // Tab autocomplete
    if (key.tab && !key.shift && completions.length > 0) {
      setCurrentInput(completions[0].name + " ");
      return;
    }

    // Shift+Tab to cycle modes
    if (key.shift && key.tab) {
      setMode((prev) => {
        const next = cycleMode(prev);
        configRef.mode = next;
        return next;
      });
    }
  });

  const handleSubmit = useCallback(
    async (value: string) => {
      if (!value.trim()) return;
      const trimmed = value.trim();

      // Reset input
      setCurrentInput("");
      addToHistory(trimmed);

      // Handle /watch locally — toggle pipeline watch display (works even during loading)
      if (trimmed === "/watch" || trimmed.startsWith("/watch ")) {
        const manifest = readManifest(configRef.projectDir);
        if (manifest) {
          setActiveRun(manifest);
          setWatching(true);
          setMessages((prev) => [
            ...prev,
            { type: "user", text: trimmed },
          ]);
        } else if (hasProteusDir(configRef.projectDir)) {
          // .proteus/ directory exists but manifest not yet written — pipeline is starting
          setMessages((prev) => [
            ...prev,
            { type: "user", text: trimmed },
            { type: "assistant", text: "Pipeline is starting... manifest not ready yet. Try /watch again in a few seconds." },
          ]);
        } else {
          setMessages((prev) => [
            ...prev,
            { type: "user", text: trimmed },
            { type: "assistant", text: "No active design run found. Start a design campaign first." },
          ]);
        }
        return;
      }

      // Check slash commands (these always work, even during loading)
      const cmdResult = handleSlashCommand(trimmed);
      if (cmdResult.handled) {
        // Handle local UI commands that toggle component visibility
        if (cmdResult.local === "approve_lab") {
          setMessages((prev) => [...prev, { type: "user", text: trimmed }]);
          setShowLabApproval(true);
          return;
        }
        if (cmdResult.local === "show_costs") {
          setMessages((prev) => [...prev, { type: "user", text: trimmed }]);
          setShowCosts(true);
          return;
        }
        if (cmdResult.local === "show_team") {
          setMessages((prev) => [...prev, { type: "user", text: trimmed }]);
          setShowTeam(true);
          return;
        }
        if (cmdResult.local === "export_markdown" || cmdResult.local === "export_csv") {
          const logger = loggerRef.current;
          const isCsv = cmdResult.local === "export_csv";
          const ext = isCsv ? "csv" : "md";
          const content = isCsv ? logger.exportCSV() : logger.exportMarkdown();
          if (!content) {
            setMessages((prev) => [
              ...prev,
              { type: "user", text: trimmed },
              { type: "assistant", text: "No conversation log found to export." },
            ]);
            return;
          }
          const exportDir = resolve(configRef.projectDir, ".proteus");
          mkdirSync(exportDir, { recursive: true });
          const date = new Date().toISOString().slice(0, 10);
          const time = new Date().toISOString().slice(11, 19).replace(/:/g, "");
          const exportPath = resolve(exportDir, `conversation_export_${date}_${time}.${ext}`);
          writeFileSync(exportPath, content);
          setMessages((prev) => [
            ...prev,
            { type: "user", text: trimmed },
            { type: "assistant", text: `Conversation log exported to:\n${exportPath}` },
          ]);
          return;
        }
        if (cmdResult.local === "resume_campaign") {
          const campaigns = listCampaigns(configRef.projectDir);
          if (campaigns.length === 0) {
            setMessages((prev) => [
              ...prev,
              { type: "user", text: trimmed },
              { type: "assistant", text: "No previous campaigns found in campaigns/ directory.\nStart a new campaign with /campaign or describe your target." },
            ]);
          } else {
            const lines = [
              "Previous campaigns:\n",
              ...campaigns.map((c, i) => {
                const date = new Date(c.lastUpdated).toLocaleString();
                return `  ${i + 1}. ${c.name}  [${c.status}]  (${date})`;
              }),
              "\nReply with the number to resume, or start a new campaign with /campaign.",
            ];
            setMessages((prev) => [
              ...prev,
              { type: "user", text: trimmed },
              { type: "assistant", text: lines.join("\n") },
            ]);
          }
          return;
        }
        setMessages((prev) => [
          ...prev,
          { type: "user", text: trimmed },
          { type: "assistant", text: cmdResult.output ?? "" },
        ]);
        return;
      }

      // Don't start a new agent query while one is running
      if (loading) {
        setMessages((prev) => [
          ...prev,
          { type: "user", text: trimmed },
          { type: "assistant", text: "Processing... please wait for the current task to complete." },
        ]);
        return;
      }

      // Don't start a new query while cancellation is in progress
      if (cancellingRef.current) {
        return;
      }

      // Add user message
      setMessages((prev) => [...prev, { type: "user", text: trimmed }]);
      loggerRef.current.logUser(trimmed);
      setLoading(true);

      let accumulatedText = "";
      lastDisplayedRef.current = "";

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const event of queryFn(trimmed, sessionId ?? undefined, controller)) {
          switch (event.type) {
            case "text_delta":
              accumulatedText += event.text;
              break;
            case "text_complete":
              if (accumulatedText.trim()) {
                const text = accumulatedText;
                // Deduplicate: skip if this exact text was just displayed
                if (text.trim() !== lastDisplayedRef.current.trim()) {
                  setMessages((prev) => [...prev, { type: "assistant", text }]);
                  lastDisplayedRef.current = text;
                  loggerRef.current.logAssistant(text);
                }
              }
              accumulatedText = "";
              break;
            case "tool_start": {
              if (accumulatedText.trim()) {
                const text = accumulatedText;
                if (text.trim() !== lastDisplayedRef.current.trim()) {
                  setMessages((prev) => [...prev, { type: "assistant", text }]);
                  lastDisplayedRef.current = text;
                  loggerRef.current.logAssistant(text);
                }
                accumulatedText = "";
              }
              const displayName = humanizeToolName(event.name);
              setActiveTool(displayName);
              loggerRef.current.logTool(event.name);
              if (displayName) {
                setMessages((prev) => [
                  ...prev,
                  { type: "tool_use", name: displayName },
                ]);
              }
              break;
            }
            case "tool_end":
              setActiveTool(null);
              // Check if agent just launched a pipeline (may have written manifest)
              // Always re-read — manifest can be written at any point during execution
              {
                const manifest = readManifest(configRef.projectDir);
                if (manifest) {
                  setActiveRun(manifest);
                }
              }
              break;
            case "result":
              // Only show result text if nothing was streamed (fallback)
              if (event.text && !lastDisplayedRef.current) {
                setMessages((prev) => [
                  ...prev,
                  { type: "assistant", text: event.text },
                ]);
              }
              break;
            case "session_init":
              setSessionId(event.sessionId);
              break;
            case "error":
              setMessages((prev) => [
                ...prev,
                { type: "error", text: event.message },
              ]);
              break;
          }
        }
        // Flush any remaining accumulated text
        if (accumulatedText.trim()) {
          const text = accumulatedText;
          if (text.trim() !== lastDisplayedRef.current.trim()) {
            setMessages((prev) => [...prev, { type: "assistant", text }]);
          }
        }
      } catch (err: unknown) {
        // Don't show abort errors — already handled by Ctrl+C/Esc
        if (cancellingRef.current) {
          return;
        }
        const msg = err instanceof Error ? err.message : String(err);
        setMessages((prev) => [...prev, { type: "error", text: msg }]);
      } finally {
        setLoading(false);
        setActiveTool(null);
        abortRef.current = null;
        cancellingRef.current = false;
      }
    },
    [queryFn, setCurrentInput, addToHistory, sessionId, loading],
  );

  return (
    <Box flexDirection="column" width={termWidth} height={termHeight}>
      <Text>{""}</Text>
      {/* Banner */}
      <Text>{renderBanner(modeConfig.displayName)}</Text>
      <Text dimColor>{"  " + "─".repeat(Math.max(termWidth - 4, 20))}</Text>
      <Text>{""}</Text>

      {/* Scrollable message area */}
      {!watching && (
        <ScrollableOutput height={contentHeight}>
          {messages.map((msg, i) => {
            switch (msg.type) {
              case "user":
                return (
                  <Text key={i}>
                    <Text color="#4CAF50">{"  ◆ "}</Text>
                    <Text color="#A0A0A0">{msg.text}</Text>
                  </Text>
                );
              case "assistant":
                return <MarkdownText key={i}>{msg.text}</MarkdownText>;
              case "progress":
                return <Text key={i}>{renderProgress(msg.data)}</Text>;
              case "results":
                return <Text key={i}>{renderResults(msg.data)}</Text>;
              case "tool_use":
                return (
                  <Text key={i}>
                    <Text dimColor>{"    ○ Using: "}</Text>
                    <Text color="#80DEEA">{msg.name}</Text>
                  </Text>
                );
              case "error":
                return (
                  <Box key={i}>
                    <Text color="#FF5252" bold>{"  ✗ "}</Text>
                    <Text color="#FF5252">{msg.text}</Text>
                  </Box>
                );
            }
          })}
        </ScrollableOutput>
      )}

      {/* Live pipeline watch */}
      {watching && activeRun && (
        <Box flexDirection="column" height={contentHeight}>
          <PipelineWatch
            manifest={activeRun}
            onComplete={() => {
              setWatching(false);
              setMessages((prev) => [
                ...prev,
                { type: "assistant", text: "Design run completed! Use /results to see the final candidates." },
              ]);
            }}
          />
        </Box>
      )}

      {/* Lab approval dialog */}
      {showLabApproval && (
        <LabApproval
          campaignName={campaign.state?.name as string ?? "Current Campaign"}
          numCandidates={(campaign.state?.candidates as number) ?? 0}
          estimatedCost={(campaign.state?.estimatedCost as number) ?? 0}
          onConfirm={() => {
            try {
              // Write approval to campaign dir (matches adaptyv server check)
              const campaignDir = campaign.campaignDir ?? resolve(configRef.projectDir, ".proteus");
              const labDir = resolve(campaignDir, "lab");
              mkdirSync(labDir, { recursive: true });
              writeFileSync(
                resolve(labDir, "approval.json"),
                JSON.stringify({
                  approved: true,
                  timestamp: new Date().toISOString(),
                  campaignDir: campaign.campaignDir,
                }, null, 2),
              );
            } catch { /* silent */ }
            setShowLabApproval(false);
            setMessages((prev) => [
              ...prev,
              { type: "assistant", text: "Lab submission APPROVED. Approval recorded." },
            ]);
          }}
          onCancel={() => {
            setShowLabApproval(false);
            setMessages((prev) => [
              ...prev,
              { type: "assistant", text: "Lab submission cancelled." },
            ]);
          }}
        />
      )}

      {/* Cost summary panel */}
      {showCosts && (
        <Box flexDirection="column">
          <CostSummary
            costs={
              Array.isArray((campaign.state as Record<string, unknown> | null)?.costs)
                ? ((campaign.state as Record<string, unknown>).costs as { source: string; amount: number }[])
                : []
            }
            total={(campaign.state?.totalCost as number) ?? 0}
          />
          <Text dimColor>{"  Press any key to dismiss"}</Text>
        </Box>
      )}

      {/* Agent team status panel */}
      {showTeam && (
        <Box flexDirection="column">
          <AgentTeamStatus
            agents={
              Array.isArray((campaign.state as Record<string, unknown> | null)?.agents)
                ? ((campaign.state as Record<string, unknown>).agents as { name: string; role: string; status: "idle" | "running" | "complete" | "error"; elapsed?: number }[])
                : []
            }
            campaignPhase={campaign.phase}
            totalCostUsd={(campaign.state?.totalCost as number) ?? 0}
          />
          <Text dimColor>{"  Press any key to dismiss"}</Text>
        </Box>
      )}

      {/* Slash command autocomplete */}
      {completions.length > 0 && (
        <Box flexDirection="column" marginLeft={2}>
          {completions.map((cmd, i) => (
            <Box key={i}>
              <Text color="#4CAF50">{cmd.name}</Text>
              <Text dimColor>{" " + cmd.description}</Text>
            </Box>
          ))}
        </Box>
      )}

      {/* Loading indicator */}
      {loading && !activeTool && (
        <Spinner label="Thinking" />
      )}

      {/* Status line */}
      <Box>
        <Text dimColor>
          {"  "}
          {mode === "vhh" ? "VHH" : mode === "scfv" ? "scFv" : "De Novo"} mode
          {activeRun ? ` | Run: ${activeRun.runId.substring(0, 8)}...` : ""}
          {loading ? " | Esc to interrupt | Ctrl+C to cancel" : " | Ctrl+C+C to exit"}
        </Text>
      </Box>

      {/* Input prompt */}
      <Box>
        <Text>
          {theme.primary("\u25C6 ")}
          {theme.primaryBold(modeConfig.displayName)}
          {theme.primary(" > ")}
        </Text>
        <TextInput
          value={currentInput}
          onChange={setCurrentInput}
          onSubmit={handleSubmit}
        />
      </Box>
    </Box>
  );
}
