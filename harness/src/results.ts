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
// Score coloring
// ---------------------------------------------------------------------------

function colorScore(
  value: number | null,
  thresholds: { good: number; excellent: number; inverted?: boolean },
): string {
  if (value === null) return chalk.gray("\u2014");
  const str = value.toFixed(2);
  if (thresholds.inverted) {
    // Lower is better (RMSD)
    if (value <= thresholds.excellent) return chalk.hex("#4CAF50")(str);
    if (value <= thresholds.good) return chalk.hex("#66BB6A")(str);
    return chalk.hex("#FF5252")(str);
  }
  if (value >= thresholds.excellent) return chalk.hex("#4CAF50")(str);
  if (value >= thresholds.good) return chalk.hex("#66BB6A")(str);
  return chalk.hex("#FF5252")(str);
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
      return chalk.hex("#4CAF50")("PASS");
    case "MARGINAL":
      return chalk.hex("#FFC107")("MARGINAL");
    case "FAIL":
      return chalk.hex("#FF5252")("FAIL");
  }
}

function formatLiabilities(liab: DesignResult["liabilities"]): string {
  if (liab.high > 0) return chalk.hex("#FF5252")(`${liab.high} high`);
  if (liab.medium > 0) return chalk.hex("#FFC107")(`${liab.medium} med`);
  return chalk.hex("#4CAF50")("0");
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
// renderResults
// ---------------------------------------------------------------------------

export function renderResults(designs: DesignResult[]): string {
  const I = "  "; // 2-space indent
  const lines: string[] = [];

  // Column widths (generous spacing) — ipSAE first as primary metric
  const W = {
    design: 18,
    ipSAE: 10,
    ipTM: 10,
    pLDDT: 10,
    rmsd: 10,
    liabilities: 16,
    status: 10,
  };

  const fullWidth =
    W.design + W.ipSAE + W.ipTM + W.pLDDT + W.rmsd + W.liabilities + W.status;

  // -- Section title --
  lines.push("");
  lines.push(I + chalk.white.bold("Design Results"));
  lines.push("");

  // -- Full table header --
  const headerRow =
    pad("Design", W.design) +
    pad("ipSAE", W.ipSAE) +
    pad("ipTM", W.ipTM) +
    pad("pLDDT", W.pLDDT) +
    pad("RMSD", W.rmsd) +
    pad("Liabilities", W.liabilities) +
    pad("Status", W.status);

  lines.push(I + chalk.white.bold(headerRow));
  lines.push(I + "\u2500".repeat(fullWidth));

  // -- Full table rows --
  for (const d of designs) {
    const row =
      pad(d.designName, W.design) +
      pad(colorScore(d.ipSAE, { good: 0.5, excellent: 0.8 }), W.ipSAE) +
      pad(colorScore(d.ipTM, { good: 0.7, excellent: 0.85 }), W.ipTM) +
      pad(colorScore(d.pLDDT, { good: 70, excellent: 90 }), W.pLDDT) +
      pad(colorRMSD(d.rmsd), W.rmsd) +
      pad(formatLiabilities(d.liabilities), W.liabilities) +
      colorStatus(d.status);

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
  lines.push(I + topTitlePadded + chalk.white.bold(topTitle));
  lines.push("");

  // Top-table column widths — ipSAE first
  const TW = {
    rank: 8,
    design: 18,
    ipSAE: 10,
    ipTM: 10,
    status: 10,
  };
  const topWidth = TW.rank + TW.design + TW.ipSAE + TW.ipTM + TW.status;

  const topHeader =
    pad("Rank", TW.rank) +
    pad("Design", TW.design) +
    pad("ipSAE", TW.ipSAE) +
    pad("ipTM", TW.ipTM) +
    pad("Status", TW.status);

  lines.push(I + chalk.white.bold(topHeader));
  lines.push(I + "\u2500".repeat(topWidth));

  sorted.forEach((d, i) => {
    const row =
      pad(String(i + 1), TW.rank) +
      pad(d.designName, TW.design) +
      pad(colorScore(d.ipSAE, { good: 0.5, excellent: 0.8 }), TW.ipSAE) +
      pad(colorScore(d.ipTM, { good: 0.7, excellent: 0.85 }), TW.ipTM) +
      colorStatus(d.status);

    lines.push(I + row);
  });

  // -- Warning note --
  lines.push("");
  lines.push(
    I +
      chalk.hex("#FFC107")("\u26A0") +
      " " +
      chalk.hex("#FFC107")(
        "Note: Run screening battery (/screen) for full developability assessment.",
      ),
  );

  // -- Next steps --
  lines.push("");
  lines.push(I + chalk.white.bold("Next steps:"));
  lines.push("");
  lines.push(
    I + chalk.cyan.bold("1") + " Run full screening on top candidates",
  );
  lines.push(
    I + chalk.cyan.bold("2") + " Visualize best designs in structural viewer",
  );
  lines.push(
    I + chalk.cyan.bold("3") + " Approve designs for experimental validation",
  );
  lines.push("");

  return lines.join("\n");
}
