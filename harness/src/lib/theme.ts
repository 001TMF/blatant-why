import chalk from "chalk";

// Okabe-Ito palette (Nature Methods standard, WCAG AA compliant)
const PALETTE = {
  skyBlue: "#56B4E9",
  orange: "#E69F00",
  bluishGreen: "#009E73",
  vermillion: "#D55E00",
  blue: "#0072B2",
  reddishPurple: "#CC79A7",
  yellow: "#F5C710",
  white: "#FFFFFF",
  body: "#B0B0B0",
  dim: "#707070",
  bg: "#1A1A2E",
};

export const theme = {
  primary: chalk.hex(PALETTE.skyBlue),
  accent: chalk.hex(PALETTE.orange),
  success: chalk.hex(PALETTE.bluishGreen),
  error: chalk.hex(PALETTE.vermillion),
  warning: chalk.hex(PALETTE.orange),
  secondary: chalk.hex(PALETTE.blue),
  muted: chalk.hex(PALETTE.reddishPurple),
  highlight: chalk.hex(PALETTE.yellow),
  body: chalk.hex(PALETTE.body),
  dim: chalk.dim,
  bold: chalk.bold,
  heading: chalk.hex(PALETTE.white).bold,

  // For Ink <Text color={theme.hex.primary}>
  hex: {
    primary: PALETTE.skyBlue,
    accent: PALETTE.orange,
    success: PALETTE.bluishGreen,
    error: PALETTE.vermillion,
    warning: PALETTE.orange,
    secondary: PALETTE.blue,
    muted: PALETTE.reddishPurple,
    highlight: PALETTE.yellow,
    body: PALETTE.body,
    dim: PALETTE.dim,
    bg: PALETTE.bg,
    white: PALETTE.white,
  },

  // Score coloring (always pair with icons, never color alone)
  scoreColor: (
    value: number,
    thresholds: { good: number; excellent: number },
  ): string => {
    if (value >= thresholds.excellent) return PALETTE.bluishGreen;
    if (value >= thresholds.good) return PALETTE.skyBlue;
    if (value >= thresholds.good * 0.6) return PALETTE.orange;
    return PALETTE.vermillion;
  },

  // Predefined threshold sets for protein design metrics
  thresholds: {
    ipSAE: { good: 0.5, excellent: 0.8 },
    ipTM: { good: 0.7, excellent: 0.85 },
    pLDDT: { good: 70, excellent: 90 },
    rmsd: { good: 3.5, excellent: 1.5 }, // lower is better, invert when using scoreColor
  },
} as const;

// Unicode icons (always paired with color, never color alone)
export const ICONS = {
  success: "\u2714",    // check mark
  error: "\u2716",      // heavy X
  warning: "\u25B2",    // triangle up
  running: "\u25CF",    // filled circle
  pending: "\u25CB",    // open circle
  prompt: "\u25C6",     // diamond
  arrow: "\u2192",      // right arrow
  bullet: "\u25B8",     // right triangle
  separator: "\u2500",  // horizontal line
  branch: "\u251C",     // tee
  corner: "\u2514",     // bottom-left corner
  vertical: "\u2502",   // vertical line
  topLeft: "\u250C",    // top-left corner
  topRight: "\u2510",   // top-right corner
  bottomLeft: "\u2514", // bottom-left corner
  bottomRight: "\u2518",// bottom-right corner
};

// Format a score with color for terminal display
export function formatScore(
  value: number,
  thresholds: { good: number; excellent: number },
  precision: number = 3,
): string {
  const color = theme.scoreColor(value, thresholds);
  return chalk.hex(color)(value.toFixed(precision));
}

// Format a RMSD score (lower is better, inverted color logic)
export function formatRmsd(value: number, precision: number = 2): string {
  let color: string;
  if (value <= 1.5) color = PALETTE.bluishGreen;
  else if (value <= 3.5) color = PALETTE.skyBlue;
  else if (value <= 5.0) color = PALETTE.orange;
  else color = PALETTE.vermillion;
  return chalk.hex(color)(value.toFixed(precision) + "\u212B"); // angstrom symbol
}

// Status badge with icon + colored text
export function statusBadge(
  status: "success" | "error" | "warning" | "running" | "pending",
): string {
  const config: Record<string, { icon: string; color: (s: string) => string }> =
    {
      success: { icon: ICONS.success, color: theme.success },
      error: { icon: ICONS.error, color: theme.error },
      warning: { icon: ICONS.warning, color: theme.warning },
      running: { icon: ICONS.running, color: theme.primary },
      pending: { icon: ICONS.pending, color: theme.muted },
    };
  const { icon, color } = config[status];
  return color(`${icon} ${status}`);
}
