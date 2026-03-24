# Frontend Rebuild — Status & Transition Document

## Branch: `frontend-rebuild` (off master)

## CRITICAL: Use an existing template harness

Before fixing bugs individually, research whether there's an existing Claude Code SDK harness/template we can build from. The official SDK has demo apps:
- **github.com/anthropics/claude-agent-sdk-demos** — includes Simple Chat App, Research Agent, etc.
- **github.com/anthropics/claude-code** — the actual Claude Code TUI source patterns
- Any community harness templates on npm/GitHub

The current rebuild was written from scratch and has fundamental Ink `<Static>` rendering issues. A proven template that already handles scrolling, streaming, tool calls, and Ctrl+C correctly would save days of debugging.

**First task next session: Research and evaluate existing harness templates before writing more code.**

## Branch: `frontend-rebuild` (off master)

## What's Done

### Architecture (correct, keep)
- Scrollback append model (no alternate screen)
- `<Static>` for completed messages
- Proper markdown via `marked` lexer + ANSI renderer
- Okabe-Ito colorblind-safe palette
- Tool activity panel with human-readable names
- StatusBar via raw ANSI (outside Ink tree)
- app.tsx under 200 lines (195)
- No mode toggle — context-aware modality

### Files (39 TypeScript files, ~3,890 lines)
- `src/lib/` — 9 modules (theme, markdown, toolNames, thinkingWords, errors, watchRun, conversationLog, proteinView, slashCommands)
- `src/components/` — 12 components
- `src/hooks/` — 5 hooks
- `src/agent.ts` — SDK wrapper
- `src/app.tsx` — thin orchestrator
- `src/index.ts` — entry point
- `src/agents/` — untouched backend (orchestrator, monitor, definitions, prompts)

### Backend (untouched, fully working)
- 11 MCP servers
- 15 skills
- 30 Python modules
- 128 tests passing
- Campaign state machine, scoring, screening, export all functional

---

## Known Bugs to Fix (Priority Order)

### BUG 1: Banner/content duplication (CRITICAL)
**Symptom**: BY banner and content re-renders every time user submits a message.
**Root cause**: Ink's `<Static>` re-renders all items when the items array reference changes. Even with the ref-based approach in `MessageList.tsx`, the component itself re-renders because React state changes trigger parent re-renders which recreate the items array.
**Attempted fixes**:
1. Moved banner inside Static items — still duplicates
2. Used useRef with append-only array — still duplicates
**Real fix needed**: The issue is likely that `useAgent` hook returns a new `messages` array on each state update, causing the `useEffect` in `MessageList` to re-run. Need to either:
- Use a proven harness template that already solves this
- Or bypass `<Static>` entirely and use `process.stdout.write` for the scrollback
- Or investigate if Ink v5 `<Static>` has a known bug with dynamic items

### BUG 2: Ctrl+C doesn't exit (CRITICAL)
**Symptom**: User can't quit the TUI. Should be double Ctrl+C like Claude Code (first cancels current operation, second exits).
**Root cause**: `index.ts` has `exitOnCtrlC: false` in the Ink render options. The SIGINT handler exists but may not be firing, or `useInput` is capturing it.
**Fix**: Implement double Ctrl+C pattern:
- First Ctrl+C: if agent is running, cancel the current operation (abort controller)
- Second Ctrl+C (within 2 seconds): exit the process
- Show "Press Ctrl+C again to exit" message after first press

### BUG 3: Content appears twice (raw + rendered)
**Symptom**: The assistant's response appears once as raw markdown (with `##`, `**`, `•`) and again as rendered text.
**Root cause**: The `useAgent` hook likely emits both `text_delta` events (which accumulate as streaming text) AND a final complete message. When the streaming text is flushed to `completedMessages` AND the SDK also emits a complete assistant message, the content doubles.
**Fix**: In `useAgent.ts`, when `text_complete` fires, DON'T add to completed messages if the same text was already streamed. Or: only add from the `result` event, not from streaming.

