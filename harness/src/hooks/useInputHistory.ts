/**
 * useInputHistory — up/down arrow command history.
 * Stores entries in memory (not persisted to disk).
 */

import { useState, useCallback } from "react";
import { useInput } from "ink";

export interface UseInputHistoryOptions {
  maxEntries?: number;
}

export interface UseInputHistoryReturn {
  /** Add an entry to the history */
  push: (entry: string) => void;
  /** Navigate up (older) — returns the history entry or undefined */
  navigateUp: () => string | undefined;
  /** Navigate down (newer) — returns the history entry or undefined */
  navigateDown: () => string | undefined;
  /** Current position in history (-1 = not browsing) */
  position: number;
  /** Reset position to bottom (called when user types) */
  resetPosition: () => void;
}

export function useInputHistory(
  opts: UseInputHistoryOptions = {},
): UseInputHistoryReturn {
  const maxEntries = opts.maxEntries ?? 100;
  const [history, setHistory] = useState<string[]>([]);
  const [position, setPosition] = useState(-1);

  const push = useCallback(
    (entry: string) => {
      if (!entry.trim()) return;
      setHistory((prev) => {
        const next = [...prev, entry];
        if (next.length > maxEntries) next.shift();
        return next;
      });
      setPosition(-1);
    },
    [maxEntries],
  );

  const navigateUp = useCallback((): string | undefined => {
    if (history.length === 0) return undefined;
    const newPos = position === -1 ? history.length - 1 : Math.max(0, position - 1);
    setPosition(newPos);
    return history[newPos];
  }, [history, position]);

  const navigateDown = useCallback((): string | undefined => {
    if (position === -1) return undefined;
    const newPos = position + 1;
    if (newPos >= history.length) {
      setPosition(-1);
      return "";
    }
    setPosition(newPos);
    return history[newPos];
  }, [history, position]);

  const resetPosition = useCallback(() => {
    setPosition(-1);
  }, []);

  return { push, navigateUp, navigateDown, position, resetPosition };
}
