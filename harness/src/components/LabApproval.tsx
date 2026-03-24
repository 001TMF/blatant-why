import React, { useState } from "react";
import { Box, Text } from "ink";
import TextInput from "ink-text-input";
import { theme, ICONS } from "../lib/theme.js";

export interface LabApprovalProps {
  campaignName: string;
  designCount: number;
  estimatedCost: string;
  provider: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const CONFIRM_WORD = "CONFIRM";

/**
 * Lab submission gate with WARNING banner and confirmation input.
 * User must type "CONFIRM" to proceed with lab submission.
 */
export function LabApproval({
  campaignName,
  designCount,
  estimatedCost,
  provider,
  onConfirm,
  onCancel,
}: LabApprovalProps) {
  const [input, setInput] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (value: string) => {
    if (value.trim() === CONFIRM_WORD) {
      onConfirm();
    } else if (value.trim().toLowerCase() === "cancel" || value.trim().toLowerCase() === "no") {
      onCancel();
    } else {
      setError(`Type "${CONFIRM_WORD}" to proceed or "cancel" to abort.`);
      setInput("");
    }
  };

  return (
    <Box flexDirection="column" marginTop={1} marginBottom={1}>
      <Box marginBottom={1}>
        <Text color={theme.hex.warning} bold>
          {ICONS.warning} WARNING: Lab Submission Gate
        </Text>
      </Box>

      <Box flexDirection="column" marginBottom={1}>
        <Text color={theme.hex.body}>
          You are about to submit designs to a physical laboratory.
        </Text>
        <Text color={theme.hex.body}>This will incur real costs and cannot be undone.</Text>
      </Box>

      <Box flexDirection="column" marginBottom={1}>
        <Text>
          <Text color={theme.hex.dim}>  Campaign:  </Text>
          <Text color={theme.hex.white}>{campaignName}</Text>
        </Text>
        <Text>
          <Text color={theme.hex.dim}>  Designs:   </Text>
          <Text color={theme.hex.white}>{designCount}</Text>
        </Text>
        <Text>
          <Text color={theme.hex.dim}>  Est. Cost: </Text>
          <Text color={theme.hex.warning}>{estimatedCost}</Text>
        </Text>
        <Text>
          <Text color={theme.hex.dim}>  Provider:  </Text>
          <Text color={theme.hex.white}>{provider}</Text>
        </Text>
      </Box>

      <Box marginBottom={1}>
        <Text color={theme.hex.warning}>
          Type "{CONFIRM_WORD}" to submit, or "cancel" to abort:
        </Text>
      </Box>

      {error ? (
        <Box marginBottom={1}>
          <Text color={theme.hex.error}>{ICONS.error} {error}</Text>
        </Box>
      ) : null}

      <Box>
        <Text color={theme.hex.warning}>{ICONS.prompt} </Text>
        <TextInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          focus={true}
        />
      </Box>
    </Box>
  );
}
