import { existsSync, readFileSync, readdirSync, statSync, writeFileSync, mkdirSync } from "fs";
import { resolve, basename } from "path";

type Message =
  | { type: "user"; text: string }
  | { type: "assistant"; text: string }
  | { type: "error"; text: string };

interface CampaignRun {
  run_id: string;
  scaffold: string;
  status: string;
  designs_requested: number;
  designs_generated: number;
  designs_passed: number;
  top_iptm: number;
  top_ipsae: number;
}

interface CampaignRound {
  round_id: number;
  state: string;
  runs: CampaignRun[];
  parameters?: Record<string, unknown>;
}

interface CampaignLog {
  campaign_id: string;
  target?: { name?: string; pdb_id?: string };
  status: string;
  rounds: CampaignRound[];
  costs?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

interface CampaignEntry {
  name: string;
  status: string;
  lastUpdated: string;
  dir: string;
  log?: CampaignLog;
}

function parseCampaignLog(logPath: string, dir: string, fallbackName: string): CampaignEntry {
  try {
    const log = JSON.parse(readFileSync(logPath, "utf-8")) as CampaignLog;
    return {
      name: log.campaign_id ?? fallbackName,
      status: log.status ?? "unknown",
      lastUpdated: log.updated_at ?? statSync(logPath).mtime.toISOString(),
      dir,
      log,
    };
  } catch {
    return {
      name: fallbackName,
      status: "unknown",
      lastUpdated: statSync(dir).mtime.toISOString(),
      dir,
    };
  }
}

function listCampaigns(projectDir: string): CampaignEntry[] {
  const campaignsDir = resolve(projectDir, "campaigns");
  if (!existsSync(campaignsDir)) return [];

  const entries: CampaignEntry[] = [];
  const seen = new Set<string>();

  try {
    const items = readdirSync(campaignsDir);
    for (const item of items) {
      const itemDir = resolve(campaignsDir, item);
      if (!statSync(itemDir).isDirectory()) continue;

      // Flat layout: campaigns/<campaign_id>/campaign_log.json
      const flatLog = resolve(itemDir, "campaign_log.json");
      if (existsSync(flatLog)) {
        if (!seen.has(itemDir)) {
          seen.add(itemDir);
          entries.push(parseCampaignLog(flatLog, itemDir, item));
        }
        continue;
      }

      // Nested layout: campaigns/<target>/<run>/campaign_log.json
      const subItems = readdirSync(itemDir);
      for (const sub of subItems) {
        const subDir = resolve(itemDir, sub);
        if (!statSync(subDir).isDirectory()) continue;
        const nestedLog = resolve(subDir, "campaign_log.json");
        if (existsSync(nestedLog) && !seen.has(subDir)) {
          seen.add(subDir);
          entries.push(parseCampaignLog(nestedLog, subDir, `${item}/${sub}`));
        }
      }
    }
  } catch (err) {
    process.stderr.write(`[proteus] Failed to list campaigns: ${err}\n`);
    return [{ name: "error", status: "error", lastUpdated: new Date().toISOString(), dir: campaignsDir }];
  }
  // Sort by most recently updated first
  entries.sort((a, b) => new Date(b.lastUpdated).getTime() - new Date(a.lastUpdated).getTime());
  return entries;
}

function formatRelativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function estimateCampaignCost(log: CampaignLog): string {
  // Check explicit costs object first
  if (log.costs && typeof log.costs === "object") {
    const total = Object.values(log.costs).reduce((sum: number, v) => {
      return sum + (typeof v === "number" ? v : 0);
    }, 0);
    if (total > 0) return `$${total.toFixed(0)} compute`;
  }
  // Estimate from design counts: ~$0.003 per design (Tamarind BoltzGen rate)
  let totalDesigns = 0;
  for (const round of log.rounds) {
    for (const run of round.runs) {
      totalDesigns += run.designs_generated || 0;
    }
  }
  if (totalDesigns === 0) return "$0 compute";
  const est = Math.max(1, Math.round(totalDesigns * 0.003));
  return `~$${est} compute`;
}

function inferNextAction(log: CampaignLog): string {
  const status = log.status;
  if (status === "ranked") return "Lab submission pending (/approve-lab)";
  if (status === "screening") return "Screening in progress...";
  if (status === "designing") {
    for (const round of log.rounds) {
      for (const run of round.runs) {
        if (run.status === "running" || run.status === "pending") {
          return `${run.scaffold} job running... wait for completion`;
        }
      }
    }
    return "Design runs complete, awaiting screening";
  }
  if (status === "configured") return "Ready to launch (/campaign)";
  if (status === "draft") return "Configure and launch (/campaign)";
  if (status === "submitted") return "Awaiting lab results";
  if (status === "complete") return "Campaign complete";
  return "Resume with /campaign";
}

function formatCampaignDetail(c: CampaignEntry, index: number): string[] {
  const lines: string[] = [];
  const log = c.log;
  const timeAgo = formatRelativeTime(c.lastUpdated);
  const cost = log ? estimateCampaignCost(log) : "";

  // Header line: number, name, status, age, cost
  const costStr = cost ? `  ·  ${cost}` : "";
  lines.push(`  ${index}. ${c.name} [${c.status}]  ·  ${timeAgo}${costStr}`);

  if (!log || log.rounds.length === 0) {
    lines.push("     No rounds yet");
    lines.push(`     Next: ${log ? inferNextAction(log) : "Resume with /campaign"}`);
    return lines;
  }

  // Per-round detail
  for (const round of log.rounds) {
    const totalGenerated = round.runs.reduce((s, r) => s + (r.designs_generated || 0), 0);
    const totalPassed = round.runs.reduce((s, r) => s + (r.designs_passed || 0), 0);
    const totalRequested = round.runs.reduce((s, r) => s + (r.designs_requested || 0), 0);

    const hasData = totalGenerated > 0 || totalRequested > 0;
    if (!hasData && round.runs.some(r => r.status === "running" || r.status === "pending")) {
      const activeRun = round.runs.find(r => r.status === "running");
      const provider = round.parameters?.provider ?? "compute";
      lines.push(`     Round ${round.round_id}: ${activeRun?.scaffold ?? "design"} job running on ${provider}...`);
      continue;
    }

    const passRate = totalGenerated > 0 ? ((totalPassed / totalGenerated) * 100).toFixed(1) : "0";
    const funnelParts: string[] = [];
    if (totalRequested > 0) funnelParts.push(`${totalRequested.toLocaleString()} requested`);
    if (totalGenerated > 0) funnelParts.push(`${totalGenerated.toLocaleString()} generated`);
    if (totalPassed > 0) funnelParts.push(`${totalPassed} passed (${passRate}%)`);

    if (funnelParts.length > 0) {
      lines.push(`     Round ${round.round_id}: ${funnelParts.join(" → ")}`);
    } else {
      lines.push(`     Round ${round.round_id}: pending`);
    }

    const runsWithData = round.runs.filter(r => r.designs_generated > 0 || r.designs_passed > 0);
    if (runsWithData.length > 0) {
      const scaffoldParts = runsWithData.map(r => {
        const parts = [`${r.scaffold}: ${r.designs_passed} passed`];
        if (r.top_ipsae > 0) parts.push(`ipSAE ${r.top_ipsae.toFixed(2)}`);
        else if (r.top_iptm > 0) parts.push(`ipTM ${r.top_iptm.toFixed(2)}`);
        return parts.join(", ");
      });
      lines.push(`       ${scaffoldParts.join("  |  ")}`);
    }
  }

  if (log) {
    lines.push(`     Next: ${inferNextAction(log)}`);
  }

  return lines;
}

export interface LocalCommandResult {
  handled: boolean;
  messages?: Message[];
}

/**
 * Handle local slash commands that don't need to go to the agent.
 * Returns messages to append to the conversation if handled.
 */
export function handleLocalCommand(
  localCommand: string,
  trimmed: string,
  campaignDir: string | null,
  projectDir: string,
  opts: {
    exportMarkdownFn?: () => string | null;
    exportCsvFn?: () => string | null;
  },
): LocalCommandResult {
  if (localCommand === "show_jobs") {
    const manifestPath = resolve(projectDir, ".proteus", "active-run.json");
    const jobLines: string[] = [];
    if (existsSync(manifestPath)) {
      try {
        const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
        const elapsed = manifest.startTime
          ? Math.round((Date.now() - manifest.startTime) / 60000)
          : 0;
        const status = manifest.pid ? "running" : "pending";
        jobLines.push(`  ${manifest.runId ?? "unknown"}    ${manifest.tool ?? "unknown"}    ${status}    ${elapsed}m elapsed`);
      } catch {
        // Ignore parse errors
      }
    }
    if (jobLines.length === 0) {
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: "No active cloud compute jobs." },
        ],
      };
    }
    const header = "  Job ID                              Tool           Status     Elapsed";
    const sep = "  " + "\u2500".repeat(68);
    return {
      handled: true,
      messages: [
        { type: "user", text: trimmed },
        { type: "assistant", text: ["Active Cloud Jobs", "", header, sep, ...jobLines].join("\n") },
      ],
    };
  }

  if (localCommand === "export_markdown" || localCommand === "export_csv") {
    const isCsv = localCommand === "export_csv";
    const content = isCsv ? opts.exportCsvFn?.() : opts.exportMarkdownFn?.();
    if (!content) {
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: "No conversation log found to export." },
        ],
      };
    }
    const ext = isCsv ? "csv" : "md";
    const exportDir = resolve(projectDir, ".proteus");
    mkdirSync(exportDir, { recursive: true });
    const date = new Date().toISOString().slice(0, 10);
    const time = new Date().toISOString().slice(11, 19).replace(/:/g, "");
    const exportPath = resolve(exportDir, `conversation_export_${date}_${time}.${ext}`);
    writeFileSync(exportPath, content);
    return {
      handled: true,
      messages: [
        { type: "user", text: trimmed },
        { type: "assistant", text: `Conversation log exported to:\n${exportPath}` },
      ],
    };
  }

  if (localCommand === "resume_campaign") {
    const campaigns = listCampaigns(projectDir);
    if (campaigns.length === 0) {
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: "No previous campaigns found in campaigns/ directory.\nStart a new campaign with /campaign or describe your target." },
        ],
      };
    }
    const lines = [
      "  Previous Campaigns\n",
      ...campaigns.flatMap((c, i) => formatCampaignDetail(c, i + 1)),
      "",
      `  Select (1-${campaigns.length}) or /campaign for new:`,
    ];
    return {
      handled: true,
      messages: [
        { type: "user", text: trimmed },
        { type: "assistant", text: lines.join("\n") },
      ],
    };
  }

  if (localCommand === "compare_rounds") {
    if (!campaignDir) {
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: "No active campaign. Start one with /campaign first." },
        ],
      };
    }
    const logPath = resolve(campaignDir, "campaign_log.json");
    if (!existsSync(logPath)) {
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: "Campaign log not found. Start a campaign with /campaign first." },
        ],
      };
    }
    try {
      const log = JSON.parse(readFileSync(logPath, "utf-8")) as {
        rounds?: Array<{
          round_id: number;
          parameters?: { scaffolds?: string[] };
          runs?: Array<{
            scaffold?: string;
            designs_generated?: number;
            designs_passed?: number;
            designs_requested?: number;
            top_iptm?: number;
            top_ipsae?: number;
            status?: string;
          }>;
        }>;
      };
      const rounds = log.rounds ?? [];
      if (rounds.length < 2) {
        return {
          handled: true,
          messages: [
            { type: "user", text: trimmed },
            { type: "assistant", text: "Only 1 round \u2014 nothing to compare yet" },
          ],
        };
      }

      const fmt = (n: number): string => n.toLocaleString("en-US");
      const delta = (a: number, b: number, decimals?: number): string => {
        const d = b - a;
        if (decimals !== undefined) {
          const sign = d > 0 ? "+" : d < 0 ? "" : "";
          return sign + d.toFixed(decimals);
        }
        const sign = d > 0 ? "+" : d < 0 ? "" : "";
        return sign + fmt(d);
      };

      interface RoundAgg {
        roundId: number;
        generated: number;
        passed: number;
        topIpsae: number;
        topIptm: number;
        scaffolds: Map<string, { passed: number; requested: number; status: string }>;
      }
      const aggs: RoundAgg[] = rounds.map((r) => {
        const agg: RoundAgg = {
          roundId: r.round_id,
          generated: 0,
          passed: 0,
          topIpsae: 0,
          topIptm: 0,
          scaffolds: new Map(),
        };
        for (const run of r.runs ?? []) {
          agg.generated += run.designs_generated ?? 0;
          agg.passed += run.designs_passed ?? 0;
          if ((run.top_ipsae ?? 0) > agg.topIpsae) agg.topIpsae = run.top_ipsae ?? 0;
          if ((run.top_iptm ?? 0) > agg.topIptm) agg.topIptm = run.top_iptm ?? 0;
          if (run.scaffold) {
            agg.scaffolds.set(run.scaffold, {
              passed: run.designs_passed ?? 0,
              requested: run.designs_requested ?? run.designs_generated ?? 0,
              status: run.status ?? "unknown",
            });
          }
        }
        return agg;
      });

      const prev = aggs[aggs.length - 2];
      const curr = aggs[aggs.length - 1];
      const prevRate = prev.generated > 0 ? (prev.passed / prev.generated) * 100 : 0;
      const currRate = curr.generated > 0 ? (curr.passed / curr.generated) * 100 : 0;
      const prevScaffoldCount = prev.scaffolds.size;
      const currScaffoldCount = curr.scaffolds.size;

      const pad = (s: string, len: number): string => s.padEnd(len);
      const rpad = (s: string, len: number): string => s.padStart(len);

      const metricCol = 22;
      const valCol = 14;

      const lines: string[] = [
        "Round Comparison",
        "",
        `  ${pad("Metric", metricCol)}${rpad(`Round ${prev.roundId}`, valCol)}${rpad(`Round ${curr.roundId}`, valCol)}${rpad("Delta", valCol)}`,
        `  ${"─".repeat(metricCol + valCol * 3)}`,
        `  ${pad("Designs generated", metricCol)}${rpad(fmt(prev.generated), valCol)}${rpad(fmt(curr.generated), valCol)}${rpad(delta(prev.generated, curr.generated), valCol)}`,
        `  ${pad("Designs passed", metricCol)}${rpad(fmt(prev.passed), valCol)}${rpad(fmt(curr.passed), valCol)}${rpad(delta(prev.passed, curr.passed), valCol)}`,
        `  ${pad("Pass rate", metricCol)}${rpad(prevRate.toFixed(1) + "%", valCol)}${rpad(currRate.toFixed(1) + "%", valCol)}${rpad(delta(prevRate, currRate, 1) + "%", valCol)}`,
        `  ${pad("Top ipSAE", metricCol)}${rpad(prev.topIpsae.toFixed(2), valCol)}${rpad(curr.topIpsae.toFixed(2), valCol)}${rpad(delta(prev.topIpsae, curr.topIpsae, 2), valCol)}`,
        `  ${pad("Top ipTM", metricCol)}${rpad(prev.topIptm.toFixed(2), valCol)}${rpad(curr.topIptm.toFixed(2), valCol)}${rpad(delta(prev.topIptm, curr.topIptm, 2), valCol)}`,
        `  ${pad("Scaffolds", metricCol)}${rpad(String(prevScaffoldCount), valCol)}${rpad(String(currScaffoldCount), valCol)}${rpad(delta(prevScaffoldCount, currScaffoldCount), valCol)}`,
      ];

      const allScaffoldNames = new Set<string>();
      prev.scaffolds.forEach((_, k) => allScaffoldNames.add(k));
      curr.scaffolds.forEach((_, k) => allScaffoldNames.add(k));

      if (allScaffoldNames.size > 0) {
        lines.push("");
        lines.push("Per-Scaffold:");
        for (const name of allScaffoldNames) {
          const pScaf = prev.scaffolds.get(name);
          const cScaf = curr.scaffolds.get(name);
          const pLabel = pScaf ? `${pScaf.passed}/${pScaf.requested}` : "—";
          const cLabel = cScaf ? `${cScaf.passed}/${cScaf.requested}` : "dropped";
          let dLabel: string;
          if (pScaf && cScaf) {
            const d = cScaf.passed - pScaf.passed;
            dLabel = d === 0 ? "=" : (d > 0 ? `+${d}` : String(d));
          } else if (!pScaf && cScaf) {
            dLabel = "new";
          } else {
            dLabel = "\u2014";
          }
          lines.push(
            `  ${pad(name, metricCol)}${rpad(pLabel, valCol)}${rpad(cLabel, valCol)}${rpad(dLabel, valCol)}`
          );
        }
      }

      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: lines.join("\n") },
        ],
      };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "error", text: `Failed to read campaign log: ${msg}` },
        ],
      };
    }
  }

  if (localCommand === "show_campaign") {
    // Check for an active campaign
    const activePath = resolve(projectDir, ".proteus", "active-campaign.json");
    if (!existsSync(activePath)) {
      // No active campaign — check campaigns/ for any existing ones
      const campaigns = listCampaigns(projectDir);
      if (campaigns.length > 0) {
        const lines = [
          "No active campaign.",
          "",
          "  Previous campaigns found:",
          "",
          ...campaigns.slice(0, 5).flatMap((c, i) => formatCampaignDetail(c, i + 1)),
          "",
          "  Use /resume to load one, or describe what you want to design to start fresh.",
        ];
        return {
          handled: true,
          messages: [
            { type: "user", text: trimmed },
            { type: "assistant", text: lines.join("\n") },
          ],
        };
      }
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: "No active campaign. Describe what you want to design to start one." },
        ],
      };
    }

    // Active campaign exists — show detailed status
    try {
      const active = JSON.parse(readFileSync(activePath, "utf-8"));
      const dir = active.campaignDir;
      if (!dir) {
        return {
          handled: true,
          messages: [
            { type: "user", text: trimmed },
            { type: "assistant", text: "Active campaign reference found but campaign directory is missing." },
          ],
        };
      }

      const logPath = resolve(dir, "campaign_log.json");
      if (!existsSync(logPath)) {
        return {
          handled: true,
          messages: [
            { type: "user", text: trimmed },
            { type: "assistant", text: `Campaign directory: ${dir}\nCampaign log not found yet. The campaign may still be initializing.` },
          ],
        };
      }

      const log = JSON.parse(readFileSync(logPath, "utf-8")) as CampaignLog;
      const targetName = log.target?.name ?? "Unknown target";
      const pdbId = log.target?.pdb_id ?? "";
      const status = log.status ?? "unknown";
      const roundCount = log.rounds?.length ?? 0;
      const currentRound = roundCount > 0 ? log.rounds[roundCount - 1] : null;
      const cost = estimateCampaignCost(log);
      const nextAction = inferNextAction(log);

      const lines: string[] = [
        "Campaign Status",
        "",
        `  Campaign     ${log.campaign_id}`,
        `  Target       ${targetName}${pdbId ? ` (${pdbId})` : ""}`,
        `  Status       ${status}`,
        `  Round        ${roundCount > 0 ? `${roundCount}` : "none"}`,
        `  Cost         ${cost}`,
      ];

      if (currentRound) {
        const totalGenerated = currentRound.runs.reduce((s, r) => s + (r.designs_generated || 0), 0);
        const totalPassed = currentRound.runs.reduce((s, r) => s + (r.designs_passed || 0), 0);
        lines.push(`  Generated    ${totalGenerated.toLocaleString()}`);
        lines.push(`  Passed       ${totalPassed.toLocaleString()}`);

        const topIpsae = Math.max(0, ...currentRound.runs.map(r => r.top_ipsae || 0));
        const topIptm = Math.max(0, ...currentRound.runs.map(r => r.top_iptm || 0));
        if (topIpsae > 0) lines.push(`  Top ipSAE    ${topIpsae.toFixed(2)}`);
        if (topIptm > 0) lines.push(`  Top ipTM     ${topIptm.toFixed(2)}`);
      }

      lines.push("");
      lines.push(`  Next: ${nextAction}`);

      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "assistant", text: lines.join("\n") },
        ],
      };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        handled: true,
        messages: [
          { type: "user", text: trimmed },
          { type: "error", text: `Failed to read campaign status: ${msg}` },
        ],
      };
    }
  }

  if (localCommand === "view_structure") {
    return {
      handled: true,
      messages: [
        { type: "user", text: trimmed },
        { type: "assistant", text: "Structure viewer not yet implemented. Use Mol* or PyMOL externally." },
      ],
    };
  }

  return { handled: false };
}
