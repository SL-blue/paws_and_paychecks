# Decisions

A short log of what is settled and why. The design docs describe *what* the game is; this file records *when* each piece was decided and *why*, so settled questions don't get reopened by accident.

Format: `- YYYY-MM-DD — decision — why`.
To change a decision, don't delete the old line. Add a new one and mark the old line **(superseded by YYYY-MM-DD)**.

## Design (owner decisions)

### Scope and format
- 2026-11-24 — v2 is for human players only; the v1 anti-AI-agent requirements no longer apply — the class assignment is done; the goal now is a story-driven game.
- 2026-11-24 — Narrative life sim + resource management + roguelike, 42 in-game days (6 weeks) — long enough for the creature to grow up and for four story lines to build and converge.
- 2026-11-24 — No instant-reaction gameplay; small interactions express feeling rather than test skill — fits a reflective, story-driven tone.
- 2026-11-24 — Bankruptcy is possible; the ending depends on the final state of stress, the relationship and the pet — choices need real stakes, and the ending should reflect how the player lived.
- 2026-11-24 — Not necessarily web-only; platform/engine undecided — the core loop should decide the engine, not the other way round.
- 2026-11-24 — Tone: warm and honest, not complaining about the current state of the world.

### Story and characters
- 2026-11-24 — The pet is an invented creature that arrives very young and grows through stages — its growth needn't match a real animal, which frees the pacing.
- 2026-11-26 — The character is a freelance translator — this came from the dream that inspired the game, and it sits right on the "expression vs. standard results" theme.
- 2026-11-26 — AI is "the weather": ambient, shaping the work (e.g. post-editing), not an antagonist or an argument — the game carries universal feelings rather than a position on AI.
- 2026-11-26 — The partner is an engineer (field unspecified) with a habit of quantifying things — it gives a contrasting perspective: meaning in work that has to be exactly right. Leaving the field open keeps the focus on her character.

### Systems
- 2026-11-26 — Relationship and pet state are never shown as numbers; money is exact; stress may be visible depending on difficulty — players read people and the creature through cues, but need to plan money and workload.
- 2026-11-26 — Events: fixed important events + random events drawn by stage + callbacks + choices that depend on earlier choices — delayed consequences make long-term judgment matter.
- 2026-11-26 — Everyday events don't need to touch two story lines; they build immersion and give small relief — not every moment has to be a plot beat.
- 2026-11-26 — Everyday moments can plant callbacks — as in real life, small things sometimes turn out to matter.
- 2026-11-26 — Daily cycle: a common-sense default day (work 9 am to 5–6 pm, evening free, 8 h sleep) that the player can rearrange freely — intuitive by default, flexible for a freelancer.
- 2026-11-26 — Sleep is a default the player can cut into, at a cost — gives a self-chosen trade-off without forced crunch.
- 2026-11-26 — Interruptions happen during the player's working hours, and not all of them are bad or important — keeps attention honest without punishing every interruption.
- 2026-11-26 — The auto-arrangement proposes the day's plan and is deliberately imperfect — if it were perfect, the player would have nothing left to decide.
- 2026-11-26 — Roguelike effects (e.g. working-efficiency modifiers) are chosen from randomly offered options; chances to pick come from a mix of sources (guaranteed, earned, bought) — run-to-run variety, plus rewards for how the player plays.

### Economy
- 2026-11-26 — The financial system is designed first, with time as the shared currency; stress, relationship and pet are coupled to it through time and efficiency, not derived from money — a relationship computed from money would feel transactional.
- 2026-11-26 — Real-world rates and throughput are kept; payment terms are compressed to game time (about 2–14 days, sometimes late) — real 30–60 day terms would pay most in-game work after the run ends, with no feedback for the player.
- 2026-11-26 — One realistic long delay is kept as a fixed story event (a week-2 job paid in week 5) — keeps the real feeling of freelance cash flow where it hurts most, in the convergence week.
- 2026-11-26 — Feedback on finished work comes at delivery (client reply, reputation, a visible "money owed" list); cash comes later — separates the sense of progress from cash flow.
- 2026-11-26 — The book starts with progress already made (60–75%); the hard chapters remain, sized to about 60–80 hours of in-game work — it shows the character's long-standing commitment, justifies a slower pace, and makes finishing a real but doable sacrifice.
- 2026-11-26 — The economy is tuned by simulation, against acceptance targets per player strategy — balance should be measured, not guessed.

### Repo and tooling
- 2026-11-26 — Design docs and the decision log live together in `design/` (the former `docs/` was merged into it) — one place for the source of truth.
- 2026-11-27 — v2 has its own repo, separate from v1 — coding agents work only from v2's design, with no v1 code or rules in view.
- 2026-11-27 — Tunable numbers live in `data/` (e.g. `data/economy.yaml`), outside `sim/` — the simulator uses them now and the game will read the same files later, so there is one set of numbers.

## Implementation (agent choices)

<!-- Coding agents may append technical choices here, one line each, with a reason. -->
