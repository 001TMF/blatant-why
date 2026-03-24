import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { theme } from "../theme.js";

interface LabApprovalProps {
  campaignName: string;
  numCandidates: number;
  estimatedCost: number;
  onConfirm: () => void;
  onCancel: () => void;
}

export function LabApproval({
  campaignName,
  numCandidates,
  estimatedCost,
  onConfirm,
  onCancel,
}: LabApprovalProps) {
  const [inputBuffer, setInputBuffer] = useState("");

  useInput((input, key) => {
    if (key.return) {
      const trimmed = inputBuffer.trim();
      if (trimmed === "CONFIRM") {
        onConfirm();
      } else {
        onCancel();
      }
      return;
    }

    if (key.backspace || key.delete) {
      setInputBuffer((prev) => prev.slice(0, -1));
      return;
    }

    if (key.escape) {
      onCancel();
      return;
    }

    // Only accept printable characters
    if (input && !key.ctrl && !key.meta) {
      setInputBuffer((prev) => prev + input);
    }
  });

  const costFormatted = "$" + estimatedCost.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });

  return (
    <Box flexDirection="column">
      <Text>{""}</Text>
      <Text color={theme.hex.warning} bold>{"  \u26A0 LAB SUBMISSION APPROVAL"}</Text>
      <Text>{""}</Text>
      <Text color={theme.hex.error} bold>
        {"  WARNING: This will submit designs to Adaptyv Bio"}
      </Text>
      <Text color={theme.hex.error} bold>
        {"  for PHYSICAL LAB TESTING."}
      </Text>
      <Text>{""}</Text>
      <Text>
        <Text dimColor>{"  Campaign:    "}</Text>
        <Text color={theme.hex.tealBright}>{campaignName}</Text>
      </Text>
      <Text>
        <Text dimColor>{"  Candidates:  "}</Text>
        <Text>{numCandidates} designs</Text>
      </Text>
      <Text>
        <Text dimColor>{"  Est. Cost:   "}</Text>
        <Text color={theme.hex.warning}>{costFormatted}</Text>
      </Text>
      <Text>
        <Text dimColor>{"  Turnaround:  "}</Text>
        <Text>2-4 weeks</Text>
      </Text>
      <Text>{""}</Text>
      <Text dimColor>{"  Type CONFIRM to proceed, or CANCEL to abort:"}</Text>
      <Text>
        <Text color={theme.hex.primary}>{"  > "}</Text>
        <Text>{inputBuffer}</Text>
        <Text color={theme.hex.primary}>{"\u2588"}</Text>
      </Text>
    </Box>
  );
}
