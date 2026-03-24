import React from "react";
import { Box, Text } from "ink";

export interface ToolEntry {
  name: string;
  status: "running" | "done" | "error";
  startTime: number;
  endTime?: number;
}

interface Props {
  tools: ToolEntry[];
  maxDisplay?: number;
}

export function ToolActivityPanel({ tools, maxDisplay = 5 }: Props) {
  const recent = tools.slice(-maxDisplay);
  if (recent.length === 0) return null;

  return (
    <Box flexDirection="column" marginLeft={2} marginBottom={1}>
      {recent.map((tool, i) => {
        const elapsed = tool.endTime
          ? ((tool.endTime - tool.startTime) / 1000).toFixed(1)
          : ((Date.now() - tool.startTime) / 1000).toFixed(0);
        const icon = tool.status === "done" ? "✓" : tool.status === "error" ? "✗" : "●";
        const color = tool.status === "done" ? "#4CAF50" : tool.status === "error" ? "#FF5252" : "#80DEEA";

        return (
          <Box key={i}>
            <Text color={color}>{icon}</Text>
            <Text color="#A0A0A0"> {tool.name.padEnd(35)}</Text>
            <Text dimColor>{elapsed}s</Text>
          </Box>
        );
      })}
    </Box>
  );
}
