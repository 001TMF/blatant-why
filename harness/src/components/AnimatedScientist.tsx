import React, { useState, useEffect } from "react";
import { Text } from "ink";
import { theme } from "../theme.js";

// ---------------------------------------------------------------------------
// Animated braille pixel-art scientist for the Proteus banner.
//
// Each Unicode braille character (U+2800..U+28FF) encodes a 2x4 pixel grid:
//
//   Dot 1 (0x01)  Dot 4 (0x08)
//   Dot 2 (0x02)  Dot 5 (0x10)
//   Dot 3 (0x04)  Dot 6 (0x20)
//   Dot 7 (0x40)  Dot 8 (0x80)
//
// Character is ~8 braille chars wide (16 px) x 7 lines tall (28 px).
// Depicts a scientist in a lab coat with glasses, holding a flask.
// Four frames cycle through: standing, raising flask, examining, eureka.
// ---------------------------------------------------------------------------

const FRAMES: string[][] = [
  // Frame 0 — Standing, flask at side (right hand low)
  [
    "⠀⠀⢀⣴⣾⣷⣄⠀⠀",
    "⠀⠀⢸⣎⣉⣱⡇⠀⠀",
    "⠀⣠⣾⣿⣿⣿⣷⣄⠀",
    "⠀⠈⠻⣿⣿⣿⠟⢀⠀",
    "⠀⠀⠀⣿⣿⡇⠀⡼⠀",
    "⠀⠀⢰⠇⠸⡇⠈⠁⠀",
    "⠀⠀⠘⠀⠀⠃⠀⠀⠀",
  ],
  // Frame 1 — Raising flask (right arm up, flask elevated)
  [
    "⠀⠀⢀⣴⣾⣷⣄⣠⠀",
    "⠀⠀⢸⣎⣉⣱⣿⡏⠀",
    "⠀⣠⣾⣿⣿⣿⠟⠀⠀",
    "⠀⠈⠻⣿⣿⣿⠃⠀⠀",
    "⠀⠀⠀⣿⣿⡇⠀⠀⠀",
    "⠀⠀⢰⠇⠸⡇⠀⠀⠀",
    "⠀⠀⠘⠀⠀⠃⠀⠀⠀",
  ],
  // Frame 2 — Examining flask (both arms mid, flask in front)
  [
    "⠀⠀⢀⣴⣾⣷⣄⠀⠀",
    "⠀⠀⢸⣎⣉⣱⡇⠀⠀",
    "⠀⣠⣾⣿⣿⣿⣿⣆⠀",
    "⠀⡿⠻⣿⣿⣿⠟⡿⠀",
    "⠀⠀⠀⣿⣿⡇⠀⠀⠀",
    "⠀⠀⢰⠇⠸⡇⠀⠀⠀",
    "⠀⠀⠘⠀⠀⠃⠀⠀⠀",
  ],
  // Frame 3 — Eureka! (both arms raised)
  [
    "⠀⡀⢀⣴⣾⣷⣄⢀⠀",
    "⠀⠑⢸⣎⣉⣱⡇⠊⠀",
    "⠀⠀⣾⣿⣿⣿⣷⠀⠀",
    "⠀⠀⠻⣿⣿⣿⠟⠀⠀",
    "⠀⠀⠀⣿⣿⡇⠀⠀⠀",
    "⠀⠀⢰⠇⠸⡇⠀⠀⠀",
    "⠀⠀⠘⠀⠀⠃⠀⠀⠀",
  ],
];

interface Props {
  /** Whether to animate. When false, shows frame 0 only. */
  animating?: boolean;
  /** Milliseconds between frames. */
  intervalMs?: number;
}

/**
 * A small animated braille-art scientist character.
 * Designed to sit to the left of the PROTEUS ASCII banner.
 */
export function AnimatedScientist({ animating = true, intervalMs = 1000 }: Props) {
  const [frameIndex, setFrameIndex] = useState(0);

  useEffect(() => {
    if (!animating) return;
    const interval = setInterval(() => {
      setFrameIndex((prev) => (prev + 1) % FRAMES.length);
    }, intervalMs);
    return () => clearInterval(interval);
  }, [animating, intervalMs]);

  const frame = FRAMES[frameIndex];

  return (
    <Text color={theme.hex.primary}>
      {frame.join("\n")}
    </Text>
  );
}
