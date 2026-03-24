import React from "react";
import { Text } from "ink";
import { theme } from "../theme.js";

const SPINNER_FRAMES = ["\u280B", "\u2819", "\u2839", "\u2838", "\u283C", "\u2834", "\u2826", "\u2827", "\u2807", "\u280F"];

interface SpinnerProps {
  label?: string;
}

export function Spinner({ label = "Thinking" }: SpinnerProps) {
  const [frame, setFrame] = React.useState(0);

  React.useEffect(() => {
    const timer = setInterval(() => {
      setFrame((prev) => (prev + 1) % SPINNER_FRAMES.length);
    }, 80);
    return () => clearInterval(timer);
  }, []);

  return (
    <Text color={theme.hex.primary}>
      {SPINNER_FRAMES[frame]} {label}...
    </Text>
  );
}