### BUG 4: Tables break at terminal width
**Symptom**: Pipe tables overflow and wrap incorrectly.
**Root cause**: `lib/markdown.ts` table renderer may not be respecting terminal width.
**Fix**: Pass `termWidth` to the markdown renderer and truncate/adapt columns.

### BUG 5: Chat context lost between messages
**Symptom**: Agent forgot it was discussing RBX1 in the same conversation.
**Root cause**: `useAgent.ts` may not be passing `sessionId` / `resume` parameter to subsequent `query()` calls. Each submit creates a new session instead of continuing.
**Fix**: In `useAgent.ts`, capture `session_id` from the first SDK response and pass `{ resume: sessionId }` in subsequent calls.

### BUG 6: Tool activity appears mid-content
**Symptom**: Tool call status lines appear between content blocks.
**Root cause**: Tool summaries are being added to the `completedMessages` array interleaved with assistant text.
**Fix**: Keep tool activity ONLY in the dynamic `<ToolActivity>` panel, don't add tool_summary messages to the Static list.

### BUG 7: Missing fold validation in campaign plan
**Symptom**: Campaign plan doesn't include computational fold validation step.
**Root cause**: System prompt / skill doesn't emphasize checking if the target folds computationally before designing binders.
**Fix**: Update `harness/src/agent.ts` buildSystemPrompt() to include: "Before designing binders, verify the target structure folds correctly in silico using Protenix. Check if cropped epitope regions maintain their fold."

---

## Design Feedback to Address

1. **Scientific focus** — agent responses should center on what a scientist needs (structure quality, fold confidence, epitope accessibility) not market data
2. **Adaptive detail** — start simple for biologists, escalate for experts
3. **Long task progress** — show step-by-step progress for research/design, not just "Thinking"
4. **Campaign plan must include fold validation** — check target folds before designing
5. **Tables** — need better rendering within terminal width constraints
6. **Tool output visibility** — show tools being called but NOT raw intermediate data
7. **Timeline** — campaign plan should include realistic timeline estimates
8. **Double Ctrl+C to exit** — first cancels operation, second exits (like Claude Code)

---

## Recommended Approach for Next Session

### Step 1: Research existing harness templates
Before fixing bugs, check:
- `github.com/anthropics/claude-agent-sdk-demos` — official demo apps
- Search npm for `claude-code-harness`, `ink-chat`, `claude-agent-tui`
- Check if there's a community template that handles Static + streaming correctly
- Look at how the official Claude Code handles scrollback (they use Ink too)

### Step 2: If good template exists → adapt it
- Port our theme, toolNames, markdown renderer on top
- Keep all backend (agents/, lib/ that doesn't touch rendering)
- This would be faster than debugging Ink's Static behavior

### Step 3: If no template → fix bugs in order
1. Fix Ctrl+C (quick, high impact)
2. Fix content duplication (hardest, may need to bypass Static)
3. Fix session context (sessionId pass-through)
4. Fix double content (streaming vs final dedup)
5. Fix tables (width-aware rendering)

---

## Files to Focus On for Bug Fixes

| Bug | Primary File |
|-----|-------------|
| 1 (duplication) | `src/components/MessageList.tsx` + `src/hooks/useAgent.ts` |
| 2 (can't quit) | `src/index.ts` + `src/app.tsx` |
| 3 (double content) | `src/hooks/useAgent.ts` |
| 4 (tables) | `src/lib/markdown.ts` |
| 5 (context) | `src/hooks/useAgent.ts` (sessionId) |
| 6 (tool placement) | `src/hooks/useAgent.ts` + `src/app.tsx` |
| 7 (fold check) | `src/agent.ts` (system prompt) |

---

## How to Resume

```bash
cd /home/tristanfarmer/Documents/protein_design_agent
git checkout frontend-rebuild
cd harness && npm install && npx tsc && npm start
```

## Session Stats
- ~80+ agent teams deployed this session
- 78 commits on master + ~8 on frontend-rebuild
- 128 backend tests passing
- Frontend rebuild: architecture correct, 7 rendering bugs remain
- Real Tamarind BoltzGen smoke test completed successfully
- 10-scenario stress test: 8 PASS, 2 PARTIAL
