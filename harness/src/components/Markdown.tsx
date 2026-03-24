import React from "react";
import { Text } from "ink";
import { renderMarkdown } from "../lib/markdown.js";

export interface MarkdownProps {
  text: string;
  width?: number;
}

/**
 * React wrapper around lib/markdown.ts renderMarkdown().
 * Pre-renders markdown to ANSI and lets Ink handle layout.
 */
export function Markdown({ text, width }: MarkdownProps) {
  const rendered = React.useMemo(() => {
    const w = width ?? (process.stdout.columns || 80);
    return renderMarkdown(text, w);
  }, [text, width]);

  // renderMarkdown returns ANSI-styled text — Ink's Text will pass it through
  return <Text>{rendered}</Text>;
}
