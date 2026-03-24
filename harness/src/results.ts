import chalk from "chalk";
import { theme } from "./theme.js";

export interface DesignResult {
  rank: number;
  designName: string;
  ipTM: number;
  ipSAE: number | null;
  pLDDT: number | null;
  rmsd: number | null;
  liabilities: { high: number; medium: number; low: number };
  status: "PASS" | "MARGINAL" | "FAIL";
}

// ---------------------------------------------------------------------------
// Score coloring — uses theme semantic tokens
// ---------------------------------------------------------------------------

function colorScore(
  value: number | null,
  thresholds: { good: number; excellent: number; inverted?: boolean },
): string {
  if (value === null) return chalk.gray("\u2014");
  const str = value.toFixed(2);
  if (thresholds.inverted) {
    // Lower is better (RMSD)
    if (value <= thresholds.excellent) return theme.scoreExcellent(str);
    if (value <= thresholds.good) return theme.scoreGood(str);
    return theme.scorePoor(str);
  }
  if (value >= thresholds.excellent) return theme.scoreExcellent(str);
  if (value >= thresholds.good) return theme.scoreGood(str);
  return theme.scorePoor(str);
}

function colorRMSD(value: number | null): string {
  return colorScore(
    value !== null ? parseFloat(value.toFixed(1)) : null,
    { good: 3.5, excellent: 1.5, inverted: true },
  );
}

function colorStatus(status: DesignResult["status"]): string {
  switch (status) {
    case "PASS":
      return theme.scoreExcellent("PASS");
    case "MARGINAL":
      return theme.scoreModerate("MARGINAL");
    case "FAIL":
      return theme.scorePoor("FAIL");
  }
}

function formatLiabilities(liab: DesignResult["liabilities"]): string {
  if (liab.high > 0) return theme.scorePoor(`${liab.high} high`);
  if (liab.medium > 0) return theme.scoreModerate(`${liab.medium} med`);
  return theme.scoreExcellent("0");
}

// ---------------------------------------------------------------------------
// Helpers for space-aligned columns (strip ANSI for width calculation)
// ---------------------------------------------------------------------------

