/**
 * app.tsx — thin orchestrator (<200 lines).
 *
 * Declares state via hooks, handles local slash commands,
 * and wires components together in JSX.
 */

import React, { useState, useCallback } from "react";
import { Box, useInput } from "ink";

// Hooks
import { useAgent } from "./hooks/useAgent.js";
import { useTerminal } from "./hooks/useTerminal.js";
import { useCampaign } from "./hooks/useCampaign.js";
import { useInputHistory } from "./hooks/useInputHistory.js";
import { useStatusBar } from "./hooks/useStatusBar.js";

// Components
import { Banner } from "./components/Banner.js";
import { MessageList } from "./components/MessageList.js";
import { StreamingText } from "./components/StreamingText.js";
import { ToolActivity } from "./components/ToolActivity.js";
import { Spinner } from "./components/Spinner.js";
import { InputPrompt } from "./components/InputPrompt.js";
import { StatusBar } from "./components/StatusBar.js";
import { LabApproval } from "./components/LabApproval.js";

// Lib
import { formatHelp, isLocalCommand } from "./lib/slashCommands.js";
import { humanizeToolName } from "./lib/toolNames.js";
import type { MessageData } from "./components/Message.js";

interface AppProps {
  projectDir: string;
  forename: string;
}

let sysIdCounter = 0;
function sysMsg(text: string): MessageData {
  return {
    id: `sys_${++sysIdCounter}_${Date.now()}`,
    role: "system",
    content: text,
    timestamp: Date.now(),
  };
}

export function App({ projectDir, forename }: AppProps) {
  useTerminal(); // subscribe to resize events
  const campaign = useCampaign({ projectDir });
  const statusBar = useStatusBar({ projectDir });
  const { push: addToHistory, navigateUp, navigateDown } = useInputHistory();

  const [showLabApproval, setShowLabApproval] = useState(false);
  const [currentInput, setCurrentInput] = useState("");
  const [localMessages, setLocalMessages] = useState<MessageData[]>([]);

  const agent = useAgent({ projectDir });

  // Merge agent messages with any locally-injected messages
  const allMessages: MessageData[] = [...localMessages, ...agent.messages];

  const addLocal = useCallback((msg: MessageData) => {
    setLocalMessages((prev) => [...prev, msg]);
  }, []);

  // Handle local slash commands — returns true if handled
  const handleLocalCommand = useCallback(
    (input: string): boolean => {
      const cmd = isLocalCommand(input);
      if (!cmd) return false;

      switch (cmd) {
        case "/help":
          addLocal(sysMsg(formatHelp()));
          break;

        case "/approve-lab":
          setShowLabApproval(true);
          break;

        case "/view": {
          const path = input.replace("/view", "").trim();
          if (!path) {
            addLocal(sysMsg("Usage: /view <pdb_or_cif_file>"));
          } else {
            import("./lib/proteinView.js").then((pv) => {
              if (pv.isProteinViewAvailable()) {
                pv.launchProteinView(path);
                addLocal(sysMsg("Returned from ProteinView."));
              } else {
                addLocal(
                  sysMsg(
                    "ProteinView not installed. Install from: github.com/001TMF/ProteinView",
                  ),
                );
              }
            });
          }
          break;
        }

        case "/export":
          import("./lib/conversationLog.js").then((cl) => {
            const logger = new cl.ConversationLog(projectDir);
            const md = logger.exportMarkdown();
            addLocal(sysMsg(`Exported ${md.length} chars to campaign dir.`));
          });
          break;

        default:
          // Other local commands: forward to agent for tool-based handling
          agent.submit(input);
          return true;
      }
      return true;
    },
    [agent, projectDir, addLocal],
  );

  // Submit handler
  const handleSubmit = useCallback(
    (input: string) => {
      if (!input.trim()) return;
      addToHistory(input);
      setCurrentInput("");

      if (handleLocalCommand(input)) return;
      agent.submit(input);
    },
    [handleLocalCommand, agent, addToHistory],
  );

  // Keyboard handling
  useInput((_ch, key) => {
    if (key.escape) agent.cancel();
    if (key.upArrow) {
      const prev = navigateUp();
      if (prev !== undefined) setCurrentInput(prev);
    }
    if (key.downArrow) {
      const next = navigateDown();
      if (next !== undefined) setCurrentInput(next);
    }
  });

  // Derive spinner label from the active tool
  const spinnerLabel = agent.activeTool
    ? humanizeToolName(agent.activeTool.toolName)
    : undefined;

  // Prepend banner as first static message (renders once, never re-renders)
  const bannerMsg: MessageData = {
    id: "banner",
    role: "banner" as MessageData["role"],
    content: forename,
    timestamp: 0,
  };
  const staticMessages: MessageData[] = [bannerMsg, ...allMessages];

  return (
    <Box flexDirection="column">
      {/* Completed messages (including banner) — scroll naturally via <Static> */}
      <MessageList messages={staticMessages} />

      {/* Dynamic section — re-renders freely */}
      {agent.streamingText && <StreamingText text={agent.streamingText} />}
      {agent.toolLog.length > 0 && <ToolActivity tools={agent.toolLog} />}
      {agent.loading && !agent.streamingText && (
        <Spinner label={spinnerLabel} />
      )}

      {/* Lab approval overlay */}
      {showLabApproval && (
        <LabApproval
          campaignName={campaign?.campaignId ?? "unknown"}
          designCount={campaign?.designCount ?? 0}
          estimatedCost={campaign?.costUsd != null ? `$${campaign.costUsd}` : "TBD"}
          provider={statusBar.provider ?? "None"}
          onConfirm={() => setShowLabApproval(false)}
          onCancel={() => setShowLabApproval(false)}
        />
      )}

      {/* Input */}
      <InputPrompt
        value={currentInput}
        onChange={setCurrentInput}
        onSubmit={handleSubmit}
        focus={!showLabApproval}
      />

      {/* Status bar — raw ANSI, outside Ink tree */}
      <StatusBar
        campaignName={campaign?.name ?? statusBar.campaignName}
        provider={statusBar.provider}
        model={statusBar.model}
      />
    </Box>
  );
}
