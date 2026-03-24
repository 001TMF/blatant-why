import chalk from "chalk";

// ---------------------------------------------------------------------------
// Okabe-Ito colorblind-safe palette (Nature Methods standard)
// ---------------------------------------------------------------------------
// All meet WCAG AA contrast against dark backgrounds.
// Key principle: never rely on color alone — pair with icons/text labels.
//
// skyBlue:      #56B4E9 — Primary — info, links, active
// orange:       #E69F00 — Accent — warnings, highlights
// bluishGreen:  #009E73 — Success — always paired with ✔ icon
// vermillion:   #D55E00 — Error — always paired with ✖ icon
// blue:         #0072B2 — Secondary — headings, emphasis
// reddishPurple:#CC79A7 — Muted — timestamps, metadata
// yellow:       #F5C710 — Highlight — search matches
// ---------------------------------------------------------------------------

export type ThemeName = "accessible" | "green";

interface ThemeColors {
  primaryHex: string;
  accentHex: string;
  successHex: string;
  warningHex: string;
  errorHex: string;
  secondaryHex: string;
  mutedHex: string;
  highlightHex: string;
}

const PALETTES: Record<ThemeName, ThemeColors> = {
  accessible: {
    primaryHex: "#56B4E9",   // Okabe-Ito skyBlue
    accentHex: "#E69F00",    // Okabe-Ito orange
    successHex: "#009E73",   // Okabe-Ito bluishGreen
    warningHex: "#E69F00",   // Okabe-Ito orange (warnings = accent)
    errorHex: "#D55E00",     // Okabe-Ito vermillion
    secondaryHex: "#0072B2", // Okabe-Ito blue
    mutedHex: "#CC79A7",     // Okabe-Ito reddishPurple
    highlightHex: "#F5C710", // Okabe-Ito yellow
  },
  green: {
    primaryHex: "#56B4E9",   // Okabe-Ito skyBlue (replaces old green)
    accentHex: "#E69F00",    // Okabe-Ito orange
    successHex: "#009E73",   // Okabe-Ito bluishGreen
    warningHex: "#E69F00",   // Okabe-Ito orange
    errorHex: "#D55E00",     // Okabe-Ito vermillion
    secondaryHex: "#0072B2", // Okabe-Ito blue
    mutedHex: "#CC79A7",     // Okabe-Ito reddishPurple
    highlightHex: "#F5C710", // Okabe-Ito yellow
  },
};

function buildTheme(name: ThemeName) {
  const p = PALETTES[name];

  return {
    // Meta
    themeName: name,

    // Base colors (Okabe-Ito)
    primary: chalk.hex(p.primaryHex),
    primaryBold: chalk.hex(p.primaryHex).bold,
    accent: chalk.hex(p.accentHex),
    secondary: chalk.hex(p.secondaryHex),
    heading: chalk.white.bold,
    body: chalk.hex("#A0A0A0"),
    dim: chalk.hex("#606060"),
    muted: chalk.hex(p.mutedHex),
    bold: chalk.bold,
    success: chalk.hex(p.successHex),
    warning: chalk.hex(p.warningHex),
    error: chalk.hex(p.errorHex),
    running: chalk.hex(p.primaryHex),
    id: chalk.hex(p.secondaryHex),
    cyan: chalk.hex(p.primaryHex),
    cyanBright: chalk.hex(p.primaryHex),
    highlight: chalk.hex(p.highlightHex),
    note: chalk.hex(p.accentHex),
    prompt: chalk.hex(p.primaryHex)("\u25C6 "),
    bullet: chalk.hex(p.primaryHex)("\u25CF "),
    warnBullet: chalk.hex(p.warningHex)("\u25B2 "),

    // Semantic tokens
    userMessage: chalk.hex("#A0A0A0"),
    assistantText: chalk.hex("#E0E0E0"),
    toolActivity: chalk.hex(p.primaryHex),
    toolDone: chalk.hex(p.successHex),
    errorText: chalk.hex(p.errorHex),
    warningText: chalk.hex(p.accentHex),

    // Tables
    tableHeader: chalk.bold.hex(p.accentHex),
    tableSeparator: chalk.dim.hex("#555555"),
    tableRow: chalk.hex("#E0E0E0"),

    // Scores — Okabe-Ito: blue/green/orange/vermillion
    // Always accompanied by text labels (PASS/MARGINAL/FAIL) or numeric values
    scoreExcellent: chalk.hex(p.secondaryHex),
    scoreGood: chalk.hex(p.successHex),
    scoreModerate: chalk.hex(p.accentHex),
    scorePoor: chalk.hex(p.errorHex),

    // Code (Okabe-Ito colors for syntax highlighting)
    codeFence: chalk.hex("#78909C"),
    codeInline: chalk.hex(p.primaryHex),

    // Status — uses icons as primary signal, color as secondary
    // Icons: ✔ complete, ● running, ✖ failed, ○ pending
    statusRunning: chalk.hex(p.primaryHex),
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
      secondary: p.secondaryHex,
      muted: p.mutedHex,
      highlight: p.highlightHex,
      body: "#A0A0A0",
      dim: "#606060",
    },
  };
}

// Default to the accessible (colorblind-friendly) theme
export const theme = buildTheme("accessible");

// Export the builder for runtime switching
export { buildTheme, ThemeName as ThemeOption };
