import React from "react";
import { Box, Text } from "ink";

export interface AgentStatus {
  name: string;
  role: string;
  status: "idle" | "running" | "complete" | "error";
  elapsed?: number; // ms
}

interface AgentTeamStatusProps {
  agents: AgentStatus[];
  campaignPhase: string;
  totalCostUsd: number;
}

function formatElapsed(ms?: number): string {
  if (ms == null) return "—";
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (min > 0) return `${min}m ${sec.toString().padStart(2, "0")}s`;
  return `${sec}s`;
}

function statusIcon(status: AgentStatus["status"]): { symbol: string; color: string } {
  switch (status) {
    case "complete":
      return { symbol: "✓", color: "#4CAF50" };
    case "running":
      return { symbol: "●", color: "#FFC107" };
    case "error":
      return { symbol: "✗", color: "#FF5252" };
    case "idle":
    default:
      return { symbol: "○", color: "#78909C" };
  }
}

export function AgentTeamStatus({ agents, campaignPhase, totalCostUsd }: AgentTeamStatusProps) {
  return (
    <Box flexDirection="column">
      <Text>
        <Text color="#66BB6A" bold>Campaign Phase: </Text>
        <Text color="#80DEEA" bold>{campaignPhase.toUpperCase()}</Text>
      </Text>
      <Text>{""}</Text>

      {/* Header row */}
      <Text>
        <Text dimColor>{"  "}</Text>
        <Text color="#A0A0A0" bold>{"Agent".padEnd(16)}</Text>
        <Text color="#A0A0A0" bold>{"Status".padEnd(14)}</Text>
        <Text color="#A0A0A0" bold>{"Elapsed"}</Text>
      </Text>

      {/* Agent rows */}
      {agents.map((agent, i) => {
        const { symbol, color } = statusIcon(agent.status);
        return (
          <Box key={i}>
            <Text>{"  "}</Text>
            <Text>{agent.name.padEnd(16)}</Text>
            <Text color={color}>{symbol} {agent.status.padEnd(11)}</Text>
            <Text dimColor>{formatElapsed(agent.elapsed)}</Text>
          </Box>
        );
      })}

      <Text>{""}</Text>
      <Text>
        <Text dimColor>{"  Running cost: "}</Text>
        <Text color="#66BB6A">${totalCostUsd.toFixed(2)}</Text>
      </Text>
    </Box>
  );
}
