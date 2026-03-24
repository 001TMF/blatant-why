import React from "react";
import { Box, Text } from "ink";
import { theme, ICONS } from "../lib/theme.js";
import { Markdown } from "./Markdown.js";
import { Banner } from "./Banner.js";

export type MessageRole =
  | "user"
  | "assistant"
  | "tool_summary"
  | "subagent"
  | "error"
  | "system"
  | "banner";

export interface MessageData {
  id: string;
  role: MessageRole;
  content: string;
  /** For tool_summary: tool name */
  toolName?: string;
  /** For tool_summary: elapsed ms */
  elapsed?: number;
  /** For subagent: agent name */
  agentName?: string;
  timestamp?: number;
}

export function Message({ message }: { message: MessageData }) {
  switch (message.role) {
    case "user":
      return <UserMessage content={message.content} />;
    case "assistant":
      return <AssistantMessage content={message.content} />;
    case "tool_summary":
      return (
        <ToolSummaryMessage
          toolName={message.toolName ?? "tool"}
          elapsed={message.elapsed}
          content={message.content}
        />
      );
    case "subagent":
      return (
        <SubAgentMessage
          agentName={message.agentName ?? "Agent"}
          content={message.content}
        />
      );
    case "error":
      return <ErrorMessage content={message.content} />;
    case "system":
      return <SystemMessage content={message.content} />;
    case "banner":
      return <Banner forename={message.content} />;
    default:
      return null;
  }
}

function UserMessage({ content }: { content: string }) {
  return (
    <Box marginTop={1} marginBottom={1}>
      <Text>
        <Text color={theme.hex.accent} bold>
          {ICONS.prompt}{" "}
        </Text>
        <Text color={theme.hex.white}>{content}</Text>
      </Text>
    </Box>
  );
}

function AssistantMessage({ content }: { content: string }) {
  return (
    <Box marginBottom={1} flexDirection="column">
      <Markdown text={content} />
    </Box>
  );
}

function ToolSummaryMessage({
  toolName,
  elapsed,
  content,
}: {
  toolName: string;
  elapsed?: number;
  content: string;
}) {
  const elapsedStr = elapsed != null ? `${(elapsed / 1000).toFixed(1)}s` : "";
  return (
    <Box>
      <Text>
        <Text color={theme.hex.success}>{ICONS.success} </Text>
        <Text color={theme.hex.dim}>{toolName}</Text>
        {elapsedStr ? (
          <Text color={theme.hex.dim}> ({elapsedStr})</Text>
        ) : null}
        {content ? <Text color={theme.hex.dim}> — {content}</Text> : null}
      </Text>
    </Box>
  );
}

function SubAgentMessage({
  agentName,
  content,
}: {
  agentName: string;
  content: string;
}) {
  return (
    <Box>
      <Text>
        <Text color={theme.hex.muted}>
          {ICONS.bullet} {agentName}
        </Text>
        <Text color={theme.hex.body}> — {content}</Text>
      </Text>
    </Box>
  );
}

function ErrorMessage({ content }: { content: string }) {
  return (
    <Box marginTop={1} marginBottom={1}>
      <Text>
        <Text color={theme.hex.error}>
          {ICONS.error} Error:{" "}
        </Text>
        <Text color={theme.hex.body}>{content}</Text>
      </Text>
    </Box>
  );
}

function SystemMessage({ content }: { content: string }) {
  return (
    <Box>
      <Text dimColor>{content}</Text>
    </Box>
  );
}
