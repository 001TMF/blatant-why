/**
 * useAgent — core hook wrapping streamQuery.
 *
 * Manages messages, streaming text, tool log, loading state.
 */

import { useState, useCallback, useRef } from "react";
import { streamQuery } from "../agent.js";
import type { AgentConfig, StreamEvent } from "../agent.js";
import type { MessageData } from "../components/Message.js";
import type { ToolEntry } from "../components/ToolActivity.js";
import { humanizeToolName } from "../lib/toolNames.js";
import { friendlyError } from "../lib/errors.js";

export interface UseAgentOptions {
  projectDir: string;
  model?: string;
  maxTurns?: number;
  appendSystemPrompt?: string;
}

export interface UseAgentReturn {
  messages: MessageData[];
  streamingText: string;
  toolLog: ToolEntry[];
  loading: boolean;
  sessionId: string | null;
  activeTool: ToolEntry | null;
  costUsd: number;
  submit: (prompt: string) => void;
  cancel: () => void;
}

let messageCounter = 0;
function nextId(): string {
  return `msg_${++messageCounter}_${Date.now()}`;
}

export function useAgent(options: UseAgentOptions): UseAgentReturn {
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [toolLog, setToolLog] = useState<ToolEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<ToolEntry | null>(null);
  const [costUsd, setCostUsd] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const streamTextRef = useRef("");

  const submit = useCallback(
    (prompt: string) => {
      if (loading) return;

      // Add user message
      const userMsg: MessageData = {
        id: nextId(),
        role: "user",
        content: prompt,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStreamingText("");
      streamTextRef.current = "";
      setLoading(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const config: AgentConfig = {
        projectDir: options.projectDir,
        model: options.model,
        maxTurns: options.maxTurns,
        appendSystemPrompt: options.appendSystemPrompt,
        abortController: controller,
        resume: sessionId ?? undefined,
      };

      // Run the stream in a microtask
      (async () => {
        try {
          for await (const event of streamQuery(prompt, config)) {
            if (controller.signal.aborted) break;
            handleEvent(event);
          }
        } catch {
          // Stream errors are handled within streamQuery
        } finally {
          // Flush any remaining streaming text as an assistant message
          if (streamTextRef.current.trim()) {
            const assistantMsg: MessageData = {
              id: nextId(),
              role: "assistant",
              content: streamTextRef.current.trim(),
              timestamp: Date.now(),
            };
            setMessages((prev) => [...prev, assistantMsg]);
          }
          setStreamingText("");
          streamTextRef.current = "";
          setLoading(false);
          setActiveTool(null);
          abortRef.current = null;
        }
      })();
    },
    [loading, options, sessionId],
  );

  const handleEvent = useCallback((event: StreamEvent) => {
    switch (event.type) {
      case "system_init": {
        setSessionId(event.data.session_id);
        break;
      }

      case "text_delta": {
        streamTextRef.current += event.text;
        setStreamingText(streamTextRef.current);
        break;
      }

      case "tool_start": {
        // Flush streaming text before tool
        if (streamTextRef.current.trim()) {
          const assistantMsg: MessageData = {
            id: nextId(),
            role: "assistant",
            content: streamTextRef.current.trim(),
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          streamTextRef.current = "";
          setStreamingText("");
        }

        const entry: ToolEntry = {
          toolUseId: event.toolUseId,
          toolName: event.toolName,
          startedAt: Date.now(),
        };
        setToolLog((prev) => [...prev, entry]);
        setActiveTool(entry);
        break;
      }

      case "tool_end": {
        setToolLog((prev) =>
          prev.map((t) =>
            !t.completedAt
              ? { ...t, completedAt: Date.now() }
              : t,
          ),
        );
        setActiveTool(null);
        break;
      }

      case "result": {
        setCostUsd((prev) => prev + event.costUsd);
        break;
      }

      case "error": {
        const friendly = friendlyError(event.message);
        if (friendly) {
          const errMsg: MessageData = {
            id: nextId(),
            role: "error",
            content: friendly,
            timestamp: Date.now(),
          };
          setMessages((prev) => [...prev, errMsg]);
        }
        break;
      }
    }
  }, []);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  return {
    messages,
    streamingText,
    toolLog,
    loading,
    sessionId,
    activeTool,
    costUsd,
    submit,
    cancel,
  };
}
