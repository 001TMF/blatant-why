import React from "react";
import { Box, Text } from "ink";
import { theme, ICONS } from "../lib/theme.js";
import { humanizeToolName, shouldShowTool } from "../lib/toolNames.js";

export interface ToolEntry {
  toolUseId: string;
  toolName: string;
  startedAt: number;
  completedAt?: number;
}

export interface ToolActivityProps {
  tools: ToolEntry[];
}

/**
 * Persistent stack of recent tool calls with icon + name + elapsed time.
 * Shows the last 5 visible (non-infrastructure) tools.
 */
export function ToolActivity({ tools }: ToolActivityProps) {
  const visible = tools.filter((t) => shouldShowTool(t.toolName));
  const recent = visible.slice(-5);

  if (recent.length === 0) return null;

  return (
    <Box flexDirection="column" marginBottom={1}>
      {recent.map((tool) => {
        const done = tool.completedAt != null;
        const now = Date.now();
        const elapsed = done
          ? tool.completedAt! - tool.startedAt
          : now - tool.startedAt;
        const elapsedStr = (elapsed / 1000).toFixed(1) + "s";
        const icon = done ? ICONS.success : ICONS.running;
        const iconColor = done ? theme.hex.success : theme.hex.primary;
        const label = humanizeToolName(tool.toolName);

        return (
          <Box key={tool.toolUseId}>
            <Text>
              <Text color={iconColor}>  {icon} </Text>
              <Text color={theme.hex.body}>
                {label.padEnd(36)}
              </Text>
              <Text color={theme.hex.dim}>
                {done ? elapsedStr : "..."}
              </Text>
            </Text>
          </Box>
        );
      })}
    </Box>
  );
}
