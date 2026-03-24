import { lexer, type Token, type Tokens, type TokensList } from "marked";
import chalk from "chalk";
import { theme } from "./theme.js";

/**
 * Render markdown text to ANSI-formatted terminal output.
 * Uses the `marked` lexer to parse into tokens, then walks the tree
 * emitting styled text with chalk.
 */
export function renderMarkdown(text: string, width: number = 80): string {
  const tokens: TokensList = lexer(text);
  return tokens.map((t) => renderToken(t, width)).join("");
}

function renderToken(token: Token, width: number): string {
  switch (token.type) {
    case "heading":
      return renderHeading(token as Tokens.Heading, width);
    case "paragraph":
      return wrapText(renderInlineTokens((token as Tokens.Paragraph).tokens), width) + "\n\n";
    case "code":
      return renderCodeBlock(
        (token as Tokens.Code).text,
        (token as Tokens.Code).lang || "",
        width,
      );
    case "list":
      return renderList(token as Tokens.List, width);
    case "table":
      return renderTable(token as Tokens.Table, width);
    case "blockquote":
      return renderBlockquote(token as Tokens.Blockquote, width);
    case "hr":
      return theme.dim("\u2500".repeat(Math.min(width, 60))) + "\n\n";
    case "space":
      return "\n";
    case "html":
      return ""; // Skip raw HTML
    default:
      if ("tokens" in token && Array.isArray(token.tokens)) {
        return renderInlineTokens(token.tokens);
      }
      if ("text" in token) {
        return renderInline((token as { text: string }).text);
      }
      return "";
  }
}

function renderHeading(token: Tokens.Heading, width: number): string {
  const text = renderInlineTokens(token.tokens);
  const prefix = "#".repeat(token.depth) + " ";
  if (token.depth === 1) {
    const line = "\u2500".repeat(Math.min(width, 60));
    return "\n" + theme.heading(prefix + text) + "\n" + theme.dim(line) + "\n\n";
  }
  if (token.depth === 2) {
    return "\n" + theme.heading(prefix + text) + "\n\n";
  }
  return chalk.hex("#B0B0B0").bold(prefix + text) + "\n\n";
}

function renderBlockquote(token: Tokens.Blockquote, width: number): string {
  const inner = token.tokens.map((t) => renderToken(t, width - 4)).join("");
  const lines = inner.split("\n").filter((l) => l.length > 0 || inner.endsWith("\n"));
  const prefixed = lines.map((l) => theme.dim("  \u2502 ") + l).join("\n");
  return prefixed + "\n";
}

function renderList(token: Tokens.List, width: number): string {
  const items = token.items.map((item, i) => {
    const bullet = token.ordered ? `${(token.start as number) + i}.` : "\u2022";
    const text = renderInlineTokens(item.tokens);
    const prefix = `  ${bullet} `;
    // Wrap continuation lines with proper indent
    const wrapped = wrapText(text, width - prefix.length);
    const lines = wrapped.split("\n");
    return (
      prefix +
      lines[0] +
      (lines.length > 1
        ? "\n" + lines.slice(1).map((l) => " ".repeat(prefix.length) + l).join("\n")
        : "")
    );
  });
  return items.join("\n") + "\n\n";
}

function renderCodeBlock(code: string, lang: string, width: number): string {
  const maxWidth = Math.min(width - 4, 76);
  const border = "\u2500".repeat(maxWidth);
  const highlighted = highlightCode(code, lang);
  const lines = highlighted.split("\n").map((l) => "  " + l);

  return (
    theme.dim("  \u250C" + border) +
    "\n" +
    lines.join("\n") +
    "\n" +
    theme.dim("  \u2514" + border) +
    "\n\n"
  );
}

