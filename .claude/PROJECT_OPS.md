# Project ops: GitHub Project board + wiki

> Settled 2026-11-27. The `project-scribe` subagent (`.claude/agents/project-scribe.md`) reads this file every run. Change it only when Nancy asks.

## 1. Who owns what

| Place | Role | Source of truth for | Who edits |
|---|---|---|---|
| `design/` in the repo | Game design + decision log | What the game is, what is settled | Nancy + main Claude Code session (per `CLAUDE.md`) |
| `sim/reports/` | Simulation results | Economy numbers and findings | Main session |
| **GitHub Project** | Work tracking | What is being done, what's next, what's waiting on Nancy | `project-scribe` (+ Nancy, + GitHub's built-in workflows) |
| **GitHub wiki** | Readable layer for Nancy and friends | Nothing new: it summarizes and links | `project-scribe` for agent-owned pages; `Notes/*` only on Nancy's request |

Rule of thumb: **the wiki never holds design content that isn't already in `design/`.** If a summary and a design doc disagree, the design doc wins and the summary gets fixed.

Audience: Nancy and her friends. Story spoilers (endings, week-5 events) are fine; this is a dev wiki.

## 2. GitHub Project (board)

**Project:** `paws and paychecks-progress tracking` (user project **#2**, https://github.com/users/SL-blue/projects/2), owned by `SL-blue`, linked to `SL-blue/paws_and_paychecks`, visibility public. Nancy created it; look it up by number, not by title.

### Fields

| Field | Type | Values |
|---|---|---|
| Status | single select | `Backlog` · `Ready` · `In progress` · `In review` · `Done` |
| Priority | single select | `P0` (now) · `P1` (next) · `P2` (later) |
| Size | single select | `XS` · `S` (< 1 session) · `M` (1–3 sessions) · `L` (several sessions) · `XL` (too big: split it) |

- `In review` = the task is finished and its PR is open, waiting for Nancy (matches `CLAUDE.md`'s "stop and wait for review").
- **Approval = Nancy merging the PR.** The PR says "Closes #n", so merging closes the issue, and GitHub's built-in project workflows set `Done`. The scribe only checks that this happened. It may also set `Done` when Nancy's approval is quoted to it (for work without a PR).
- Size is a rough guess, set when the issue is created. Its main use: any `XL` gets split before work starts, usually into sub-issues (see below).
- Milestones use GitHub's built-in **Milestones**, not a custom field.

### Labels (issue type)

`design` · `sim` · `story` · `code` · `art` · `tooling` · `docs`, plus **`decision-needed`**: a question only Nancy can answer.

### Milestones

| Milestone | Covers | Done when |
|---|---|---|
| **M0 · Economy sim & tuning** | Current phase: simulator, report, tuning | Nancy accepts the report and its "Open issues" are resolved or moved to issues |
| **M1 · Systems spec** | The open questions in `STORY_CONCEPT_V2.md`: daily-cycle time unit, cost of cutting sleep, interruptions, auto-arrangement, stress visibility vs. difficulty, event system details | Each question is decided in `DECISIONS.md` or deliberately parked |
| **M2 · Story outline** | 42-day beat sheet, characters, fixed events, first event pools, why they live apart | A full beat sheet Nancy is happy with |
| **M3 · Platform + prototype** | Engine/platform decision, a playable prototype of one in-game week | The engine is decided; week 1 is playable end to end |

The agent **must not create new milestones** outside setup; it proposes them in its summary instead.

### Views

1. **Board**: grouped by Status
2. **Roadmap**: table, grouped by Milestone, sorted by Priority
3. **Nancy's inbox**: Status = `In review` OR label = `decision-needed`

### Issue conventions

- Titles: imperative and prefixed by type, e.g. `Decide: time unit for the daily cycle`, `Sim: re-run with the recommended overlay`, `Story: draft the week-5 convergence beats`.
- Body template:
  ```
  **Context:** one or two lines + links (design doc section, report section, commit)
  **Done when:** a concrete check
  **Notes:** optional
  ```
- `decision-needed` issues are closed **only** after a matching line exists in `design/DECISIONS.md` on `main`; the closing comment links to it.
- Never delete issues. Close duplicates as "not planned" with a link to the kept one.

### Parent issues (sub-issues)

- Use a parent issue only for a real cluster of related work inside **one** milestone (e.g. "Sim round 2: owner decisions"). Milestones group by phase; parents group by topic within a phase.
- **One level only:** a sub-issue never has its own sub-issues.
- Labels, Priority and Size go on the sub-issues. A parent gets only its milestone and a title without a type prefix, e.g. `Economy simulator`.
- A parent closes when all its sub-issues are closed.
- New issues (from `/todo` or end-of-task) go under an existing parent when they clearly belong to its topic and milestone; otherwise they stay standalone. Don't create new parents outside setup; propose them in the summary.
- Link with the GraphQL `addSubIssue` mutation (`gh` has no sub-issue command).

## 3. Wiki

Local clone: `.wiki/` in the repo root (gitignored). The wiki's branch is `master`, and it's pushed directly: the repo's branch/PR rules don't apply to it.

### Pages

| Page | Content | Who edits |
|---|---|---|
| `Home` | One-paragraph pitch, current phase, links to the other pages and the board | agent |
| `Roadmap` | Milestones with status, what's next, a "Waiting on Nancy" list (generated from the board) | agent |
| `Dev-Log` | One entry per task, updated each session (format below) | agent |
| `Design-Overview` | A one-page readable summary of `design/` with links to each section; no new content | agent |
| `Simulation` | How to run it, what each policy means, headline results, link to `SIM_REPORT.md` | agent |
| `Glossary` | Terms such as lifelines, receivables, end value, crisis, convergence week, post-editing, policies | agent |
| `_Sidebar` | Navigation | agent |
| `Notes/*` | Nancy's own pages (mood boards, ideas, references) | Nancy; the agent reads them, and edits **only when Nancy explicitly asks for that edit** |

### Dev-Log format

Organized **by task**, with one dated update per work session. Tasks still in progress are at the top; finished tasks follow, newest first.

```
## Sim: re-run with the recommended overlay · #12 · In review
- **2026-11-28:** what changed this session (1–3 bullets, plain language) · PR #14
  - Decided: <link to DECISIONS.md line>, if any
  - Waiting on Nancy: <items>, if any
- **2026-11-27:** ...
```

- A task's heading carries its issue number and its current board Status. Update the Status whenever the board changes.
- A session that touched several tasks adds one dated update under each of them.
- Work that isn't tied to an issue goes under a heading named `Misc` instead of getting a new task heading.

## 4. Agent boundaries

The `project-scribe` subagent:

**May**
- Create and edit issues, labels and comments; add items to the project; set Status, Priority, Size and Milestone (existing milestones only)
- Edit agent-owned wiki pages in `.wiki/`; commit and push the wiki
- Read anything in the main repo (`design/`, `sim/reports/`, `git log`) and in the wiki, including `Notes/*`

**Must not**
- Edit, stage or commit anything in the main repo
- Set `Done` unless the PR is merged or Nancy's approval is quoted to it
- Close a `decision-needed` issue without a matching `DECISIONS.md` line on `main`
- Create milestones, labels or fields (except in setup), delete anything, or merge PRs
- Edit `Notes/*` unless the delegation message passes on Nancy's explicit request to edit it
- Write design content into the wiki that isn't in `design/`

**Input:** the subagent starts with a fresh context and doesn't see the conversation. The delegation message starts with `MODE: <mode>` and must include the session summary: tasks and issue numbers, PR links, what changed, approvals Nancy gave (quoted), new to-dos or questions, and any explicit Notes request.

**Always** end with a short summary: board changes, wiki changes, and anything it was unsure about. A subagent can't ask questions mid-run, so anything unclear goes into that summary instead of being guessed.

## 5. Triggers

| Trigger | When | What the scribe does |
|---|---|---|
| **Automatic, end of task** (`CLAUDE.md` → "Board and wiki") | The main session opens the PR, just before it stops for review | Moves the item to `In review`, comments with the summary and PR link, adds the session update to the Dev-Log, files new to-dos or questions |
| **`/sync`** | Nancy wraps up a session, or has just merged/approved work | Adds a session update for every task touched (including unfinished ones), confirms merged work shows `Done`, closes decided `decision-needed` issues, refreshes Roadmap, Home and the summary pages |
| **`/todo <text>`** | Any time an idea comes up | Creates one `Backlog` issue; doesn't touch the wiki |
| **`/board-setup`**, then **`/board-setup apply`** | Once | Dry-run plan → Nancy edits it → the scribe creates exactly that |

Run `/sync` at the end of any session that didn't end on a finished task, so the Dev-Log still gets that session's update.

Not used for now: Stop hooks (they fire every turn, which is too often and too costly) and GitHub Actions (`@claude` in issues; billed separately, maybe later).

## 6. Seeding (first `/board-setup`)

Seed sources:
- Open questions in `design/STORY_CONCEPT_V2.md` → `decision-needed` issues under M1/M2
- The "Open issues" section of `sim/reports/SIM_REPORT.md` → `sim` issues under M0
- Work already done (`git log`) → one item per finished task, `In review` or `Done`
- The platform/engine decision → a `decision-needed` issue under M3
- Wiki: replace the placeholder `Home`, create the pages in §3, and add an empty `Notes/` index page

Manual steps for Nancy in the web UI (the CLI can't do these reliably): create the three views, check the built-in workflows ("Item closed" and "Pull request merged" → `Done`; "Auto-add to project" for this repo).

## 7. Visibility note

On GitHub Free, wikis only work on **public** repos. If the repo is made private, the wiki becomes unavailable unless the account is upgraded to GitHub Pro, and friends would need to be added as collaborators. The Project board's visibility is a separate setting.
