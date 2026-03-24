import React from "react";
import { Box, Text } from "ink";
import TextInput from "ink-text-input";
import { theme, ICONS } from "../lib/theme.js";

export interface InputPromptProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  focus?: boolean;
}

/**
 * Text input with diamond prompt character in primary color.
 */
export function InputPrompt({
  value,
  onChange,
  onSubmit,
  focus = true,
}: InputPromptProps) {
  return (
    <Box>
      <Text color={theme.hex.primary}>{ICONS.prompt} </Text>
      <TextInput
        value={value}
        onChange={onChange}
        onSubmit={onSubmit}
        focus={focus}
        showCursor
      />
    </Box>
  );
}
