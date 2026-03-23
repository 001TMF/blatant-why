import { useState, useCallback } from "react";
import { useInput } from "ink";

export function useInputHistory() {
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [currentInput, setCurrentInput] = useState("");
  const [savedInput, setSavedInput] = useState("");

  useInput((_, key) => {
    if (key.upArrow && history.length > 0) {
      const newIndex = historyIndex < history.length - 1 ? historyIndex + 1 : historyIndex;
      if (historyIndex === -1) {
        setSavedInput(currentInput);
      }
      setHistoryIndex(newIndex);
      setCurrentInput(history[history.length - 1 - newIndex]);
    } else if (key.downArrow) {
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setCurrentInput(history[history.length - 1 - newIndex]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCurrentInput(savedInput);
      }
    }
  });

  const addToHistory = useCallback((value: string) => {
    if (value.trim()) {
      setHistory((prev) => [...prev, value.trim()]);
    }
    setHistoryIndex(-1);
    setSavedInput("");
  }, []);

  return {
    currentInput,
    setCurrentInput,
    addToHistory,
  };
}
