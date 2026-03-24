import React, { useRef } from "react";
import { Static } from "ink";
import { Message } from "./Message.js";
import type { MessageData } from "./Message.js";

export interface MessageListProps {
  messages: MessageData[];
}

/**
 * Wrapper around Ink <Static> with a STABLE append-only array.
 *
 * Ink's <Static> only renders NEW items (by tracking array length).
 * We maintain a ref-based array that only grows, appending new messages
 * synchronously during render so <Static> sees them on the first paint.
 */
export function MessageList({ messages }: MessageListProps) {
  const stableRef = useRef<MessageData[]>([]);
  const seenIds = useRef<Set<string>>(new Set());
  const [, setTick] = React.useState(0);

  // Append new messages synchronously (before JSX return)
  // so <Static> has items available on first render.
  let added = false;
  for (const msg of messages) {
    if (!seenIds.current.has(msg.id)) {
      seenIds.current.add(msg.id);
      stableRef.current.push(msg);
      added = true;
    }
  }

  // Schedule re-render if new items were added (for subsequent updates)
  if (added) {
    // Use queueMicrotask to avoid setState-during-render warning
    queueMicrotask(() => setTick((t) => t + 1));
  }

  return (
    <Static items={stableRef.current}>
      {(msg) => <Message key={msg.id} message={msg} />}
    </Static>
  );
}
