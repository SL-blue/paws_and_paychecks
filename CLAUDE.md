# CLAUDE.md

Instructions for coding agents working in this repo.

## What this project is

**Paws & Paychecks** is a narrative life-sim roguelike for human players. Over 42 in-game days, a freelance translator raises an invented creature from infancy to adulthood while managing money, stress and a relationship. It features uneven pacing, delayed consequences, possible bankruptcy and multiple endings.

This is the **v2** project, in its own repo. An earlier class-assignment version (v1, a Three.js browser game built to be hard for AI agents) lives in a separate repo that is not available here. Don't look for it or reuse its code. None of v1's anti-agent rules (hidden server state, timed choices, bot resistance) apply here.

## Current phase

**Economy design and simulation.** There is no game code yet, and the engine/platform is **not decided**.
- Do not scaffold a game client, pick an engine, or add game-runtime code unless the owner asks.
- Current task: build and run the economy simulation described in `design/SIM_BASELINE.md` §9, and write the report.

## Repo layout

```
README.md
CLAUDE.md                 # this file
design/                   # design docs and the decision log (source of truth)
  STORY_CONCEPT_V2.md     # story, characters, systems, themes
  SIM_BASELINE.md         # economy numbers + simulation spec
  DECISIONS.md            # log of settled decisions
data/                     # numeric config shared by the simulator now and the game later
  economy.yaml
sim/                      # economy simulator
  src/
  tests/
  reports/                # SIM_REPORT.md and charts (committed); raw run data is gitignored
```

Create `data/`, `sim/src/`, `sim/tests/` and `sim/reports/` when you first need them.

## Read before working

1. `design/DECISIONS.md`: what is settled. Don't reopen these.
2. `design/STORY_CONCEPT_V2.md`: what the game is.
3. `design/SIM_BASELINE.md`: the numbers and what the simulation must do.

Note: `STORY_CONCEPT_V2.md` mentions `GAME_DESIGN.md`, `TECH_SPEC.md` and a `CLAUDE.md` as v1 documents. Those are the v1 files, not this file, and they are not in this repo.

## Hard rules

1. **Design docs are the source of truth. Don't change the design.** If the docs are ambiguous or conflict, and the choice affects game rules, ask the owner. If it doesn't, make the simplest reasonable choice and record it (see "Logging" below).
2. **All tunable numbers live in `data/economy.yaml`**, not in code. The simulator reads them from there. The game will later read the same file, so keep it engine-agnostic: plain YAML, readable names, a short comment per value giving units and meaning.
3. **The numbers in `SIM_BASELINE.md` are starting values.** When tuning changes a number, change it in `data/economy.yaml` and explain the change in the report. Don't silently edit the spec's numbers.
4. **Determinism.** Every simulation run is seeded and reproducible from (config, policy, seed).
5. **Keep dependencies minimal.** Allowed without asking: Python standard library, `pyyaml`, `numpy`, `matplotlib`, `pytest`. Anything else needs a one-line reason under "Implementation" in `design/DECISIONS.md`.
6. **Don't commit junk.** Keep a `.gitignore` covering `.DS_Store`, virtual environments, caches and raw simulation output.

## Simulation conventions

- Python 3.11+.
- One module per system, matching `SIM_BASELINE.md` §9.1: calendar, offers/jobs, payments, costs, stress, time demands, effects, lifelines, book.
- Player strategies (policies) are separate, swappable classes. No policy may read hidden future state, such as upcoming offers or random draws, except the explicitly search-based "greedy-optimal" policy, which must be labeled as such in the report.
- Unit tests for the rules: payment timing, rent and bills, stress changes, effect stacking and caps, lifelines, bankruptcy.
- One command reproduces the full report (fill in below once it exists).

## Commands

(Fill in once scaffolded.)
- Install: `pip install -r sim/requirements.txt`
- Tests: `pytest sim/tests`
- Full run + report: `python -m sim.run --all` (~8 min on 10 cores; raw results go to `sim/reports/raw/`, gitignored)
- Rebuild the report from saved results: `python -m sim.run --report`
- Re-run only the recommended overlay (`data/economy.recommended.yaml`) on saved results: `python -m sim.run --recommended`

## Logging

- **`design/DECISIONS.md`** has two kinds of entries:
  - **Design:** decisions the owner made. Add one only when the owner confirms a decision in the conversation.
  - **Implementation:** your own technical choices (libraries, data formats, modeling simplifications). You may append these yourself, one line each, with a reason.
- **Interpretation choices** about ambiguous spec details go in the report's "Open issues" section, so the owner can review them.

## Workflow

- Work on **one task at a time**. At the end of each task: make sure it runs, run the tests, then summarize what changed, how to try it, and anything the owner should decide. Then **stop and wait for review**.
- Keep functions small and readable. The owner must be able to explain the code.
- Docs and code comments are in English.

## Git workflow
- Never commit to `main`. Before starting a task, update main and create a new branch:
  `git switch main && git pull && git switch -c <type>/<short-name>`
  (types: feat, fix, docs, chore, e.g. `feat/econ-sim-core`)
- One branch per task. Commit in small, logical steps with clear messages.
- When the task is done: push the branch and open a pull request with `gh pr create`,
  describing what changed and how it was tested. Link the issue if there is one ("Closes #12").
- Don't merge pull requests yourself. Nancy reviews and merges.

## Terms used in the docs

- **"The weather"**: AI as an ambient condition of the world (e.g. clients moving work to post-editing). It is not a plot driver.
- **Effects**: roguelike modifiers offered at random. The player picks 1 of 3.
- **Lifelines**: ways out of a cash crisis (borrowing from her, an early payment, late rent).
- **Callbacks**: events scheduled by earlier choices, including everyday moments.
- **Convergence week**: week 5 (days 29–35), when the four story lines peak together.
