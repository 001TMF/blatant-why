import React, { useState, useEffect } from "react";
import { Box, Text } from "ink";
import { pollRunStatus, getStageNames, getToolNames, formatElapsed, RunManifest, RunStatus } from "../watchRun.js";
import { theme } from "../theme.js";

interface PipelineWatchProps {
  manifest: RunManifest;
  onComplete: () => void;
}

export function PipelineWatch({ manifest, onComplete }: PipelineWatchProps) {
  const [status, setStatus] = useState<RunStatus>({
    stage: 1,
    stageName: "Design",
    stagesTotal: 5,
    designsComplete: 0,
    designsTotal: manifest.total,
    elapsed: 0,
    complete: false,
    error: false,
  });

  useEffect(() => {
    // Poll immediately
    const update = () => {
      const newStatus = pollRunStatus(manifest);
      setStatus(newStatus);
      if (newStatus.complete) {
        onComplete();
      }
    };
    update();

    // Then poll every 2 seconds
    const timer = setInterval(update, 2000);
    return () => clearInterval(timer);
  }, [manifest, onComplete]);

  const stageNames = getStageNames(manifest.tool);
  const toolNames = getToolNames(manifest.tool);
  const truncId = manifest.runId.substring(0, 15) + "...";

  return (
    <Box flexDirection="column">
      <Text color={theme.hex.accent} bold>Watching run {truncId}</Text>
      <Text dimColor>  Press Ctrl+C to stop</Text>
      <Text>{""}</Text>
      <Text>Design Run: <Text color={theme.hex.tealBright}>{truncId}</Text></Text>
      <Text>{""}</Text>
      {stageNames.map((name, i) => {
        const stageNum = i + 1;
        let symbol: string;
        let color: string;

        if (stageNum < status.stage || status.complete) {
          symbol = "\u2713";
          color = theme.hex.success;
        } else if (stageNum === status.stage && !status.complete) {
          symbol = "\u25CF";
          color = theme.hex.warning;
        } else {
          symbol = "\u25CB";
          color = "#78909C";
        }

        return (
          <Box key={i}>
            <Text color={color}>{`  ${symbol} `}</Text>
            <Text color={color} bold={stageNum === status.stage && !status.complete}>
              {name.padEnd(28)}
            </Text>
            <Text dimColor>{toolNames[i] ?? ""}</Text>
          </Box>
        );
      })}
      <Text>{""}</Text>
      <Text>
        <Text color={theme.hex.accent}>Progress: </Text>
        <Text>{status.designsComplete}/{status.designsTotal} designs</Text>
        <Text dimColor> | Elapsed: {formatElapsed(status.elapsed)}</Text>
      </Text>
      <Text>{""}</Text>
      <Text>
        <Text>Status: </Text>
        {status.complete ? (
          <Text color={theme.hex.success}>{"\u2713"} complete</Text>
        ) : status.error ? (
          <Text color={theme.hex.error}>{"\u2717"} error</Text>
        ) : (
          <Text color={theme.hex.teal}>{"\u25CF"} running</Text>
        )}
      </Text>
      {status.complete && (
        <>
          <Text>{""}</Text>
          <Text color={theme.hex.success}>{"\u2713"} Design run completed!</Text>
          <Text>Use /results or ask me to show the designs.</Text>
        </>
      )}
    </Box>
  );
}
