---
name: by:set-profile
description: Switch model profile (quality/balanced/budget)
argument-hint: "<quality|balanced|budget>"
---

# /set-profile — Switch Model Profile

Change the model profile used for spawning agents. This controls which
Claude model each agent type uses, trading cost for capability.

## Instructions

This command does NOT spawn agents. It reads and writes config directly.

### Step 1: Validate argument

The argument must be one of: `quality`, `balanced`, `budget`.

If missing or invalid, show usage:
```
Usage: /by:set-profile <quality|balanced|budget>

Profiles control which models are used for each agent:
  quality  — Best results, highest cost (Opus for most agents)
  balanced — Good results, moderate cost (Sonnet for most agents)
  budget   — Fast iteration, lowest cost (Haiku where possible)
```

### Step 2: Read current config

```bash
CONFIG_FILE=".by/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
  mkdir -p .by
  echo '{"model_profile": "balanced"}' > "$CONFIG_FILE"
fi
```

Read the current config file.

### Step 3: Update profile

Write the new model_profile value to `.by/config.json`, preserving
any other fields in the config.

### Step 4: Display profile table

Show the complete model assignment table for the selected profile:

```
Model Profile: {selected}

Agent                      quality     balanced    budget
-------------------------  ----------  ----------  ----------
by-research                opus        sonnet      sonnet
by-design                  opus        sonnet      sonnet
by-screening               sonnet      sonnet      haiku
by-campaign                opus        opus        sonnet
by-knowledge               sonnet      haiku       haiku
by-verifier                sonnet      sonnet      sonnet
by-plan-checker            sonnet      sonnet      haiku
by-environment             sonnet      sonnet      haiku
by-lab                     opus        opus        sonnet
by-evaluator               opus        sonnet      sonnet
by-visualization           sonnet      sonnet      haiku
by-diversity               sonnet      sonnet      haiku
by-epitope                 opus        sonnet      sonnet
by-humanization            opus        sonnet      haiku
by-liability-engineer      sonnet      sonnet      haiku
by-formatter               sonnet      haiku       haiku
```

Highlight the active column.

### Step 5: Confirm

Report: "Profile switched to **{selected}**. All future agent spawns
will use the models shown above."
