import { spawnSync } from "child_process";
import { existsSync } from "fs";

// Detect terminal capabilities for ProteinView render mode
function detectRenderMode(): string {
  if (process.env.KITTY_WINDOW_ID) return "--fullhd";
  if (process.env.TERM_PROGRAM === "iTerm.app") return "--fullhd";
  if (process.env.SSH_CONNECTION || process.env.TERM?.includes("screen") || process.env.TERM?.includes("tmux")) return "--hd";
  return "--hd";
}

// Find proteinview binary
function findProteinView(): string | null {
  const paths = [
    process.env.HOME + "/.cargo/bin/proteinview",
    "/usr/local/bin/proteinview",
    "proteinview",
  ];
  for (const p of paths) {
    try {
      const result = spawnSync("which", [p], { stdio: "pipe" });
      if (result.status === 0) return result.stdout.toString().trim() || p;
    } catch { /* continue */ }
  }
  return null;
}

export function isProteinViewAvailable(): boolean {
  return findProteinView() !== null;
}

export function getTerminalInfo(): { renderMode: string; available: boolean } {
  return {
    renderMode: detectRenderMode(),
    available: isProteinViewAvailable(),
  };
}

export interface ViewOptions {
  colorScheme?: string;  // "plddt", "chain", "rainbow", "bfactor"
  renderMode?: string;   // "--hd", "--fullhd", "--braille"
}

// Launch ProteinView with full terminal handoff
// Returns true if launched successfully, false if not available
export function launchProteinView(
  structurePath: string,
  options: ViewOptions = {},
): boolean {
  const binary = findProteinView();
  if (!binary) return false;
  if (!existsSync(structurePath)) return false;

  const renderMode = options.renderMode || detectRenderMode();
  const colorScheme = options.colorScheme || "plddt";

  const args = [structurePath, renderMode, "--color", colorScheme];

  // Full terminal handoff — proteinview takes over, returns on quit
  const result = spawnSync(binary, args, {
    stdio: "inherit",  // Give it full terminal control
    env: { ...process.env },
  });

  return result.status === 0;
}
