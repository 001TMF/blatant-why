import { render } from "ink";
import React from "react";
import { App } from "./app.js";
import { ProteusMode } from "./modes.js";
import { streamQuery, AgentConfig } from "./agent.js";
import { renderBanner } from "./banner.js";

// Print banner immediately
console.log(renderBanner("Binder Designer"));
console.log();

async function main() {
  let mode: ProteusMode = "binder";
  const output: string[] = [];

  const config: AgentConfig = {
    projectDir: process.cwd(),
    mode,
    mcpServers: {},
  };

  const handleSubmit = async (input: string) => {
    output.push(`> ${input}`);
    try {
      for await (const chunk of streamQuery(input, config)) {
        output.push(chunk);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      output.push(`Error: ${msg}`);
    }
  };

  const handleModeChange = (newMode: ProteusMode) => {
    mode = newMode;
    config.mode = newMode;
  };

  const { unmount } = render(
    React.createElement(App, {
      onSubmit: handleSubmit,
      output,
      mode,
      onModeChange: handleModeChange,
    })
  );

  // Keep process alive
  process.on("SIGINT", () => {
    unmount();
    process.exit(0);
  });
}

main().catch(console.error);
