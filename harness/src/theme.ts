import chalk from "chalk";

// ---------------------------------------------------------------------------
// Colorblind-friendly palette
// ---------------------------------------------------------------------------
// Uses blue-amber-teal scheme safe for deuteranopia, protanopia, tritanopia.
// Key principle: never rely on green/red alone — pair with icons/text labels.
//
// Primary:  #448AFF (blue 400)      — universally distinguishable
// Accent:   #FFAB40 (amber 400)     — high contrast, safe for all types
// Teal:     #26C6DA (cyan 400)      — distinguishable from blue
// Success:  #69F0AE (green A200)    — always paired with checkmark icon
// Error:    #FF5252 (red A200)      — always paired with cross icon
// Warning:  #FFD740 (amber A200)    — always paired with triangle icon
// ---------------------------------------------------------------------------

export type ThemeName = "accessible" | "green";

interface ThemeColors {
  primaryHex: string;
  accentHex: string;
  successHex: string;
  warningHex: string;
  errorHex: string;
  tealHex: string;
  tealBrightHex: string;
}

const PALETTES: Record<ThemeName, ThemeColors> = {
  accessible: {
    primaryHex: "#448AFF",
    accentHex: "#FFAB40",
    successHex: "#69F0AE",
    warningHex: "#FFD740",
    errorHex: "#FF5252",
    tealHex: "#26C6DA",
    tealBrightHex: "#80DEEA",
  },
  green: {
    primaryHex: "#4CAF50",
    accentHex: "#66BB6A",
    successHex: "#4CAF50",
    warningHex: "#FFC107",
    errorHex: "#FF5252",
    tealHex: "#4DD0E1",
    tealBrightHex: "#80DEEA",
  },
};

function buildTheme(name: ThemeName) {
  const p = PALETTES[name];

  return {
    // Meta
    themeName: name,

    // Base colors
    primary: chalk.hex(p.primaryHex),
    primaryBold: chalk.hex(p.primaryHex).bold,
    accent: chalk.hex(p.accentHex),
    heading: chalk.white.bold,
    body: chalk.hex("#A0A0A0"),
    dim: chalk.hex("#606060"),
    bold: chalk.bold,
    success: chalk.hex(p.successHex),
    warning: chalk.hex(p.warningHex),
    error: chalk.hex(p.errorHex),
    running: chalk.hex(p.tealHex),
    id: chalk.hex(p.primaryHex),
    cyan: chalk.hex(p.tealHex),
    cyanBright: chalk.hex(p.tealBrightHex),
    highlight: chalk.hex("#FFD54F"),
    note: chalk.hex("#FFB74D"),
    prompt: chalk.hex(p.primaryHex)("\u25C6 "),
    bullet: chalk.hex(p.primaryHex)("\u25CF "),
    warnBullet: chalk.hex(p.warningHex)("\u25B2 "),

    // Semantic tokens
    userMessage: chalk.hex("#A0A0A0"),
    assistantText: chalk.hex("#E0E0E0"),
    toolActivity: chalk.hex(p.tealBrightHex),
    toolDone: chalk.hex(p.successHex),
    errorText: chalk.hex(p.errorHex),
    warningText: chalk.hex("#FFB74D"),

    // Tables
    tableHeader: chalk.bold.hex(p.accentHex),
    tableSeparator: chalk.dim.hex("#555555"),
    tableRow: chalk.hex("#E0E0E0"),

    // Scores — use blue/amber/red instead of green/yellow/red
    // Always accompanied by text labels (PASS/MARGINAL/FAIL) or numeric values
    scoreExcellent: chalk.hex(p.primaryHex),
    scoreGood: chalk.hex(p.tealHex),
    scoreModerate: chalk.hex(p.accentHex),
    scorePoor: chalk.hex(p.errorHex),

    // Code
    codeFence: chalk.hex("#78909C"),
    codeInline: chalk.hex("#80CBC4"),

    // Status — uses icons as primary signal, color as secondary
    // Icons: done=checkmark, running=bullet, failed=cross, pending=circle
    statusRunning: chalk.hex(p.tealBrightHex),
    statusComplete: chalk.hex(p.successHex),
    statusFailed: chalk.hex(p.errorHex),
    statusPending: chalk.dim,

    // Hex values for use in JSX components (ink <Text color=...>)
    hex: {
      primary: p.primaryHex,
      accent: p.accentHex,
      success: p.successHex,
      warning: p.warningHex,
      error: p.errorHex,
      teal: p.tealHex,
      tealBright: p.tealBrightHex,
      body: "#A0A0A0",
      dim: "#606060",
    },
  };
}

// Default to the accessible (colorblind-friendly) theme
export const theme = buildTheme("accessible");

// Export the builder for runtime switching
export { buildTheme, ThemeName as ThemeOption };
