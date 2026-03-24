import React from "react";
import { Box, Text } from "ink";
import { AnimatedScientist } from "./AnimatedScientist.js";
import { theme } from "../theme.js";

// Same title lines from banner.ts — kept in sync
const TITLE_LINES = [
  "\u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u2588\u2588\u2557   \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557",
  "\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2550\u2588\u2588\u2557\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d\u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2550\u2550\u255d",
  "\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2551   \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557",
  "\u2588\u2588\u2554\u2550\u2550\u2550\u255d \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2551   \u2588\u2588\u2554\u2550\u2550\u255d  \u2588\u2588\u2551   \u2588\u2588\u2551\u255a\u2550\u2550\u2550\u2550\u2588\u2588\u2551",
  "\u2588\u2588\u2551     \u2588\u2588\u2551  \u2588\u2588\u2551\u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d   \u2588\u2588\u2551   \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\u255a\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551",
  "\u255a\u2550\u255d     \u255a\u2550\u255d  \u255a\u2550\u255d \u255a\u2550\u2550\u2550\u2550\u2550\u255d    \u255a\u2550\u255d   \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u2550\u2550\u2550\u2550\u2550\u255d",
];

interface BannerProps {
  mode: string;
  forename: string;
  termWidth: number;
}

/**
 * React component banner with animated scientist character to the left
 * of the PROTEUS ASCII title. Replaces the static string-based banner
 * when rendered inside the Ink component tree.
 */
export function BannerComponent({ mode, forename, termWidth }: BannerProps) {
  // Narrow terminal — compact banner, no scientist
  if (termWidth < 65) {
    return (
      <Box flexDirection="column">
        <Text color={theme.hex.primary} bold>PROTEUS</Text>
        <Text dimColor>
          {"Welcome, "}
          <Text color={theme.hex.accent}>{forename}</Text>
          {" | Mode: "}
          <Text color={theme.hex.accent}>{mode}</Text>
        </Text>
      </Box>
    );
  }

  // The scientist is 7 lines, the title is 6 lines.
  // We pad the title with one empty line at the top so they align vertically.
  return (
    <Box flexDirection="column">
      <Box flexDirection="row">
        {/* Animated scientist to the left */}
        <Box flexDirection="column" justifyContent="center">
          <AnimatedScientist intervalMs={1200} />
        </Box>

        {/* Small gap */}
        <Box width={2} />

        {/* PROTEUS title */}
        <Box flexDirection="column" justifyContent="flex-end">
          {TITLE_LINES.map((line, i) => (
            <Text key={i} color={theme.hex.primary}>{line}</Text>
          ))}
        </Box>
      </Box>

      {/* Subtitle and info lines */}
      <Text dimColor>{"  AI-Powered Biologics Design Campaign Agent"}</Text>
      <Text>
        <Text dimColor>{"  Welcome back, "}</Text>
        <Text color={theme.hex.accent}>{forename}</Text>
        <Text dimColor>{". Ready to engineer proteins."}</Text>
      </Text>
      <Text>
        <Text dimColor>{"  Mode: "}</Text>
        <Text color={theme.hex.accent}>{mode}</Text>
        <Text dimColor>{"  (Shift+Tab to switch)"}</Text>
      </Text>
      <Text>
        <Text dimColor>{"  Type "}</Text>
        <Text color={theme.hex.accent}>/help</Text>
        <Text dimColor>{" for commands, or describe what you want to design."}</Text>
      </Text>
    </Box>
  );
}
