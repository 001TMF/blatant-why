import React, { useEffect, useRef, useCallback } from "react";
import { theme } from "../lib/theme.js";

export interface StatusBarProps {
  campaignName?: string;
  provider?: string;
  model?: string;
}

/**
 * Fixed bottom bar using raw ANSI cursor positioning.
 * Uses process.stdout.write directly — NOT part of Ink render tree.
 * Renders a single line at the bottom of the terminal.
 */
export function StatusBar({ campaignName, provider, model }: StatusBarProps) {
  const prevLine = useRef("");

  const render = useCallback(() => {
    const cols = process.stdout.columns || 80;
    const rows = process.stdout.rows || 24;

    const left = campaignName
      ? ` ${campaignName}`
      : " Proteus";
    const mid = provider ? ` | ${provider}` : "";
    const right = " Ctrl+C quit | /help ";
    const modelTag = model ? ` | ${model}` : "";

    const content = left + mid + modelTag;
    const padLen = Math.max(0, cols - stripAnsi(content).length - stripAnsi(right).length);
    const line = content + " ".repeat(padLen) + right;

    // Only re-draw if changed
    if (line === prevLine.current) return;
    prevLine.current = line;

    // Save cursor, move to bottom row, write bar, restore cursor
    const bgColor = "\x1b[48;2;26;26;46m"; // theme.hex.bg
    const fgColor = "\x1b[38;2;176;176;176m"; // theme.hex.body
    const reset = "\x1b[0m";

    const seq =
      "\x1b7" + // save cursor
      `\x1b[${rows};1H` + // move to last row
      bgColor +
      fgColor +
      line.substring(0, cols) +
      reset +
      "\x1b8"; // restore cursor

    process.stdout.write(seq);
  }, [campaignName, provider, model]);

  useEffect(() => {
    render();
    const onResize = () => render();
    process.stdout.on("resize", onResize);
    return () => {
      process.stdout.removeListener("resize", onResize);
      // Clear the status bar on unmount
      const rows = process.stdout.rows || 24;
      const cols = process.stdout.columns || 80;
      process.stdout.write(
        `\x1b[${rows};1H\x1b[2K`,
      );
    };
  }, [render]);

  // Re-render periodically to keep it pinned
  useEffect(() => {
    const timer = setInterval(() => render(), 2000);
    return () => clearInterval(timer);
  }, [render]);

  // This component has no Ink output — it writes directly to stdout
  return null;
}

function stripAnsi(str: string): string {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*m/g, "");
}
