import React from "react";
import { Text } from "ink";

interface MarkdownTextProps {
  children: string;
}

export function MarkdownText({ children }: MarkdownTextProps) {
  // Simple markdown→ANSI conversion for terminal
  const rendered = React.useMemo(() => {
    let text = children;

    // Bold: **text** or __text__
    text = text.replace(/\*\*(.*?)\*\*/g, "\x1b[1m$1\x1b[22m");
    text = text.replace(/__(.*?)__/g, "\x1b[1m$1\x1b[22m");

    // Italic: *text* or _text_
    text = text.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, "\x1b[3m$1\x1b[23m");

    // Inline code: `text`
    text = text.replace(/`([^`]+)`/g, "\x1b[38;2;76;175;80m$1\x1b[0m");

    // Headers: # text
    text = text.replace(/^### (.+)$/gm, "\x1b[1;37m  $1\x1b[0m");
    text = text.replace(/^## (.+)$/gm, "\x1b[1;37m $1\x1b[0m");
    text = text.replace(/^# (.+)$/gm, "\x1b[1;37m$1\x1b[0m");

    // Code blocks: ```...``` (just color them green)
    text = text.replace(/```[\s\S]*?```/g, (match) => {
      const code = match.replace(/```\w*\n?/g, "").replace(/```/g, "");
      return "\x1b[38;2;102;187;106m" + code.trimEnd() + "\x1b[0m";
    });

    // Detect pipe tables and render as clean space-aligned columns
    text = text.replace(
      /(?:^|\n)((?:\|[^\n]+\|\n?)+)/g,
      (match) => {
        const rows = match.trim().split("\n").filter(r => r.trim());

        // Parse cells from each row
        const parsed = rows.map(row =>
          row.split("|").slice(1, -1).map(cell => cell.trim())
        );

        // Identify separator rows (|---|---|)
        const isSeparator = (row: string) => /^\|[\s\-:|]+\|$/.test(row.trim());

        // Get data rows (non-separator)
        const dataRows = rows.filter(r => !isSeparator(r));
        const dataParsed = dataRows.map(row =>
          row.split("|").slice(1, -1).map(cell => cell.trim())
        );

        if (dataParsed.length === 0) return match;

        // Compute max column widths (minimum 4 padding)
        const numCols = dataParsed[0]?.length ?? 0;
        const colWidths = Array.from({ length: numCols }, (_, ci) =>
          Math.max(...dataParsed.map(r => (r[ci] ?? "").length), 4) + 4
        );

        // Build output lines
        const lines: string[] = [];
        let isFirstDataRow = true;

        for (let ri = 0; ri < rows.length; ri++) {
          if (isSeparator(rows[ri])) {
            // Render as horizontal line
            const totalWidth = colWidths.reduce((a, b) => a + b, 0);
            lines.push("  " + "─".repeat(totalWidth));
            continue;
          }

          const cells = rows[ri].split("|").slice(1, -1).map(c => c.trim());
          const paddedCells = cells.map((cell, ci) => cell.padEnd(colWidths[ci] ?? cell.length + 4));
          const line = "  " + paddedCells.join("");

          if (isFirstDataRow) {
            // Header row — bold
            lines.push("\x1b[1m" + line + "\x1b[22m");
            isFirstDataRow = false;
          } else {
            lines.push(line);
          }
        }

        return "\n" + lines.join("\n") + "\n";
      }
    );

    // List items: - text or * text
    text = text.replace(/^[\s]*[-*] (.+)$/gm, "  \x1b[38;2;76;175;80m●\x1b[0m $1");

    // Numbered list items
    text = text.replace(/^[\s]*(\d+)\. (.+)$/gm, "  \x1b[38;2;76;175;80m$1.\x1b[0m $2");

    return text;
  }, [children]);

  return <Text>{rendered}</Text>;
}
