import React, { useState, useCallback } from "react";
import { Box, Text, useInput } from "ink";
import TextInput from "ink-text-input";
import { renderBanner } from "./banner.js";
import { ProteusMode, cycleMode, getModeConfig } from "./modes.js";
import { theme } from "./theme.js";

interface AppProps {
  queryFn: (input: string) => AsyncGenerator<string>;
  mode: ProteusMode;
  onModeChange: (mode: ProteusMode) => void;
}

export function App({ queryFn, mode, onModeChange }: AppProps) {
  const [input, setInput] = useState("");
  const [output, setOutput] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const modeConfig = getModeConfig(mode);

  useInput((_, key) => {
    if (key.shift && key.tab) {
      onModeChange(cycleMode(mode));
    }
  });

  const handleSubmit = useCallback(async (value: string) => {
    if (!value.trim()) return;
    const trimmed = value.trim();
    setInput("");
    setOutput(prev => [...prev, `> ${trimmed}`]);
    setLoading(true);
    try {
      for await (const chunk of queryFn(trimmed)) {
        setOutput(prev => [...prev, chunk]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setOutput(prev => [...prev, `Error: ${msg}`]);
    } finally {
      setLoading(false);
    }
  }, [queryFn]);

  return (
    <Box flexDirection="column" padding={1}>
      {/* Banner */}
      <Text>{renderBanner(modeConfig.displayName)}</Text>
      <Text>{""}</Text>

      {/* Output area */}
      {output.map((line, i) => (
        <Text key={i}>{line}</Text>
      ))}

      {/* Loading indicator */}
      {loading && <Text color="#66BB6A">Thinking...</Text>}

      {/* Input prompt */}
      <Box>
        <Text>{theme.prompt}</Text>
        <TextInput value={input} onChange={setInput} onSubmit={handleSubmit} />
      </Box>
    </Box>
  );
}
