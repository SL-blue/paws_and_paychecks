---
name: sync
description: End-of-session update. While the board and wiki are paused, logs the session in PROGRESS.md (no GitHub calls).
argument-hint: "[optional: approvals, decisions or notes, in your own words]"
disable-model-invocation: true
---

First read `.claude/PROJECT_OPS.md` §0.

## If the status is PAUSED (now)

Don't delegate to `project-scribe` and don't call `gh`. Update `PROGRESS.md` from what happened in **this session**:

1. For each task touched (finished or not): add today's dated update under its heading in "Log" (create the heading if needed, newest first). Use 1–3 plain-language bullets, plus the branch or PR link.
2. Update "Now" and the status at the end of each heading. A task Nancy says she merged is `Done`; finished but not merged is `In review`; anything else is `In progress`.
3. Add new to-dos to "To-dos" and new questions to "Waiting on Nancy".
4. Only record approvals and decisions Nancy actually gave in this conversation or below. Never infer them.
5. Commit `PROGRESS.md` on the current task branch. If you're on `main`, don't commit: leave the change uncommitted and tell Nancy it will go in with the next task's branch.

Show Nancy a short summary of what you changed.

## If the status is ACTIVE

Delegate to `project-scribe` with `MODE: sync` and this session summary:

```
MODE: sync
Date: <today, YYYY-MM-DD>
Tasks touched:
- <task title> · issue #<n or "none"> · PR <link or "none"> · <finished / unfinished>
  - <what changed this session, 1–3 plain-language bullets>
New to-dos: <list or "none">
Questions for Nancy: <list or "none">
Approvals/decisions from Nancy (quote her words): <list or "none">
Notes edit requested by Nancy (quote her words): <or "none">
```

Show Nancy the scribe's summary as it is, and ask about anything under "Unsure".

Extra from Nancy: $ARGUMENTS
