## Brief overview
- Global working rule: maintain a `memory-bank/` directory as the authoritative project memory across sessions.
- At the start of every new task/session, read **all** core Memory Bank files before making changes.
- Keep entries concise, factual, and action-oriented so future sessions can resume quickly.

## Memory Bank required files
- Ensure these core files exist in `memory-bank/`:
  - `projectbrief.md`
  - `productContext.md`
  - `activeContext.md`
  - `systemPatterns.md`
  - `techContext.md`
  - `progress.md`
- If a required file is missing, create it with a minimal but clear structure before continuing major implementation work.

## Session start workflow
- On every task start, read all core Memory Bank files in full.
- Use `projectbrief.md` as scope/source-of-truth when requirements appear ambiguous.
- Use `activeContext.md` and `progress.md` to decide immediate next steps and avoid repeating completed work.

## Update triggers
- Update Memory Bank when:
  - New architectural or workflow patterns are discovered.
  - Significant features/fixes are implemented.
  - The user asks to **update memory bank** (must review all core files first).
  - Existing context is unclear or outdated.

## Update quality standards
- Prefer clear bullet points over long prose.
- Record decisions with rationale when it affects future implementation.
- Keep `activeContext.md` focused on: current focus, recent changes, next steps, active decisions, and key learnings.
- Keep `progress.md` explicitly split between what works, what remains, and known issues.

## Additional context organization
- Add extra docs/subfolders under `memory-bank/` only when they improve retrieval (e.g., integrations, API notes, test strategy, deployment runbooks).
- Use descriptive, narrow filenames so future sessions can find context quickly.
- Keep additional files linked or referenced from relevant core files when useful.