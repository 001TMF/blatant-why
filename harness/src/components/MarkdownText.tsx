import React from "react";
import { Text } from "ink";

// eslint-disable-next-line no-control-regex
const ANSI_RE = /\u001b\[[0-9;]*m/g;

/** Visible length of a string, ignoring ANSI escape sequences. */
function visLen(s: string): number {
  return s.replace(ANSI_RE, "").length;
}

/**
 * Wrap a single line at `maxWidth` visible characters, preserving ANSI codes.
 * Returns an array of wrapped lines.
 */
function wrapLine(line: string, maxWidth: number): string[] {
  if (maxWidth <= 0 || visLen(line) <= maxWidth) return [line];

  const result: string[] = [];
  let current = "";
  let currentVis = 0;

  // Walk through the string, tracking visible vs. invisible characters
  let i = 0;
  while (i < line.length) {
    // Check for ANSI escape sequence
    if (line[i] === "\x1b" && line[i + 1] === "[") {
      const end = line.indexOf("m", i);
      if (end !== -1) {
        current += line.slice(i, end + 1);
        i = end + 1;
        continue;
      }
    }

    // Regular visible character
    if (currentVis >= maxWidth) {
      result.push(current);
      current = "";
      currentVis = 0;
    }

    current += line[i];
    currentVis++;
    i++;
  }

  if (current) {
    result.push(current);
  }

  return result;
}

/** Apply basic syntax highlighting to a code block based on language. */
function highlightCode(code: string, lang: string): string {
  const supported = ["yaml", "json", "python", "py", "bash", "sh"];
  if (!supported.includes(lang)) {
    // Default: just green
    return "\x1b[38;2;102;187;106m" + code + "\x1b[0m";
  }

  const lines = code.split("\n");
  const highlighted = lines.map((line) => {
    let result = line;

    // Strings in accent color (#66BB6A)
    result = result.replace(
      /(["'])(?:(?=(\\?))\2.)*?\1/g,
      "\x1b[38;2;102;187;106m$&\x1b[38;2;120;144;156m",
    );

    // Numbers in cyan (#80DEEA)
    result = result.replace(
      /(?<![a-zA-Z_])(\d+\.?\d*(?:e[+-]?\d+)?)\b/g,
      "\x1b[38;2;128;222;234m$1\x1b[38;2;120;144;156m",
    );

    // Language-specific keywords
    if (lang === "python" || lang === "py") {
      result = result.replace(
        /\b(def|class|import|from|return|if|else|elif|for|while|with|as|in|not|and|or|True|False|None|try|except|finally|raise|yield|async|await)\b/g,
        "\x1b[38;2;76;175;80m$1\x1b[38;2;120;144;156m",
      );
    } else if (lang === "bash" || lang === "sh") {
      result = result.replace(
        /\b(if|then|else|fi|for|do|done|while|case|esac|function|export|source|echo|cd|ls|grep|sed|awk)\b/g,
        "\x1b[38;2;76;175;80m$1\x1b[38;2;120;144;156m",
      );
    } else if (lang === "yaml") {
      // YAML keys (word followed by colon)
      result = result.replace(
        /^(\s*)([\w.-]+)(:)/gm,
        "$1\x1b[38;2;76;175;80m$2\x1b[38;2;120;144;156m$3",
      );
    } else if (lang === "json") {
      // JSON keys
      result = result.replace(
        /"([^"]+)"\s*:/g,
        "\x1b[38;2;76;175;80m\"$1\"\x1b[38;2;120;144;156m:",
      );
    }

    // Comments in dim
    if (lang === "python" || lang === "py" || lang === "yaml" || lang === "bash" || lang === "sh") {
      result = result.replace(
        /(#.*)$/gm,
        "\x1b[2m$1\x1b[22m",
      );
    }

    return result;
  });

  return "\x1b[38;2;120;144;156m" + highlighted.join("\n") + "\x1b[0m";
}

interface MarkdownTextProps {
  children: string;
  width?: number;
}

export function MarkdownText({ children, width }: MarkdownTextProps) {
  // Simple markdown -> ANSI conversion for terminal
  const rendered = React.useMemo(() => {
    let text = children;

    // Bold: **text** or __text__
    text = text.replace(/\*\*(.*?)\*\*/g, "\x1b[1m$1\x1b[22m");
    text = text.replace(/__(.*?)__/g, "\x1b[1m$1\x1b[22m");

    // Italic: *text* or _text_
    text = text.replace(/(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)/g, "\x1b[3m$1\x1b[23m");

    // Inline code: `text`
    text = text.replace(/`([^`]+)`/g, "\x1b[38;2;128;203;196m$1\x1b[0m");

    // Headers: # text
    text = text.replace(/^### (.+)$/gm, "\x1b[1;37m  $1\x1b[0m");
    text = text.replace(/^## (.+)$/gm, "\x1b[1;37m $1\x1b[0m");
    text = text.replace(/^# (.+)$/gm, "\x1b[1;37m$1\x1b[0m");

    // Code blocks: ```lang\n...\n``` — with language-aware highlighting
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_match, lang: string, code: string) => {
      const trimmed = code.trimEnd();
      return highlightCode(trimmed, lang.toLowerCase());
    });

    // Detect pipe tables and render as clean space-aligned columns
    text = text.replace(
      /(?:^|\n)((?:\|[^\n]+\|\n?)+)/g,
      (match) => {
        const rows = match.trim().split("\n").filter(r => r.trim());

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
            lines.push("  " + "\u2500".repeat(totalWidth));
            continue;
          }

          const cells = rows[ri].split("|").slice(1, -1).map(c => c.trim());
          const paddedCells = cells.map((cell, ci) => cell.padEnd(colWidths[ci] ?? cell.length + 4));
          const line = "  " + paddedCells.join("");

          if (isFirstDataRow) {
            // Header row — bold accent
            lines.push("\x1b[1;38;2;102;187;106m" + line + "\x1b[0m");
            isFirstDataRow = false;
          } else {
            lines.push(line);
          }
        }

        return "\n" + lines.join("\n") + "\n";
      }
    );

    // List items: - text or * text
    text = text.replace(/^[\s]*[-*] (.+)$/gm, "  \x1b[38;2;76;175;80m\u25CF\x1b[0m $1");

    // Numbered list items
    text = text.replace(/^[\s]*(\d+)\. (.+)$/gm, "  \x1b[38;2;76;175;80m$1.\x1b[0m $2");

    // Width-aware wrapping
    if (width && width > 0) {
      const lines = text.split("\n");
      const wrapped = lines.flatMap((line) => wrapLine(line, width));
      text = wrapped.join("\n");
    }

    return text;
  }, [children, width]);

  return <Text>{rendered}</Text>;
}
