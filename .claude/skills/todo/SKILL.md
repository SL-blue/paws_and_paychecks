---
name: todo
description: Capture one idea or to-do. While the board is paused, adds it to PROGRESS.md (no GitHub calls).
argument-hint: "<the idea, in your own words>"
disable-model-invocation: true
---

First read `.claude/PROJECT_OPS.md` §0.

**If the status is PAUSED (now):** add one line to the "To-dos" section of `PROGRESS.md`:
`- [ ] <short imperative title with a type prefix> · <label> · <milestone guess or "?"> · added <today>`
Keep Nancy's meaning; you may shorten her words. Commit it only if you're on a task branch; on `main`, leave it uncommitted. Reply with the line you added. Don't call `gh`.

**If the status is ACTIVE:** delegate to `project-scribe` with:
```
MODE: todo

Idea from Nancy: <her words>
```
Reply with the issue link it returns.

Idea from Nancy: $ARGUMENTS
