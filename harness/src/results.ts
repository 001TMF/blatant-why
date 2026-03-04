import chalk from "chalk";
import { theme } from "./theme.js";

export interface DesignResult {
  rank: number;
  designName: string;
  ipTM: number;
  ipSAE: number | null;
  pBind: number | null;
  rmsd: number | null;
  liabilities: { high: number; medium: number; low: number };
  status: "PASS" | "MARGINAL" | "FAIL";
}

function formatScore(value: number | null, thresholds: { good: number; excellent: number }): string {
  if (value === null) return theme.dim("—");
  const str = value.toFixed(2);
  if (value >= thresholds.excellent) return theme.success(str);
  if (value >= thresholds.good) return theme.accent(str);
  return theme.warning(str);
}

function formatRMSD(value: number | null): string {
  if (value === null) return theme.dim("—");
  const str = value.toFixed(1) + "A";
  if (value <= 1.5) return theme.success(str);
  if (value <= 3.5) return theme.accent(str);
  return theme.error(str);
}

function formatStatus(status: DesignResult["status"]): string {
  switch (status) {
    case "PASS": return theme.success("PASS");
    case "MARGINAL": return theme.warning("MARGINAL");
    case "FAIL": return theme.error("FAIL");
  }
}

function formatLiabilities(liab: DesignResult["liabilities"]): string {
  if (liab.high > 0) return theme.error(`${liab.high} high`);
  if (liab.medium > 0) return theme.warning(`${liab.medium} med`);
  return theme.success("0");
}

export function renderResults(designs: DesignResult[], pbindAvailable: boolean = false): string {
  const lines: string[] = [];

  // Header
  const headers = ["Rank", "Design", "ipTM", "ipSAE", "p_bind", "RMSD", "Liabilities", "Status"];
  const widths = [6, 14, 8, 8, 8, 8, 14, 10];

  lines.push(
    theme.heading(
      headers.map((h, i) => h.padEnd(widths[i])).join("")
    )
  );

  // Data rows
  for (const d of designs) {
    const cols = [
      String(d.rank).padEnd(widths[0]),
      d.designName.padEnd(widths[1]),
      formatScore(d.ipTM, { good: 0.7, excellent: 0.85 }).padEnd(widths[2]),
      formatScore(d.ipSAE, { good: 0.5, excellent: 0.8 }).padEnd(widths[3]),
      formatScore(d.pBind, { good: 0.5, excellent: 0.8 }).padEnd(widths[4]),
      formatRMSD(d.rmsd).padEnd(widths[5]),
      formatLiabilities(d.liabilities).padEnd(widths[6]),
      formatStatus(d.status),
    ];
    lines.push(cols.join(""));
  }

  // Warnings
  if (!pbindAvailable) {
    lines.push("");
    lines.push(theme.warnBullet + theme.warning(" Note: p_bind scores require trained checkpoint."));
  }

  // Next steps
  lines.push("");
  lines.push(theme.heading("Next steps:"));
  lines.push(`${theme.id("1")} Visualize the structure with hotspots highlighted?`);
  lines.push(`${theme.id("2")} Run full screening battery on top designs?`);
  lines.push(`${theme.id("3")} Approve top designs for experimental validation?`);

  return lines.join("\n");
}
