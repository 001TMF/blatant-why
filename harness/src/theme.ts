import chalk from "chalk";

export const theme = {
  primary: chalk.hex("#4CAF50"),
  primaryBold: chalk.hex("#4CAF50").bold,
  accent: chalk.hex("#66BB6A"),
  heading: chalk.white.bold,
  body: chalk.hex("#A0A0A0"),
  dim: chalk.hex("#606060"),
  success: chalk.hex("#4CAF50"),
  warning: chalk.hex("#FFC107"),
  error: chalk.hex("#FF5252"),
  running: chalk.hex("#4CAF50"),
  id: chalk.hex("#4CAF50"),
  prompt: chalk.hex("#4CAF50")("◆ "),
  bullet: chalk.hex("#4CAF50")("● "),
  warnBullet: chalk.hex("#FFC107")("▲ "),
};
