import React from "react";
import { Box, Text } from "ink";

interface CostEntry {
  source: string;
  amount: number;
}

interface CostSummaryProps {
  costs: CostEntry[];
  total: number;
}

function formatDollars(amount: number): string {
  return "$" + amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function CostSummary({ costs, total }: CostSummaryProps) {
  const maxSourceLen = Math.max(20, ...costs.map((c) => c.source.length));
  const dividerLen = maxSourceLen + 14;

  return (
    <Box flexDirection="column">
      <Text color="#66BB6A" bold>{"  Cost Breakdown"}</Text>
      <Text>{""}</Text>

      {costs.map((entry, i) => (
        <Box key={i}>
          <Text>{"  "}</Text>
          <Text>{entry.source.padEnd(maxSourceLen)}</Text>
          <Text color="#A0A0A0">{formatDollars(entry.amount).padStart(12)}</Text>
        </Box>
      ))}

      <Text dimColor>{"  " + "─".repeat(dividerLen)}</Text>

      <Box>
        <Text>{"  "}</Text>
        <Text bold>{"Total".padEnd(maxSourceLen)}</Text>
        <Text color="#66BB6A" bold>{formatDollars(total).padStart(12)}</Text>
      </Box>
    </Box>
  );
}
