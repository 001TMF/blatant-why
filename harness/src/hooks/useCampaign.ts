/**
 * useCampaign — polls .proteus/active-campaign.json + campaign_log.json.
 * Returns campaign state or null if no active campaign.
 */

import { useState, useEffect } from "react";
import { readFileSync, existsSync } from "fs";
import { resolve } from "path";

export interface CampaignState {
  campaignId: string;
  name: string;
  phase: string;
  roundCount: number;
  designCount: number;
  costUsd: number;
  planApproved: boolean;
}

export interface UseCampaignOptions {
  projectDir: string;
  pollIntervalMs?: number;
}

export function useCampaign({
  projectDir,
  pollIntervalMs = 5000,
}: UseCampaignOptions): CampaignState | null {
  const [state, setState] = useState<CampaignState | null>(null);

  useEffect(() => {
    const poll = () => {
      const activePath = resolve(projectDir, ".proteus", "active-campaign.json");
      if (!existsSync(activePath)) {
        setState(null);
        return;
      }

      try {
        const active = JSON.parse(readFileSync(activePath, "utf-8"));
        const campaignDir = active.campaignDir as string | undefined;
        if (!campaignDir) {
          setState(null);
          return;
        }

        const logPath = resolve(campaignDir, "campaign_log.json");
        if (!existsSync(logPath)) {
          setState({
            campaignId: active.campaignId ?? "unknown",
            name: active.name ?? "Unnamed",
            phase: "planning",
            roundCount: 0,
            designCount: 0,
            costUsd: 0,
            planApproved: false,
          });
          return;
        }

        const log = JSON.parse(readFileSync(logPath, "utf-8"));
        const rounds = (log.rounds as unknown[]) ?? [];
        setState({
          campaignId: log.campaign_id ?? active.campaignId ?? "unknown",
          name: log.name ?? active.name ?? "Unnamed",
          phase: (log.status as string) ?? "planning",
          roundCount: rounds.length,
          designCount: (log.total_designs as number) ?? 0,
          costUsd: (log.total_cost_usd as number) ?? 0,
          planApproved: log.plan_approved === true,
        });
      } catch {
        setState(null);
      }
    };

    poll(); // immediate first check
    const timer = setInterval(poll, pollIntervalMs);
    return () => clearInterval(timer);
  }, [projectDir, pollIntervalMs]);

  return state;
}
