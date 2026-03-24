const WORDS = [
  "Thinking",
  "Reasoning",
  "Analyzing",
  "Researching",
  "Considering",
  "Evaluating",
  "Processing",
  "Examining",
  "Investigating",
  "Exploring",
];

let index = 0;

export function nextThinkingWord(): string {
  const word = WORDS[index % WORDS.length];
  index++;
  return word;
}

export function thinkingWordForTool(toolName: string): string {
  if (toolName.includes("search") || toolName.includes("fetch"))
    return "Searching";
  if (toolName.includes("screen") || toolName.includes("score"))
    return "Screening";
  if (toolName.includes("submit") || toolName.includes("run"))
    return "Submitting";
  if (toolName.includes("campaign")) return "Managing";
  if (toolName.includes("research")) return "Researching";
  if (toolName.includes("align") || toolName.includes("fold"))
    return "Folding";
  if (toolName.includes("export") || toolName.includes("download"))
    return "Exporting";
  return "Processing";
}
