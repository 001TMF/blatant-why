import { useState, useEffect } from "react";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

interface CampaignStateHook {
  state: Record<string, unknown> | null;
  phase: string;
  isActive: boolean;
  campaignDir: string | null;
}

export function useCampaignState(projectDir: string, pollMs: number = 2000): CampaignStateHook {
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [campaignDir, setCampaignDir] = useState<string | null>(null);

  useEffect(() => {
    const check = () => {
      const activePath = resolve(projectDir, ".proteus", "active-campaign.json");
      if (!existsSync(activePath)) {
        setState(null);
        setCampaignDir(null);
        return;
      }
      try {
        const active = JSON.parse(readFileSync(activePath, "utf-8"));
        setCampaignDir(active.campaignDir ?? null);
        if (active.campaignDir) {
          const logPath = resolve(active.campaignDir, "campaign_log.json");
          if (existsSync(logPath)) {
            setState(JSON.parse(readFileSync(logPath, "utf-8")));
          }
        }
      } catch { /* silent */ }
    };

    check();
    const interval = setInterval(check, pollMs);
    return () => clearInterval(interval);
  }, [projectDir, pollMs]);

  return {
    state,
    phase: (state as Record<string, unknown> | null)?.status as string ?? "inactive",
    isActive: state !== null,
    campaignDir,
  };
}
