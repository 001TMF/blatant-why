import { createInterface } from "node:readline";
import { writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";

export async function promptApiKeys(targetDir: string, skip: boolean): Promise<void> {
  if (skip) return;

  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const ask = (q: string): Promise<string> => new Promise(r => rl.question(q, r));

  console.log("\n  API Keys (press Enter to skip)\n");

  const tamarind = await ask("  TAMARIND_API_KEY: ");
  const adaptyv = await ask("  ADAPTYV_API_KEY: ");

  rl.close();

  const localSettings: Record<string, unknown> = {};
  const env: Record<string, string> = {};

  if (tamarind.trim()) env.TAMARIND_API_KEY = tamarind.trim();
  if (adaptyv.trim()) env.ADAPTYV_API_KEY = adaptyv.trim();

  if (Object.keys(env).length > 0) {
    localSettings.env = env;
    const settingsPath = resolve(targetDir, ".claude", "settings.local.json");
    mkdirSync(dirname(settingsPath), { recursive: true });
    writeFileSync(settingsPath, JSON.stringify(localSettings, null, 2) + "\n");
    console.log("  Saved to .claude/settings.local.json (gitignored)");
  }
}
