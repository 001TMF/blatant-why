/**
 * screenshot_mockups.mjs — Uses Playwright MCP to screenshot the HTML mockups.
 *
 * For each of the 5 scenario terminal mockups, takes a targeted screenshot
 * and saves to docs/screenshots/.
 *
 * Usage: Run via Claude Code (uses Playwright MCP browser tools).
 *        Or: npx playwright test --config=playwright.config.mjs
 *
 * This script is designed to be called from Claude Code using the
 * Playwright MCP tools (browser_navigate, browser_take_screenshot, etc.)
 */

// This is a descriptor file — the actual screenshotting is done via
// Playwright MCP tools called by Claude Code.
//
// Steps for Claude Code:
// 1. browser_navigate to file:///...harness/test_mockups.html
// 2. For each #scenario-N element:
//    a. Scroll to it
//    b. Take a screenshot of that element
//    c. Save to docs/screenshots/test-N-<name>.png

export const scenarios = [
  { id: "scenario-1", name: "beginner-question", label: "Simple Beginner Question" },
  { id: "scenario-2", name: "expert-parameters", label: "Expert with Parameters" },
  { id: "scenario-3", name: "liability-screening", label: "Liability Screening" },
  { id: "scenario-4", name: "research-target", label: "Research EGFR Target" },
  { id: "scenario-5", name: "help-command", label: "/help Command" },
];
