import React, { useState, useEffect } from "react";
import { Box, Text } from "ink";
import { theme, ICONS } from "../lib/theme.js";

export interface SubAgentBadgeProps {
  agentName: string;
  task: string;
  startedAt: number;
}

/**
 * Shows when a sub-agent is active.
 * Displays: triangle + agent name + task description + elapsed time
 */
export function SubAgentBadge({
  agentName,
  task,
  startedAt,
}: SubAgentBadgeProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startedAt]);

  return (
    <Box marginBottom={1}>
      <Text>
        <Text color={theme.hex.muted}>{ICONS.bullet} </Text>
        <Text color={theme.hex.accent} bold>
          {agentName}
        </Text>
        <Text color={theme.hex.body}> {"\u2014"} {task}</Text>
        <Text color={theme.hex.dim}> ({elapsed}s)</Text>
      </Text>
    </Box>
  );
}
