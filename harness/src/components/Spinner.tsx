import React, { useState, useEffect } from "react";
import { Text } from "ink";
import { theme } from "../lib/theme.js";
import { nextThinkingWord } from "../lib/thinkingWords.js";

const BRAILLE = ["\u2807", "\u2838", "\u2834", "\u2826", "\u2816", "\u280B"];

export interface SpinnerProps {
  /** Override the label (default: rotating thinking words) */
  label?: string;
}

/**
 * Braille spinner with rotating thinking words.
 * Cycles through frames at ~100ms and words every ~3s.
 */
export function Spinner({ label }: SpinnerProps) {
  const [frame, setFrame] = useState(0);
  const [word, setWord] = useState(() => label ?? nextThinkingWord());

  useEffect(() => {
    const timer = setInterval(() => {
      setFrame((f) => (f + 1) % BRAILLE.length);
    }, 100);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (label) {
      setWord(label);
      return;
    }
    const timer = setInterval(() => {
      setWord(nextThinkingWord());
    }, 3000);
    return () => clearInterval(timer);
  }, [label]);

  return (
    <Text>
      <Text color={theme.hex.primary}>{BRAILLE[frame]} </Text>
      <Text color={theme.hex.dim}>{word}...</Text>
    </Text>
  );
}
