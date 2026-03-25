---
name: by:view
description: View a protein structure in ProteinView (opens tmux split pane)
argument-hint: "<PDB ID, file path, or design name>"
---

# /view — View Protein Structure

Open a protein structure in ProteinView in a tmux split pane with FullHD rendering.

## Instructions

### Step 1: Resolve the input

The argument can be:
- **PDB ID** (4 chars, e.g., `3DPL`) — fetch from RCSB
- **File path** (e.g., `.by/campaigns/.../design_003.cif`) — open directly
- **Design name** (e.g., `design_003`) — search active campaign for matching CIF/PDB file

If a design name is given, find the file:
```bash
CAMPAIGN_DIR=$(cat .by/active_campaign 2>/dev/null)
FILE=$(find "$CAMPAIGN_DIR" -name "*${DESIGN_NAME}*.cif" -o -name "*${DESIGN_NAME}*.pdb" 2>/dev/null | head -1)
```

### Step 2: Determine color scheme

Pick color based on context:
- If viewing a design with confidence data → `--color plddt`
- If viewing a multi-chain complex → `--color chain`
- If viewing a target structure → `--color structure`
- Default → `--color chain`

### Step 3: Open in tmux split

```bash
tmux split-window -h "proteinview '${FILE_OR_PDB}' --fullhd --color ${COLOR}; read -p 'Press Enter to close'"
```

If the input is a PDB ID (no file):
```bash
tmux split-window -h "proteinview --fetch ${PDB_ID} --fullhd --color ${COLOR}; read -p 'Press Enter to close'"
```

### Step 4: Confirm to user

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 BY ► VIEWING: {name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Opened in tmux split pane (FullHD mode).
Color: {color scheme}
File: {path or PDB ID}

Controls: arrow keys to rotate, +/- to zoom, q to quit
```

### Error handling

- If `proteinview` not found: `cargo install proteinview` or download from GitHub
- If not in tmux: show the command for the user to run manually
- If file not found: list available structure files in the campaign