// eslint-disable-next-line no-control-regex
const ANSI_RE = /\u001b\[[0-9;]*m/g;

function visLen(s: string): number {
  return s.replace(ANSI_RE, "").length;
}

function pad(s: string, width: number): string {
  const diff = width - visLen(s);
  return diff > 0 ? s + " ".repeat(diff) : s;
}

// ---------------------------------------------------------------------------
// Column layout computation
// ---------------------------------------------------------------------------

interface ColumnDef {
  key: string;
  label: string;
  minWidth: number;
}

const ALL_COLUMNS: ColumnDef[] = [
  { key: "design",      label: "Design",      minWidth: 14 },
  { key: "ipSAE",       label: "ipSAE",       minWidth: 8 },
  { key: "ipTM",        label: "ipTM",        minWidth: 8 },
  { key: "pLDDT",       label: "pLDDT",       minWidth: 8 },
  { key: "rmsd",        label: "RMSD",        minWidth: 8 },
  { key: "liabilities", label: "Liabilities", minWidth: 12 },
  { key: "status",      label: "Status",      minWidth: 10 },
];

/** Columns to drop for narrow terminals (<90 cols). */
const NARROW_DROP = new Set(["rmsd", "liabilities"]);

function computeColumns(termWidth: number): { cols: ColumnDef[]; widths: Record<string, number> } {
  const indent = 2;
  const available = termWidth - indent;

  // Select columns based on terminal width
  let cols = ALL_COLUMNS;
  if (termWidth < 90) {
    cols = cols.filter((c) => !NARROW_DROP.has(c.key));
  }

  // Sum minimum widths
  const minTotal = cols.reduce((sum, c) => sum + c.minWidth, 0);

  // Distribute extra space proportionally
  const extra = Math.max(0, available - minTotal);
  const perCol = Math.floor(extra / cols.length);

  // Wide terminals get more generous spacing
  const bonus = termWidth > 140 ? 2 : 0;

  const widths: Record<string, number> = {};
  for (const col of cols) {
    widths[col.key] = col.minWidth + perCol + bonus;
  }

  // Give design column extra room if available
  if (extra > cols.length * 2) {
    widths["design"] = (widths["design"] ?? 14) + Math.min(6, Math.floor(extra / 4));
  }

  return { cols, widths };
}

// ---------------------------------------------------------------------------
// Cell renderers
// ---------------------------------------------------------------------------

function renderCell(key: string, d: DesignResult): string {
  switch (key) {
    case "design":      return d.designName;
    case "ipSAE":       return colorScore(d.ipSAE, { good: 0.5, excellent: 0.8 });
    case "ipTM":        return colorScore(d.ipTM, { good: 0.7, excellent: 0.85 });
    case "pLDDT":       return colorScore(d.pLDDT, { good: 70, excellent: 90 });
    case "rmsd":        return colorRMSD(d.rmsd);
    case "liabilities": return formatLiabilities(d.liabilities);
    case "status":      return colorStatus(d.status);
    default:            return "";
  }
}

// ---------------------------------------------------------------------------
// renderResults
// ---------------------------------------------------------------------------

export function renderResults(designs: DesignResult[], termWidth: number = 120): string {
  const I = "  "; // 2-space indent
  const lines: string[] = [];

  const { cols, widths } = computeColumns(termWidth);

  const fullWidth = cols.reduce((sum, c) => sum + (widths[c.key] ?? c.minWidth), 0);

  // -- Section title --
  lines.push("");
  lines.push(I + theme.heading("Design Results"));
  lines.push("");

  // -- Full table header --
  const headerRow = cols
    .map((c) => pad(c.label, widths[c.key] ?? c.minWidth))
    .join("");

  lines.push(I + theme.tableHeader(headerRow));
  lines.push(I + theme.tableSeparator("\u2500".repeat(fullWidth)));

  // -- Full table rows --
  for (const d of designs) {
    const row = cols
      .map((c) => pad(renderCell(c.key, d), widths[c.key] ?? c.minWidth))
      .join("");

    lines.push(I + row);
  }

  // -- Top 5 by ipSAE (primary metric) --
  const topN = 5;
  const sorted = [...designs]
    .sort((a, b) => (b.ipSAE ?? 0) - (a.ipSAE ?? 0) || b.ipTM - a.ipTM)
    .slice(0, topN);

  lines.push("");

  // Centered title
  const topTitle = "Top " + sorted.length + " by ipSAE";
  const topTitlePadded = " ".repeat(
    Math.max(0, Math.floor((fullWidth - topTitle.length) / 2)),
  );
  lines.push(I + topTitlePadded + theme.heading(topTitle));
  lines.push("");

  // Top-table: always compact (Rank, Design, ipSAE, ipTM, Status)
  const topCols = [
    { key: "rank",   label: "Rank",   width: 8 },
    { key: "design", label: "Design", width: Math.min(widths["design"] ?? 18, 20) },
    { key: "ipSAE",  label: "ipSAE",  width: 10 },
    { key: "ipTM",   label: "ipTM",   width: 10 },
    { key: "status", label: "Status", width: 10 },
  ];
  const topWidth = topCols.reduce((s, c) => s + c.width, 0);

  const topHeader = topCols.map((c) => pad(c.label, c.width)).join("");
  lines.push(I + theme.tableHeader(topHeader));
  lines.push(I + theme.tableSeparator("\u2500".repeat(topWidth)));

  sorted.forEach((d, i) => {
    const row =
      pad(String(i + 1), topCols[0].width) +
      pad(d.designName, topCols[1].width) +
      pad(colorScore(d.ipSAE, { good: 0.5, excellent: 0.8 }), topCols[2].width) +
      pad(colorScore(d.ipTM, { good: 0.7, excellent: 0.85 }), topCols[3].width) +
      colorStatus(d.status);

    lines.push(I + row);
  });

  // -- Warning note --
  lines.push("");
  lines.push(
    I +
      theme.warningText("\u26A0") +
      " " +
      theme.warningText(
        "Note: Run screening battery (/screen) for full developability assessment.",
      ),
  );

  // -- Next steps --
  lines.push("");
  lines.push(I + theme.heading("Next steps:"));
  lines.push("");
  lines.push(
    I + theme.accent("1") + " Run full screening on top candidates",
  );
  lines.push(
    I + theme.accent("2") + " Visualize best designs in structural viewer",
  );
  lines.push(
    I + theme.accent("3") + " Approve designs for experimental validation",
  );
  lines.push("");

  return lines.join("\n");
}
