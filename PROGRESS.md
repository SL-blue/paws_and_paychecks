# Progress

The GitHub board (https://github.com/users/SL-blue/projects/2) and the wiki are **paused** since 2026-11-27 and frozen as of that date (see `.claude/PROJECT_OPS.md` §0). Until they're back, this file is where progress and new to-dos are recorded. Existing issues keep their numbers; the board's Roadmap page shows how things stood at the pause.

Format:
- **Now**: tasks in progress, with branch and issue
- **Waiting on Nancy**: PRs to open or review, and questions only Nancy can answer
- **To-dos**: new since the pause (no issue numbers yet)
- **Log**: one heading per task (newest first) with one dated update per session; the heading ends in the task's status (`In progress` · `In review` · `Done`)

## Now

- (nothing yet)

## Waiting on Nancy

- Open decisions from before the pause are on the board: M0 #13–#21, M1 #30–#34, M2 #43, M3 #45.
- **Open the PR for `feat/econ-sim-round3`** (round 3, spec v0.4) and review it.
- **Round 3 decisions** (`sim/reports/SIM_REPORT.md` §12): careful players get no short-term stress, so the stress
  targets conflict (convergence-week pressure, S drivers, or restated targets?); keep or revert the far-from-spec tuned
  stress numbers; the grinder stuck at stress 100; the feedback target vs. the intended squeeze; five dead effects and
  the standing desk; apply the recommended overlay?

## To-dos

- [ ] Re-run the stress search at the final starting cash (or alternate stress and cash searches) · sim · ? · added 2026-11-28
- [ ] Model a convergence-week job for careful players and measure its short-term stress · sim · ? · added 2026-11-28

<!-- Format: - [ ] <short imperative title> · <label> · <milestone or "?"> · added YYYY-MM-DD -->

## Log

### Economy simulation round 3 (spec v0.4) · issue none · In review
- **2026-11-28:** Built the v0.4 rules (two-layer stress, money tiers with "poor", $400 loan and −$100 floor, skip,
  value-based shop, changed effects, imperfect careful, 9,000-word story job) and a stress-parameter search. Archived
  round 2 as `SIM_REPORT_round2.md`. Ran 2,000 seeds: 23/39 targets met (25/39 with the recommended overlay). Money
  targets now mostly met; the stress targets conflict because careful players' short-term stress stays at 0.

### Tooling: pause the board and wiki, ready-made PR links, PROGRESS.md · issue none · In review
- **2026-11-27:** Paused `project-scribe` (the GitHub account it uses was restricted). The main session now pushes the branch and gives a ready-made PR link instead of opening the PR, and tracks progress here. Added rate limits and a `catch-up` mode for when the board comes back.

Everything finished before the pause (PRs #1–#5) is in the wiki's Dev-Log.
