import { theme } from "./theme.js";

const BANNER_TEXT = `
██████╗ ██████╗  ██████╗ ████████╗███████╗██╗   ██╗███████╗
██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝██║   ██║██╔════╝
██████╔╝██████╔╝██║   ██║   ██║   █████╗  ██║   ██║███████╗
██╔═══╝ ██╔══██╗██║   ██║   ██║   ██╔══╝  ██║   ██║╚════██║
██║     ██║  ██║╚██████╔╝   ██║   ███████╗╚██████╔╝███████║
╚═╝     ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚══════╝
`;

export function renderBanner(): string {
  return theme.primary(BANNER_TEXT.trim());
}

export function renderSubtitle(mode: string): string {
  return theme.dim("  Protein Design Agent") + "  " + theme.accent(`[${mode}]`);
}
