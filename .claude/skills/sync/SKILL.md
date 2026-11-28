---
name: sync
description: End-of-session update of the GitHub Project board and the wiki Dev-Log, through the project-scribe subagent.
argument-hint: "[optional: approvals, decisions or Notes requests, in your own words]"
disable-model-invocation: true
---

Nancy is wrapping up this session (or has just approved work). Delegate to the `project-scribe` subagent; don't edit the board or the wiki yourself.

Write the delegation message like this, from what happened in **this session**:

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
Extra from Nancy: $ARGUMENTS
```

Only list approvals, decisions and Notes requests that Nancy actually gave in this conversation or in the arguments above. Never infer them.

When the scribe returns, show Nancy its summary as it is. If it reports anything under "Unsure", ask her about those items.
