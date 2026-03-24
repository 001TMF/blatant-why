import React from "react";
import { Static } from "ink";
import { Message } from "./Message.js";
import type { MessageData } from "./Message.js";

export interface MessageListProps {
  messages: MessageData[];
}

/**
 * Thin wrapper around Ink <Static> that maps messages to Message components.
 * Static items are rendered once and then scroll off the visible area.
 */
export function MessageList({ messages }: MessageListProps) {
  return (
    <Static items={messages}>
      {(msg) => <Message key={msg.id} message={msg} />}
    </Static>
  );
}
