import React, { useState, useEffect } from "react";
import { Box, Text, useInput } from "ink";

interface ScrollableOutputProps {
  children: React.ReactNode[];
  height?: number;
}

export function ScrollableOutput({ children, height = 20 }: ScrollableOutputProps) {
  const totalItems = React.Children.count(children);
  const [scrollOffset, setScrollOffset] = useState(0);

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    const maxOffset = Math.max(0, totalItems - height);
    setScrollOffset(maxOffset);
  }, [totalItems, height]);

  useInput((input, key) => {
    if (key.upArrow) {
      setScrollOffset((prev) => Math.max(0, prev - 1));
    } else if (key.downArrow) {
      setScrollOffset((prev) => Math.min(Math.max(0, totalItems - height), prev + 1));
    } else if (key.pageUp) {
      setScrollOffset((prev) => Math.max(0, prev - height));
    } else if (key.pageDown) {
      setScrollOffset((prev) => Math.min(Math.max(0, totalItems - height), prev + height));
    }
  });

  const childArray = React.Children.toArray(children);
  const visibleChildren = childArray.slice(scrollOffset, scrollOffset + height);

  const canScrollUp = scrollOffset > 0;
  const canScrollDown = scrollOffset < totalItems - height;

  return (
    <Box flexDirection="column">
      {canScrollUp && (
        <Text color="#606060">  ▲ {scrollOffset} more above</Text>
      )}
      {visibleChildren}
      {canScrollDown && (
        <Text color="#606060">  ▼ {totalItems - scrollOffset - height} more below</Text>
      )}
    </Box>
  );
}
