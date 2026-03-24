/**
 * useTerminal — terminal size polling.
 * Returns { width, height } and updates on resize.
 */

import { useState, useEffect } from "react";

export interface TerminalSize {
  width: number;
  height: number;
}

export function useTerminal(): TerminalSize {
  const [size, setSize] = useState<TerminalSize>({
    width: process.stdout.columns || 80,
    height: process.stdout.rows || 24,
  });

  useEffect(() => {
    const onResize = () => {
      setSize({
        width: process.stdout.columns || 80,
        height: process.stdout.rows || 24,
      });
    };

    process.stdout.on("resize", onResize);
    return () => {
      process.stdout.removeListener("resize", onResize);
    };
  }, []);

  return size;
}
