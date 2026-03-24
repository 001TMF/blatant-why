import chalk from "chalk";

export const theme = {
  // Base colors
  primary: chalk.hex("#4CAF50"),
  primaryBold: chalk.hex("#4CAF50").bold,
  accent: chalk.hex("#66BB6A"),
  heading: chalk.white.bold,
  body: chalk.hex("#A0A0A0"),
  dim: chalk.hex("#606060"),
  bold: chalk.bold,
  success: chalk.hex("#4CAF50"),
  warning: chalk.hex("#FFC107"),
  error: chalk.hex("#FF5252"),
  running: chalk.hex("#4CAF50"),
  id: chalk.hex("#4CAF50"),
  cyan: chalk.hex("#4DD0E1"),
  cyanBright: chalk.hex("#80DEEA"),
  highlight: chalk.hex("#FFD54F"),
  note: chalk.hex("#FFB74D"),
  prompt: chalk.hex("#4CAF50")("◆ "),
  bullet: chalk.hex("#4CAF50")("● "),
  warnBullet: chalk.hex("#FFC107")("▲ "),

  // Semantic tokens
  userMessage: chalk.hex("#A0A0A0"),
  assistantText: chalk.hex("#E0E0E0"),
  toolActivity: chalk.hex("#80DEEA"),
  toolDone: chalk.hex("#4CAF50"),
  errorText: chalk.hex("#FF5252"),
  warningText: chalk.hex("#FFB74D"),

  // Tables
  tableHeader: chalk.bold.hex("#66BB6A"),
  tableSeparator: chalk.dim.hex("#555555"),
  tableRow: chalk.hex("#E0E0E0"),

  // Scores
  scoreExcellent: chalk.hex("#4CAF50"),
  scoreGood: chalk.hex("#66BB6A"),
  scoreModerate: chalk.hex("#FFB74D"),
  scorePoor: chalk.hex("#FF5252"),

  // Code
  codeFence: chalk.hex("#78909C"),
  codeInline: chalk.hex("#80CBC4"),

  // Status
  statusRunning: chalk.hex("#80DEEA"),
  statusComplete: chalk.hex("#4CAF50"),
  statusFailed: chalk.hex("#FF5252"),
  statusPending: chalk.dim,
};
