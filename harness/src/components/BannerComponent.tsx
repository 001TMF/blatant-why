import React from "react";
import { Box, Text } from "ink";
import { theme } from "../theme.js";

const TITLE_LINES = [
  "██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗",
  "██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝",
  "██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗",
  "██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║",
  "██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║",
  "╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝",
];

interface BannerProps {
  forename: string;
  termWidth: number;
}

/**
 * Clean text banner — no mascot, no mode display.
 * Mode is context-aware (determined by user intent, not a toggle).
 */
export function BannerComponent({ forename, termWidth }: BannerProps) {
  if (termWidth < 65) {
    return (
      <Box flexDirection="column">
        <Text color={theme.hex.primary} bold>PROTEUS</Text>
        <Text dimColor>Biologics Design Agent</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <Box flexDirection="column">
        {TITLE_LINES.map((line, i) => (
          <Text key={i} color={theme.hex.primary}>{line}</Text>
        ))}
      </Box>
      <Text dimColor>  AI-Powered Biologics Design Campaign Agent</Text>
      <Text>
        <Text dimColor>  Welcome back, </Text>
        <Text color={theme.hex.accent}>{forename}</Text>
      </Text>
    </Box>
  );
}
