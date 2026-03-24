import React, { useState, useEffect } from "react";
import { Box, Text } from "ink";
import { theme, ICONS } from "../lib/theme.js";
import {
  pollRunStatus,
  formatElapsed,
} from "../lib/watchRun.js";
import type { RunManifest, StageInfo } from "../lib/watchRun.js";

export interface PipelineWatchProps {
  manifest: RunManifest;
  pollIntervalMs?: number;
}

/**
 * Live pipeline progress with stages.
 * Polls the run directory and re-renders stage indicators.
 */
export function PipelineWatch({
  manifest: initialManifest,
  pollIntervalMs = 3000,
}: PipelineWatchProps) {
  const [manifest, setManifest] = useState(initialManifest);

  useEffect(() => {
    const timer = setInterval(() => {
      const updated = pollRunStatus(manifest);
      setManifest(updated);
    }, pollIntervalMs);
    return () => clearInterval(timer);
  }, [manifest, pollIntervalMs]);

  const allComplete = manifest.stages.every((s) => s.status === "complete");

  return (
    <Box flexDirection="column" marginBottom={1}>
      <Box marginBottom={1}>
        <Text color={theme.hex.primary} bold>
          Pipeline: {manifest.runId.substring(0, 8)}
        </Text>
        <Text color={theme.hex.dim}>
          {" "}({manifest.tool} via {manifest.provider})
        </Text>
      </Box>

      {manifest.stages.map((stage) => (
        <StageRow key={stage.id} stage={stage} />
      ))}

      <Box marginTop={1}>
        <Text color={theme.hex.dim}>
          {manifest.designsGenerated}/{manifest.totalDesigns} designs
          {" "}{ICONS.separator}{" "}
          {formatElapsed(manifest.elapsedMs)} elapsed
          {manifest.estimatedRemainingMs != null && !allComplete ? (
            ` ${ICONS.separator} ~${formatElapsed(manifest.estimatedRemainingMs)} remaining`
          ) : null}
        </Text>
      </Box>
    </Box>
  );
}

function StageRow({ stage }: { stage: StageInfo }) {
  const icon = stageIcon(stage.status);
  const iconColor = stageColor(stage.status);
  const progressStr =
    stage.progress != null && stage.status === "running"
      ? ` (${Math.round(stage.progress * 100)}%)`
      : "";
  const msgStr = stage.message ? ` — ${stage.message}` : "";

  return (
    <Box>
      <Text>
        <Text color={iconColor}>  {icon} </Text>
        <Text
          color={
            stage.status === "complete"
              ? theme.hex.dim
              : stage.status === "running"
                ? theme.hex.body
                : theme.hex.dim
          }
        >
          {stage.label}
        </Text>
        <Text color={theme.hex.dim}>
          {progressStr}
          {msgStr}
        </Text>
      </Text>
    </Box>
  );
}

function stageIcon(status: StageInfo["status"]): string {
  switch (status) {
    case "complete":
      return ICONS.success;
    case "running":
      return ICONS.running;
    case "failed":
      return ICONS.error;
    case "pending":
    default:
      return ICONS.pending;
  }
}

function stageColor(status: StageInfo["status"]): string {
  switch (status) {
    case "complete":
      return theme.hex.success;
    case "running":
      return theme.hex.primary;
    case "failed":
      return theme.hex.error;
    case "pending":
    default:
      return theme.hex.dim;
  }
}
