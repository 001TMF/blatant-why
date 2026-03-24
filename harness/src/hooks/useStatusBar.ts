/**
 * useStatusBar — manages the raw ANSI status bar at bottom of terminal.
 * Computes the props for <StatusBar> from campaign and provider state.
 */

import { useState, useEffect, useCallback } from "react";

export interface StatusBarState {
  campaignName?: string;
  provider?: string;
  model?: string;
}

export interface UseStatusBarOptions {
  projectDir: string;
  model?: string;
}

export function useStatusBar(options: UseStatusBarOptions): StatusBarState {
  const [state, setState] = useState<StatusBarState>({
    model: options.model,
  });

  // Detect provider from environment
  useEffect(() => {
    const providers: string[] = [];
    if (process.env.TAMARIND_API_KEY) providers.push("Tamarind");
    if (process.env.LEVITATE_CLIENT_ID) providers.push("Levitate");
    if (
      process.env.PROTEUS_FOLD_DIR ||
      process.env.PROTEUS_PROT_DIR ||
      process.env.PROTEUS_AB_DIR
    ) {
      providers.push("Local GPU");
    }
    const provider = providers.length > 0 ? providers.join(" + ") : "No provider";

    setState((prev) => ({ ...prev, provider }));
  }, []);

  // Update model when option changes
  useEffect(() => {
    setState((prev) => ({ ...prev, model: options.model }));
  }, [options.model]);

  const setCampaignName = useCallback((name: string | undefined) => {
    setState((prev) => ({ ...prev, campaignName: name }));
  }, []);

  return state;
}
