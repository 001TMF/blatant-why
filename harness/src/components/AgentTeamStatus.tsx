import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

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
  if (ms == null) return "\u2014";
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (min > 0) return `${min}m ${sec.toString().padStart(2, "0")}s`;
  return `${sec}s`;
}

function statusIcon(status: AgentStatus["status"]): { symbol: string; color: string } {
  switch (status) {
    case "complete":
      return { symbol: "\u2714", color: theme.hex.success };
    case "running":
      return { symbol: "\u25CF", color: theme.hex.primary };
    case "error":
      return { symbol: "\u2716", color: theme.hex.error };
    case "idle":
    default:
      return { symbol: "\u25CB", color: "#78909C" };
  }
}

export function AgentTeamStatus({ agents, campaignPhase, totalCostUsd }: AgentTeamStatusProps) {
  return (
    <Box flexDirection="column">
      <Text>
        <Text color={theme.hex.accent} bold>Campaign Phase: </Text>
        <Text color={theme.hex.primary} bold>{campaignPhase.toUpperCase()}</Text>
      </Text>
      <Text>{""}</Text>

      {/* Header row */}
      <Text>
        <Text dimColor>{"  "}</Text>
        <Text color={theme.hex.body} bold>{"Agent".padEnd(16)}</Text>
        <Text color={theme.hex.body} bold>{"Status".padEnd(14)}</Text>
        <Text color={theme.hex.body} bold>{"Elapsed"}</Text>
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
        <Text color={theme.hex.accent}>${totalCostUsd.toFixed(2)}</Text>
      </Text>
    </Box>
  );
}
