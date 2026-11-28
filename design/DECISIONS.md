# Decisions

A short log of what is settled and why. The design docs describe *what* the game is; this file records *when* each piece was decided and *why*, so settled questions don't get reopened by accident.

Format: `- YYYY-MM-DD — decision — why`.
To change a decision, don't delete the old line. Add a new one and mark the old line **(superseded by YYYY-MM-DD)**.

## Design (owner decisions)

### Scope and format
- 2026-11-24 — v2 is for human players only; the v1 anti-AI-agent requirements no longer apply — the class assignment is done; the goal now is a story-driven game.
- 2026-11-24 — Narrative life sim + resource management + roguelike, 42 in-game days (6 weeks) — long enough for the creature to grow up and for four story lines to build and converge.
- 2026-11-24 — No instant-reaction gameplay; small interactions express feeling rather than test skill — fits a reflective, story-driven tone.
- 2026-11-24 — Bankruptcy is possible; the ending depends on the final state of stress, the relationship and the pet — choices need real stakes, and the ending should reflect how the player lived. **(superseded by 2026-11-27: five ending goals; bankruptcy becomes the parents' ending)**
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
- 2026-11-26 — The book starts with progress already made (60–75%); the hard chapters remain, sized to about 60–80 hours of in-game work — it shows the character's long-standing commitment, justifies a slower pace, and makes finishing a real but doable sacrifice. **(range superseded by 2026-11-27: narrower variation, sized by ending targets)**
- 2026-11-26 — The economy is tuned by simulation, against acceptance targets per player strategy — balance should be measured, not guessed.

### Repo and tooling
- 2026-11-26 — Design docs and the decision log live together in `design/` (the former `docs/` was merged into it) — one place for the source of truth.
- 2026-11-27 — v2 has its own repo, separate from v1 — coding agents work only from v2's design, with no v1 code or rules in view.
- 2026-11-27 — Tunable numbers live in `data/` (e.g. `data/economy.yaml`), outside `sim/` — the simulator uses them now and the game will read the same files later, so there is one set of numbers.

### Endings (2026-11-27)
- 2026-11-27 — Endings are built from five goals: keep the pet, a good relationship with her (not ignoring her too much), the book finished, low or medium stress, and a good financial situation; their combination decides the ending — the ending should reflect how the player balanced their life, not one score.
- 2026-11-27 — The best ending needs all five goals, including the book; meeting the other four without the book is still a good ending — the book is the character's own voice, so it marks the best outcome, but a life kept in balance is already a good one.
- 2026-11-27 — A good financial situation = not in the parents' ending, no debt left, and an end value of at least about one month's rent; "okay" = solvent but below that — "good" means a month of safety, not wealth.
- 2026-11-27 — Bankruptcy doesn't end the run directly: borrowing from her raises stress sharply, and if the loan isn't repaid within 7 days (Normal; 5 on Hard), the game ends with the character's parents calling to help — a warm ending, not a punishment, that fits the tone.
- 2026-11-27 — The book's finishing rate is set by ending targets (careful player: finishes ~40–50%, best ending ~25–35%; book-heavy: best ending ~45–55% with bankruptcy risk) — the best ending should be earned, not the default; committing to the book is rewarded at a risk.
- 2026-11-27 — The book's starting progress varies only a little between runs, and a nearly finished book ("finished a month later") counts toward the good ending, not the best — finishing should depend on choices, not dice.
- 2026-11-27 — The book pays no advance during the run — an advance made book-heavy play almost risk-free (27% → 1% bankrupt), and working on the book should stay a real sacrifice.

### Work and money (2026-11-27)
- 2026-11-27 — The week-2 story job is a story choice that is hard to refuse (it comes from the regular client); declining is allowed but hurts that client relationship — keeps the week-5 squeeze likely while leaving the choice to the player.
- 2026-11-27 — A fixed small direct-client job on day 1–2, paid around day 4, opens the run — fixes the empty first week (feedback and the day-5 cash low) and doubles as a tutorial.
- 2026-11-27 — The feedback target counts job payments only (the day-1 job included), not pre-move invoices — feedback should come from work the player actually played.
- 2026-11-27 — The tax share is fixed at 22% and is no longer a tuning lever; how it is shown (net pay, a tax jar or a tax bill) is still open — it was the strongest lever in the economy and would hide other problems.
- 2026-11-27 — Most clients are modeled as types; a few regular clients are a special kind with a slightly better pay-to-time ratio or faster payment, each with its own habits, from a shared simulation baseline — named clients carry the story without a full client system.
- 2026-11-27 — Regular clients' work is mixed: one or two fixed story commissions on set days, plus random work that follows each client's habit — fixed beats serve the story; learnable habits reward planning.
- 2026-11-27 — Rush jobs: about 15% of offers, half the deadline, 1.25× pay, and a higher stress cost — confirmed from the simulator's interpretation, with stress added.

### Effects (2026-11-27)
- 2026-11-27 — The effect pool grows to about 30–40 effects — with ~10–14 chances to pick per run, a small pool makes every run end with the same effects.
- 2026-11-27 — Only a few effects speed up the book, not all efficiency effects — otherwise finishing the book depends mostly on which effects were offered.
- 2026-11-27 — Efficiency effects get smaller individually, rather than a higher efficiency cap — a high cap shrinks the work time needed and distorts the whole economy.
- 2026-11-27 — The CAT tool becomes weaker and more expensive (about +10% throughput, about $60/week; the simulation may fine-tune the price) — it was a near-automatic pick.
- 2026-11-27 — "Her spreadsheet" is a story and UI effect only: it helps the player see the character's state, which they might otherwise ignore — it has no mechanical bonus.

## Implementation (agent choices)

<!-- Coding agents may append technical choices here, one line each, with a reason. -->
- 2026-11-27 — Simulator in Python 3.11+ with only pyyaml, numpy, matplotlib, pytest (stdlib `random` for draws, `concurrent.futures` for parallel seeds) — allowed list, nothing else needed.
- 2026-11-27 — Random draws come from named streams keyed by (seed, system, day/job id), so offers, interruptions, costs and payment lateness are identical across policies for a seed — reproducible per (config, policy, seed) and fair policy comparisons.
- 2026-11-27 — The whole offer stream of a run is generated up front; only the greedy-optimal policy may read it — makes the "no hidden future state" rule checkable (`Policy.uses_foresight`).
- 2026-11-27 — Player-behaviour numbers live in `data/policies.yaml` (simulator-only), economy numbers in `data/economy.yaml` — keeps economy.yaml clean for the game while keeping every number out of code.
- 2026-11-27 — Recommended tuning changes are an overlay, `data/economy.recommended.yaml`, applied on top of economy.yaml for the re-run — the owner can review them before they become the game's numbers.
- 2026-11-27 — Bankruptcy does not stop a simulated run; it is flagged and the run continues to day 42 — the spec calls it an ending path, and stress/relationship metrics stay comparable across runs.- 2026-11-27 — Round 2 (spec v0.3): regular clients' habit jobs, their effect-only extra jobs (loyal client) and extra random offers (direct network, rush specialist) are all pre-generated in the offer stream and only become visible with the effect — the world stays identical across policies for a seed, so effects are compared fairly.
- 2026-11-27 — Every offer carries pre-drawn rolls (reputation drop, specialist-niche drop, deposit-terms drop, extra-offer visibility) from its own stream keyed by offer id — filters stay deterministic and independent of what else the player holds.
- 2026-11-27 — Effects that move a number by a share are applied as config-driven pure functions in `effects.py`; caps clamp each category's sum per job and work segment; synergies are added after the cap — keeps "categories multiply, synergies may exceed caps" checkable in unit tests.
- 2026-11-27 — Effect time (classes, admin, naps, cooking) is taken from free time first, then from paid hours; overlaps (reading aloud, quiet company, evening walks) are computed when the day's plan is fitted into 24 h — the spec's "free time first, then paid time" rule, in one place.
- 2026-11-27 — The day's pet-care need is fixed when the plan is made, so an effect picked later that day (e.g. evening walks, +0.25 h) starts the next day — avoids false deficit days.
- 2026-11-27 — A parents' ending stops the run on that day; metrics are computed up to it, and its stress goal uses the last 7 days if the run ended before day 36 — spec §6 ("record the day and compute metrics up to it").
- 2026-11-27 — Value-based policies rate effects with a short analytic estimate (money, stress points, book hours, free hours, risk) weighted by hand-set per-policy weights in `data/policies.yaml` (`sim/src/effect_value.py`), not a simulated look-ahead — fast enough for 2,000 seeds × every sweep point, and every weight is visible in config.
- 2026-11-27 — The starting-cash search, H search, CAT-price check and sensitivity sweep run the four player policies only; greedy-optimal (12 simulated plans per seed) runs in the main matrix and the recommended re-run — its targets (0% best/good) do not depend on these numbers, and it would multiply the run time by ~4.
- 2026-11-27 — The "effect boost on paid work" metric counts efficiency × throughput × rate effects (round 1: efficiency × throughput only) — v0.3 moves much of the effects' value into pay per word, which is part of "paid work".
- 2026-11-27 — Round-1 headline numbers are kept in `sim/reports/round1_headline.yaml` (extracted once from round-1 raw results) — the round-2 report compares against them without needing the old code or raw data.
