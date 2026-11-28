---
name: board-setup
description: One-time setup of the GitHub Project, labels, milestones, seed issues and wiki pages. Run without arguments for a dry run; run with "apply" after approving the plan.
argument-hint: "[apply]"
disable-model-invocation: true
---

Delegate to the `project-scribe` subagent. Don't create anything yourself.

- If the argument is empty: send `MODE: setup-dry-run`. When the plan comes back, show it to Nancy in full and ask what to change. Then stop.
- If the argument is `apply`: send `MODE: setup-apply`, followed by the **last plan from this conversation with all of Nancy's edits applied**, written out in full. If there is no approved plan in this conversation, don't delegate. Tell Nancy to run `/board-setup` first.

When the scribe finishes, show its summary and the list of manual steps Nancy still has to do in the web UI.

Argument: $ARGUMENTS
