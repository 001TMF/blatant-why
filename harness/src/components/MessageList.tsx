import React, { useRef, useEffect } from "react";
import { Static } from "ink";
import { Message } from "./Message.js";
import type { MessageData } from "./Message.js";

export interface MessageListProps {
  messages: MessageData[];
}

/**
 * Wrapper around Ink <Static> with a STABLE append-only array.
 *
 * Ink's <Static> re-renders everything when the array reference changes.
 * We maintain a ref-based array that only grows (never shrinks/rebuilds),
 * appending new messages by comparing IDs.
 */
export function MessageList({ messages }: MessageListProps) {
  const stableRef = useRef<MessageData[]>([]);
  const seenIds = useRef<Set<string>>(new Set());

  // Append only new messages to the stable array
  useEffect(() => {
    let added = false;
    for (const msg of messages) {
      if (!seenIds.current.has(msg.id)) {
        seenIds.current.add(msg.id);
        stableRef.current.push(msg);
        added = true;
      }
    }
    // Force re-render if new items were added
    if (added) setTick((t) => t + 1);
  }, [messages]);

  const [, setTick] = React.useState(0);

  return (
    <Static items={stableRef.current}>
      {(msg) => <Message key={msg.id} message={msg} />}
    </Static>
  );
}