function highlightCode(code: string, lang: string): string {
  // Language-specific keyword sets
  const keywords: Record<string, string[]> = {
    python: [
      "def", "class", "import", "from", "return", "if", "else", "elif",
      "for", "while", "with", "as", "try", "except", "finally", "raise",
      "yield", "async", "await", "True", "False", "None", "and", "or",
      "not", "in", "is", "lambda", "pass", "break", "continue",
    ],
    typescript: [
      "const", "let", "var", "function", "return", "if", "else", "for",
      "while", "import", "export", "from", "class", "interface", "type",
      "extends", "implements", "new", "this", "async", "await", "try",
      "catch", "finally", "throw", "true", "false", "null", "undefined",
    ],
    javascript: [
      "const", "let", "var", "function", "return", "if", "else", "for",
      "while", "import", "export", "from", "class", "new", "this",
      "async", "await", "try", "catch", "finally", "throw",
      "true", "false", "null", "undefined",
    ],
    yaml: ["true", "false", "null", "yes", "no"],
    bash: [
      "if", "then", "else", "fi", "for", "do", "done", "while", "case",
      "esac", "function", "return", "export", "source", "echo", "cd",
    ],
    json: [],
  };

  // Resolve language aliases
  const langAliases: Record<string, string> = {
    py: "python",
    ts: "typescript",
    js: "javascript",
    sh: "bash",
    shell: "bash",
    yml: "yaml",
  };

  const resolvedLang = langAliases[lang] ?? lang;
  const kws = keywords[resolvedLang] ?? [];
  const kwSet = new Set(kws);

  return code
    .split("\n")
    .map((line) => {
      // Comments
      if (line.trimStart().startsWith("#") || line.trimStart().startsWith("//")) {
        return theme.dim(line);
      }

      let result = line;

      // Strings (single and double quoted)
      result = result.replace(
        /(["'])(?:(?!\1|\\).|\\.)*\1/g,
        (match) => chalk.hex("#E69F00")(match),
      );

      // Numbers
      result = result.replace(
        /\b(\d+\.?\d*(?:e[+-]?\d+)?)\b/g,
        (match) => chalk.hex("#56B4E9")(match),
      );

      // Keywords (only if we have a known language)
      if (kws.length > 0) {
        result = result.replace(
          /\b([a-zA-Z_]+)\b/g,
          (match) => {
            if (kwSet.has(match)) return chalk.hex("#0072B2")(match);
            return match;
          },
        );
      }

      // YAML keys
      if (resolvedLang === "yaml") {
        result = result.replace(
          /^(\s*)([\w.-]+)(:)/gm,
          (_match, indent: string, key: string, colon: string) =>
            indent + chalk.hex("#0072B2")(key) + chalk.dim(colon),
        );
      }

      return result;
    })
    .join("\n");
}

function renderTable(token: Tokens.Table, width: number): string {
  if (token.header.length === 0) return "";

  // Calculate column widths from content
  const colWidths: number[] = token.header.map((cell) => stripAnsi(cell.text).length);

  for (const row of token.rows) {
    for (let i = 0; i < row.length; i++) {
      const cellWidth = stripAnsi(row[i].text).length;
      if (i < colWidths.length) {
        colWidths[i] = Math.max(colWidths[i], cellWidth);
      }
    }
  }

  // Cap total width
  const totalWidth =
    colWidths.reduce((a, b) => a + b, 0) + (colWidths.length - 1) * 3 + 4;
  if (totalWidth > width) {
    const scale = (width - 4 - (colWidths.length - 1) * 3) / (totalWidth - 4 - (colWidths.length - 1) * 3);
    for (let i = 0; i < colWidths.length; i++) {
      colWidths[i] = Math.max(3, Math.floor(colWidths[i] * scale));
    }
  }

  const hBorder = colWidths.map((w) => "\u2500".repeat(w + 2)).join("\u252C");
  const hSep = colWidths.map((w) => "\u2500".repeat(w + 2)).join("\u253C");

  // Header
  const headerCells = token.header.map((cell, i) => {
    const text = renderInline(cell.text);
    return " " + padCell(text, cell.text, colWidths[i], cell.align) + " ";
  });

  const lines: string[] = [];
  lines.push(theme.dim("\u250C" + hBorder + "\u2510"));
  lines.push(
    theme.dim("\u2502") + headerCells.map((c) => theme.bold(c)).join(theme.dim("\u2502")) + theme.dim("\u2502"),
  );
  lines.push(theme.dim("\u251C" + hSep + "\u2524"));

  // Body rows
  for (const row of token.rows) {
    const cells = row.map((cell, i) => {
      const text = renderInline(cell.text);
      const w = i < colWidths.length ? colWidths[i] : 10;
      const align = i < token.header.length ? token.header[i].align : null;
      return " " + padCell(text, cell.text, w, align) + " ";
    });
    lines.push(
      theme.dim("\u2502") + cells.join(theme.dim("\u2502")) + theme.dim("\u2502"),
    );
  }

  lines.push(theme.dim("\u2514" + colWidths.map((w) => "\u2500".repeat(w + 2)).join("\u2534") + "\u2518"));

  return lines.join("\n") + "\n\n";
}

function truncateAnsi(str: string, maxWidth: number): string {
  if (maxWidth <= 0) return "";
  let visible = 0;
  let i = 0;
  while (i < str.length && visible < maxWidth) {
    // Skip ANSI escape sequences
    if (str[i] === "\x1b" && str[i + 1] === "[") {
      const end = str.indexOf("m", i);
      if (end !== -1) {
        i = end + 1;
        continue;
      }
    }
    visible++;
    i++;
  }
  // Collect any trailing ANSI reset sequences
  let tail = "";
  while (i < str.length && str[i] === "\x1b") {
    const end = str.indexOf("m", i);
    if (end !== -1) {
      tail += str.slice(i, end + 1);
      i = end + 1;
    } else break;
  }
  return str.slice(0, i - (visible > maxWidth ? 1 : 0)) + tail;
}

function padCell(
  styledText: string,
  rawText: string,
  width: number,
  align: "center" | "left" | "right" | null,
): string {
  const textLen = stripAnsi(rawText).length;

  if (textLen > width) {
    const truncated = truncateAnsi(styledText, width - 1);
    return truncated + "\u2026"; // ellipsis
  }

  const pad = Math.max(0, width - textLen);

  // Auto-detect numbers for right alignment
  const isNumber = /^\s*-?\d+\.?\d*\s*$/.test(rawText);
  const effectiveAlign = align ?? (isNumber ? "right" : "left");

  switch (effectiveAlign) {
    case "right":
      return " ".repeat(pad) + styledText;
    case "center": {
      const left = Math.floor(pad / 2);
      const right = pad - left;
      return " ".repeat(left) + styledText + " ".repeat(right);
    }
    default:
      return styledText + " ".repeat(pad);
  }
}

/**
 * Render inline tokens from the marked AST.
 * This handles bold, italic, code, links etc. from the token tree.
 */
function renderInlineTokens(tokens: Token[]): string {
  return tokens
    .map((token) => {
      switch (token.type) {
        case "strong":
          return theme.bold(renderInlineTokens((token as Tokens.Strong).tokens));
        case "em":
          return theme.accent(renderInlineTokens((token as Tokens.Em).tokens));
        case "codespan":
          return theme.secondary((token as Tokens.Codespan).text);
        case "link":
          return (
            renderInlineTokens((token as Tokens.Link).tokens) +
            theme.dim(` (${(token as Tokens.Link).href})`)
          );
        case "br":
          return "\n";
        case "del":
          return chalk.strikethrough(
            renderInlineTokens((token as Tokens.Del).tokens),
          );
        case "text": {
          const t = token as Tokens.Text;
          if (t.tokens && t.tokens.length > 0) {
            return renderInlineTokens(t.tokens);
          }
          return t.text;
        }
        case "escape":
          return (token as Tokens.Escape).text;
        case "image":
          return theme.dim(`[image: ${(token as Tokens.Image).text}]`);
        default:
          if ("text" in token) return (token as { text: string }).text;
          return "";
      }
    })
    .join("");
}

/**
 * Render inline markdown using regex (fallback for raw text strings).
 */
function renderInline(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, (_: string, t: string) => theme.bold(t))
    .replace(/\*(.+?)\*/g, (_: string, t: string) => theme.accent(t))
    .replace(/`(.+?)`/g, (_: string, t: string) => theme.secondary(t))
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      (_: string, label: string, url: string) => label + theme.dim(` (${url})`),
    );
}

/**
 * Word-wrap text respecting ANSI escape sequences.
 * Measures visible character width, not byte length.
 */
function wrapText(text: string, width: number): string {
  if (width <= 0) return text;

  const lines: string[] = [];
  // Split on existing newlines first
  const paragraphs = text.split("\n");

  for (const paragraph of paragraphs) {
    if (stripAnsi(paragraph).length <= width) {
      lines.push(paragraph);
      continue;
    }

    // Word-wrap this paragraph
    const words = paragraph.split(/(\s+)/);
    let currentLine = "";
    let currentWidth = 0;

    for (const word of words) {
      const wordWidth = stripAnsi(word).length;

      if (currentWidth + wordWidth > width && currentWidth > 0) {
        lines.push(currentLine);
        currentLine = "";
        currentWidth = 0;
        // Skip leading whitespace on new line
        if (/^\s+$/.test(word)) continue;
      }

      currentLine += word;
      currentWidth += wordWidth;
    }

    if (currentLine.length > 0) {
      lines.push(currentLine);
    }
  }

  return lines.join("\n");
}

/**
 * Strip ANSI escape sequences from a string to measure visible width.
 */
function stripAnsi(str: string): string {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*m/g, "");
}
