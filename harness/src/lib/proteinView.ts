import { execSync, exec as execCb } from "child_process";
import { existsSync } from "fs";

export type RenderMode = "sixel" | "kitty" | "iterm" | "ascii" | "none";

export interface TerminalInfo {
  term: string;
  colorTerm: string;
  columns: number;
  rows: number;
  renderMode: RenderMode;
  supportsTrueColor: boolean;
}

/**
 * Detect the terminal capabilities for protein structure rendering.
 */
export function getTerminalInfo(): TerminalInfo {
  const term = process.env.TERM ?? "";
  const colorTerm = process.env.COLORTERM ?? "";
  const columns = process.stdout.columns ?? 80;
  const rows = process.stdout.rows ?? 24;
  const renderMode = detectRenderMode();
  const supportsTrueColor =
    colorTerm === "truecolor" ||
    colorTerm === "24bit" ||
    term.includes("256color");

  return { term, colorTerm, columns, rows, renderMode, supportsTrueColor };
}

/**
 * Detect the best rendering mode for inline protein images.
 * Checks for Sixel, Kitty graphics protocol, and iTerm2 inline images.
 */
export function detectRenderMode(): RenderMode {
  const term = process.env.TERM ?? "";
  const termProgram = process.env.TERM_PROGRAM ?? "";
  const kittyPid = process.env.KITTY_PID ?? "";

  // Kitty graphics protocol
  if (kittyPid || termProgram === "kitty") return "kitty";

  // iTerm2 inline images
  if (termProgram === "iTerm.app" || process.env.ITERM_SESSION_ID)
    return "iterm";

  // Sixel support (common in xterm, mlterm, foot, WezTerm)
  if (
    term.includes("xterm") ||
    termProgram === "WezTerm" ||
    termProgram === "foot" ||
    termProgram === "mlterm"
  ) {
    // Probe for sixel support via DA1 response would require async IO,
    // so we check known-supporting terminals
    if (termProgram === "WezTerm" || termProgram === "foot") return "sixel";
  }

  // Fallback: no inline graphics
  return "none";
}

/**
 * Check if ProteinView (PyMOL-based renderer) is available.
 * Looks for pymol in PATH and our rendering script.
 */
export function isProteinViewAvailable(): boolean {
  // Check for PyMOL
  try {
    execSync("which pymol", { stdio: "pipe" });
  } catch {
    return false;
  }

  // Check for our rendering script
  const scriptPaths = [
    "/data/proteus/scripts/render_protein.py",
    process.env.PROTEUS_RENDER_SCRIPT ?? "",
  ].filter(Boolean);

  return scriptPaths.some((p) => existsSync(p));
}

/**
 * Launch ProteinView to render a protein structure file.
 * Returns a path to the rendered image file, or null on failure.
 */
export function launchProteinView(
  structurePath: string,
  options: {
    outputPath?: string;
    width?: number;
    height?: number;
    style?: "cartoon" | "surface" | "sticks" | "ribbon";
    colorScheme?: "chain" | "confidence" | "hydrophobicity" | "custom";
    highlightResidues?: string; // comma-separated residue IDs
    background?: "white" | "black" | "transparent";
  } = {},
): Promise<string | null> {
  return new Promise((resolve) => {
    if (!isProteinViewAvailable()) {
      resolve(null);
      return;
    }

    const {
      outputPath = "/tmp/proteus_render.png",
      width = 800,
      height = 600,
      style = "cartoon",
      colorScheme = "chain",
      highlightResidues,
      background = "white",
    } = options;

    const scriptPath =
      process.env.PROTEUS_RENDER_SCRIPT ??
      "/data/proteus/scripts/render_protein.py";

    const args = [
      `--input "${structurePath}"`,
      `--output "${outputPath}"`,
      `--width ${width}`,
      `--height ${height}`,
      `--style ${style}`,
      `--color-scheme ${colorScheme}`,
      `--background ${background}`,
    ];

    if (highlightResidues) {
      args.push(`--highlight "${highlightResidues}"`);
    }

    const cmd = `pymol -cq "${scriptPath}" -- ${args.join(" ")}`;

    execCb(cmd, { timeout: 30000 }, (error) => {
      if (error) {
        resolve(null);
        return;
      }
      if (existsSync(outputPath)) {
        resolve(outputPath);
      } else {
        resolve(null);
      }
    });
  });
}

/**
 * Display an image inline in the terminal if the terminal supports it.
 * Returns true if the image was displayed, false otherwise.
 */
export function displayInlineImage(
  imagePath: string,
  termInfo?: TerminalInfo,
): boolean {
  const info = termInfo ?? getTerminalInfo();

  if (!existsSync(imagePath)) return false;

  switch (info.renderMode) {
    case "kitty": {
      try {
        execSync(`kitty +kitten icat "${imagePath}"`, { stdio: "inherit" });
        return true;
      } catch {
        return false;
      }
    }
    case "iterm": {
      // iTerm2 inline image protocol
      try {
        const fs = require("fs");
        const data = fs.readFileSync(imagePath);
        const b64 = data.toString("base64");
        const seq = `\x1b]1337;File=inline=1:${b64}\x07`;
        process.stdout.write(seq);
        return true;
      } catch {
        return false;
      }
    }
    case "sixel": {
      try {
        execSync(`img2sixel "${imagePath}"`, { stdio: "inherit" });
        return true;
      } catch {
        return false;
      }
    }
    default:
      return false;
  }
}
