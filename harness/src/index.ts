import { render } from "ink";
import React from "react";
import { App } from "./app.js";
import { ProteusMode } from "./modes.js";
import { streamQuery, AgentConfig } from "./agent.js";

async function main() {
  let mode: ProteusMode = "binder";

  const config: AgentConfig = {
    projectDir: process.cwd(),
    mode,
    mcpServers: {},
  };

  async function* queryFn(input: string): AsyncGenerator<string> {
    yield* streamQuery(input, config);
  }

  const handleModeChange = (newMode: ProteusMode) => {
    mode = newMode;
    config.mode = newMode;
  };

  const { unmount } = render(
    React.createElement(App, {
      queryFn,
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
