---
description: Watch live pipeline progress for a design run
arguments:
  - name: run_id
    description: The run identifier to watch
    required: true
---

Watch the live progress of design run `$ARGUMENTS`. Use the by-tools MCP server to check the current status and display the pipeline stages with progress indicators.

Show the pipeline progress display with:
- Current stage (marked with green dot ●)
- Completed stages (marked with ✓)
- Pending stages (marked with ○)
- Design count progress (X/Y designs)
- Elapsed time

Update every 30 seconds until complete. Report final results when done.
