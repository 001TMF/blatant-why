import React from "react";
import { Box, Text } from "ink";
import { theme } from "../lib/theme.js";

export interface StreamingTextProps {
  text: string;
}

/**
 * Shows partial streaming text with a dim vertical bar prefix.
 * Updates on each token delta from the SDK stream.
 */
export function StreamingText({ text }: StreamingTextProps) {
  if (!text) return null;

  const lines = text.split("\n");
  return (
    <Box flexDirection="column">
      {lines.map((line, i) => (
        <Text key={i}>
          <Text color={theme.hex.dim}>{"\u2502"} </Text>
          <Text color={theme.hex.body}>{line}</Text>
        </Text>
      ))}
    </Box>
  );
}
