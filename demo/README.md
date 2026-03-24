# BY Demo — VHH Nanobody Design Against RBX1

45-second demo video storyboard and runner script for the BY (Blatant-Why) campaign orchestrator.

## Storyboard (45 seconds)

```
0-5s:   Terminal opens. Run `npx by-design init --skip-keys`
        -> Files generated, "BY initialized" message

5-10s:  Run `claude` in the directory
        -> Claude Code opens with BY CLAUDE.md loaded

10-15s: Type: "Design VHH nanobodies against RBX1"
        -> Agent starts researching (cut here -- skip wait)

15-25s: [CUT TO] Research results appearing:
        -> UniProt: RBX1 (P62877), 108aa, RING domain E3 ligase
        -> PDB structures found (4P5O, etc.)
        -> SAbDab: no existing antibody binders
        -> Campaign plan table with parameters

25-30s: [CUT TO] User types "go"
        -> Design job submitted to Tamarind
        -> Pipeline progress showing

30-40s: [CUT TO] Results table:
        -> Ranked designs with ipSAE, ipTM, pLDDT, liabilities
        -> Top 3 candidates highlighted
        -> "3 designs pass all screening gates"

40-45s: [CUT TO] /by:results command showing final ranked table
        -> Diversity analysis
        -> "Ready for lab submission"
```

## Target: RBX1

- **UniProt**: P62877 (RBX1_HUMAN)
- **Function**: RING-box protein 1, E3 ubiquitin ligase component of Cullin-RING complexes
- **Size**: 108 amino acids
- **PDB**: 4P5O (CUL5-RBX1 complex), 1LDK (CUL1-RBX1), others
- **Significance**: Key component of ubiquitin-proteasome system; important for targeted protein degradation (PROTAC/molecular glue) research

## Running the Demo

```bash
# From the project root:
node demo/run_demo.mjs

# Output will be written to:
#   demo/output/demo_transcript.md   -- full conversation text
#   demo/output/tool_calls.json      -- all MCP tool calls with timing
```

**Warning**: A full run takes 10-15 minutes due to cloud compute jobs on Tamarind Bio. The script captures all output for post-production editing into the 45-second video.

## Requirements

- Node.js >= 18
- `@anthropic-ai/claude-code` SDK installed
- `.env` in project root with `TAMARIND_API_KEY` set
- MCP servers configured in `.claude/settings.json`

## Post-Production Notes

The raw transcript and tool calls are designed for editing. Key cut points:

1. **Research phase end**: Look for UniProt/PDB/SAbDab results in transcript
2. **Design submission**: Look for `tamarind_submit_job` in tool_calls.json
3. **Results table**: Look for the screening summary with ipSAE/ipTM columns
4. **Final ranking**: Look for diversity analysis and "ready for lab" message

Use a terminal recording tool (asciinema, VHS, or Screen Studio) and splice the real output at the storyboard cut points.
