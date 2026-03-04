import React, { useState, useCallback } from "react";
import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import { renderBanner } from "./banner.js";
import { ProteusMode, cycleMode, getModeConfig } from "./modes.js";
import { theme } from "./theme.js";

interface AppProps {
  onSubmit: (input: string) => void;
  output: string[];
  mode: ProteusMode;
  onModeChange: (mode: ProteusMode) => void;
}

export function App({ onSubmit, output, mode, onModeChange }: AppProps) {
  const [input, setInput] = useState("");
  const modeConfig = getModeConfig(mode);

  useInput((_, key) => {
    if (key.shift && key.tab) {
      onModeChange(cycleMode(mode));
    }
  });

  const handleSubmit = useCallback((value: string) => {
    if (value.trim()) {
      onSubmit(value.trim());
      setInput("");
    }
  }, [onSubmit]);

  return (
    <Box flexDirection="column" padding={1}>
      {/* Banner */}
      <Text>{renderBanner(modeConfig.displayName)}</Text>
      <Text>{""}</Text>

      {/* Output area */}
      {output.map((line, i) => (
        <Text key={i}>{line}</Text>
      ))}

      {/* Input prompt */}
      <Box>
        <Text>{theme.prompt}</Text>
        <TextInput value={input} onChange={setInput} onSubmit={handleSubmit} />
      </Box>
    </Box>
  );
}
