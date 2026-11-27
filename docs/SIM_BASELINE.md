# Paws & Paychecks — Economy baseline & simulation spec (v0.2)

> Purpose: the starting numbers for the v2 financial system (money, time, effects), and the spec for a simulation that tests them. Written so a coding agent can build and run the simulation and write a report without further input. Companion to `STORY_CONCEPT_V2.md`.
>
> All numbers are **placeholders anchored in real-world data** (US dollars, US national averages, since the city is unspecified). They are meant to be tuned by the simulation, not treated as final. Anything marked **(tune)** is expected to move.
>
> **Changes in v0.2:** payment terms compressed to game time, with one long story delay (§3.4); feedback on delivery separated from cash (§3.6); the book starts with progress already made, sized by an hour budget (§3.3); starting cash to be re-tuned for the faster cash flow (§5, §9.3); the earlier pre-check figures no longer apply (§9.5).

## 1. Design approach

- **The financial system is designed first**, with **time as the shared currency**. Stress, the relationship and the pet are not derived *from* money; they are coupled to it through time and efficiency:
  - Relationship and pet need **hours** (evenings with her, walks, play). Every hour they get is an hour not billed.
  - **Stress** is driven by workload, short sleep, deadlines and money anxiety, and it feeds back into **working efficiency**.
  - Money pressure can **trigger** relationship events (e.g. borrowing from her), but the relationship is not a function of money.
- In the simulation, stress is modeled numerically; relationship and pet are modeled as **time demands with thresholds** (enough evenings with her per week, enough daily care) plus a few money-relevant events. Their narrative depth is out of scope here.
- **Game-time scaling:** real-world rates and throughput are kept; **payment delays are compressed** to fit a 42-day run, so that players see payments for work they actually played (§3.4).

## 2. Calendar and time

- 42 days, **day 1 = Monday**. 30 weekdays, 12 weekend days. The character may work weekends.
- **Time unit: 1 hour.**
- Default day: work 9:00–18:00 with a 1 h lunch (**8 work hours**), evening free, **8 h sleep** (23:00–07:00), ~2 h morning/evening routines.
- Default working time over the run ≈ **240 hours** (30 weekdays × 8 h).
- Sleep can be cut (min 4 h) at a cost (see §7).
- Interruptions during work hours remove **0–25%** of planned work time per day (tune); some are pleasant, some neutral, some cost money or create callbacks.
- Days 41–42: no new paid work starts (wrap-up / ending).

## 3. Work

### 3.1 Work types

| Type | Throughput (finished words/hour, incl. research & checking) | Rate ($/word, gross) | ≈ Gross $/hour | Notes |
|---|---|---|---|---|
| Standard translation (agency) | 310 | 0.10 | ~31 | The default bread-and-butter job |
| Standard translation (direct client) | 310 | 0.14 | ~43 | Rarer offers; fastest payment |
| Post-editing (MTPE) | 470 | 0.055 | ~26 | More words, less per word, lower hourly; share grows over the run ("the weather") |
| Rush job | 310 (×1.0) | base × 1.25 | +25% | Tight deadline; adds stress; often needs evening/weekend hours |
| Own book (literary) | **150** | — | ~0 (see 3.3) | Slow, careful work choosing words and phrases; restores stress |

Grounding: agencies expect roughly 2,000–3,000 finished words per day (≈310/h over 8 h); standard agency rates sit around $0.10–0.13/word; MTPE roughly $0.05–0.15 vs. $0.15–0.30 for full translation; a working estimate of ~450–500 words/hour post-editing vs. ~300–350 translating. Literary throughput (150 w/h) is a design assumption to tune.

**Net income:** apply **NET = 0.78** to all payments (≈22% set aside for taxes; tune). The game can show this as an automatic "tax jar" or simply pay net amounts.

### 3.2 Job offers

- Offers arrive on weekdays: **Poisson(1.3)/day** (tune), shown with size, rate, deadline and payment terms.
- Sizes:

| Size | Words | ≈ Hours (standard) | Share of offers |
|---|---|---|---|
| Small | 500–1,500 | 2–5 | 50% |
| Medium | 3,000–6,000 | 10–20 | 35% |
| Large | 10,000–20,000 | 32–65 | 15% |

- Deadline = estimated hours / 6 working days × uniform(1.1, 1.8), min 1 day (tune).
- Missing a deadline: −20% payment and a reputation hit (fewer/lower offers from that client for 7 days).
- **Story hook (fixed):** in week 2 or 3, the regular client switches to post-editing; from then on, the PE share of offers rises from ~25% to ~50% by week 6.
- Offers expire after 1 day if not accepted.

### 3.3 The book project (starts with progress)

- The character has been translating the book in spare time for months (since before the move). **At the start of the run, 60–75% of the book is already done** (random per run; tune).
- What remains are **the hard parts**: the chapters the character kept putting off. Which chapters remain can vary per run.
- **Size the remaining work by hours, not words:** finishing should take **60–80 hours** of book work (≈ a quarter to a third of a careful player's working time). At 150 w/h that is **≈9,000–12,000 words** remaining (derive per run from the starting progress).
- Split into **3 milestones** (≈ 20–27 h each).
- Pays nothing by default. Variant to simulate: **small advance**, $400 (gross) per milestone.
- Each book hour reduces stress (see §7). Each milestone grants an effect offer (see §8) and a story beat.
- "Book finished" = all 3 milestones by day 42.

### 3.4 Payment terms (compressed to game time)

| Client type | Share of jobs | Paid … after delivery |
|---|---|---|
| Direct client | 25% | 2–3 days |
| Standard agency | 50% | ~7 days |
| Slow agency | 25% | ~14 days |

- Additionally, **20% of payments arrive 3–7 days late** (tune).
- **Fixed story event (the one realistic delay):** a **large agency job taken in week 2** is paid only in **week 5** (≈ 3 weeks after delivery), landing in the convergence week alongside rent (day 31) and the vet bill. Its size should be large enough to matter (≈ 10,000–15,000 words; tune).
- Real-world reference (for flavor text only): agencies commonly pay at 30/45/60 days.

### 3.5 Pre-move receivables (fixed, story-tied)

Invoices for work done before the move, arriving during the run (amounts to be re-tuned; with faster payments they may be reduced):

| Day | Amount (net) |
|---|---|
| 6 | 600 (tune) |
| 13 | 900 (tune) |
| 24 | 500 (originally due day 18; arrives late) (tune) |

### 3.6 Feedback on delivery (separate from cash)

When a job is delivered, the player gets immediate feedback even though cash comes later:
- The client's reply (quality/tone reaction; occasionally a revision request).
- A reputation change with that client (affects future offers).
- The invoice appears in a visible **"money owed" list** with its expected payment date (and a late flag if overdue).

The simulation only needs the reputation effect; the rest is UI/narrative.

## 4. Costs

| Item | Amount | When |
|---|---|---|
| Rent (1-bedroom, ~US national average) | 1,500 | Day 1 (paid before start), **day 31** |
| Living costs (groceries, utilities, phone/internet, transport, insurance, misc.) | 48/day | Daily (game can bill weekly) |
| Pet food | 2/day | Daily; rises 50% after the first growth stage |
| Pet starter supplies | 250 | Day 1 |
| Vet: first exam + vaccines | 150 | Day 3 (fixed) |
| Vet: booster visits | 100 each | Days 17 and 31 (fixed) |
| Pet transformation/illness (week 5) | 300 / 500 / 800 (random; lower if pet care has been good) | ~Day 30 |
| Random small costs (breakages, a gift, a dinner out) | 20–150 | From events (~1 per 4 days) |

Grounding: one-bedroom national average ~$1,500–1,650/month; first puppy exam ~$50–150; puppy vaccines $75–200 per visit across several visits; emergency vet $280–1,750.

## 5. Starting state

- **Cash after day-1 rent: to be tuned.** Start the search at 2,000 and expect it to come down (likely ~1,200–1,600) because compressed payment terms speed up cash flow. See §9.3.
- **Book progress:** 60–75% done (§3.3).
- Stress: low. Relationship: good. Pet: baby, healthy.
- No effects at start (working style may be a starting effect; see §8).

## 6. Money crisis and bankruptcy

- **Crisis:** cash < 0 at the end of a day. The player gets lifelines (each usable once unless noted):
  1. **Borrow from her** (up to 800). Repayable; triggers a relationship event (how it's asked matters).
  2. **Ask a client to pay early** at −10% of that invoice.
  3. **Pay rent late** once, with a 75 late fee, up to 7 days.
- **Bankrupt:** cash < 0 with no lifeline left, **or** cash < −300 at any point. Bankruptcy is an ending path, not an immediate game over (tune).
- **End-of-run money value** = cash + 0.9 × outstanding receivables − debts. (Without counting receivables, work in the last days would be pointless.)

## 7. Stress (v0) and other time demands

### Stress
Internal 0–100 (shown per difficulty, see `STORY_CONCEPT_V2.md`). Daily change:

| Driver | Δ stress |
|---|---|
| Each paid work hour beyond 6 in a day | +2 |
| Each hour of sleep cut | +4 (and next-day efficiency −5% per hour cut) |
| Each consecutive short night (<7 h) after the first | +3 extra |
| A deadline due tomorrow with work remaining | +5 |
| Cash runway < 7 days of costs | +4/day |
| A rush job in progress | +2/day |
| Each leisure / time-with-her hour | −2 |
| Each book hour | −2.5 |
| A day with no paid work | −6 |
| Natural recovery | −3/day |

Efficiency multiplier from stress: **1.0** below 50; then **−1% per point above 50** (e.g. stress 80 → 0.70). Above 85 for 2+ days: illness risk 15%/day (lose a day's work; vet-style cost 0–80).

### Relationship (time demand, simulated)
- Needs **≥3 evenings with her per week (≥2 h each)**, or 2 evenings + a weekend half-day. She is only available evenings and weekends (office hours).
- A missed week → a negative relationship event; two in a row → strong negative.
- She has her own crunch in weeks 4–5: fewer available evenings (2/week), which makes each one more valuable.

### Pet care (time demand, simulated)
- Daily care: **2.5 h** (baby, days 1–13), **2 h** (days 14–27), **1.5 h** (days 28–42).
- Each day below need → raises the week-5 illness cost tier and the chance of small damage costs.

## 8. Effects (roguelike layer)

### 8.1 How effects are offered (mixed)
Each offer = **pick 1 of 3**, drawn at random from the pool (no duplicates of held effects).

| Source | When | Expected offers / run (careful player) |
|---|---|---|
| Weekly reflection (guaranteed) | End of weeks 1–5 | 5 |
| Work milestone (earned) | Every 4th completed paid job | ~2–3 |
| Book milestone (earned) | Each book milestone | 0–3 (only if pursued) |
| Shop (bought) | Always available; items cost money | 0–2 |

**Target: a careful player holds 7–9 effects by the end; a neglectful or narrowly focused one, 5–6.**

### 8.2 Sizing: why the timing matters
An effect's total value ≈ its strength × the work-days left after it's taken. Average efficiency boost over the run:

> avg boost ≈ Σ eᵢ × (42 − tᵢ) / 42

Example: four +10% efficiency effects taken on days 7, 14, 21, 28 → avg boost ≈ 0.10 × (35+28+21+14)/42 ≈ **+23%** over the run, ending at **+40%**.

Targets:
- **End-of-run efficiency boost** for a well-built character: **+30–50%**; average over the run: **+15–25%**.
- Early effects (weeks 1–2) are worth ~2–3× late ones. So **late offers (weeks 4–5) should lean toward stress, relationship, pet and one-off money effects** rather than efficiency, or be stronger.

### 8.3 Stacking rules
- Within a category, effects **add**; each category has a cap: efficiency **+40%**, rate **+25%**, stress-relief multipliers **+50%**.
- Categories **multiply** with each other.
- 2–3 **designed synergies** (named combos) are allowed above caps; nothing else may exceed them.

### 8.4 Starter pool (v0, sizes tunable)

| Effect | Category | Upside | Downside / cost |
|---|---|---|---|
| Deep focus | Efficiency (style) | +15% efficiency on days with only one paid project | −10% on days with 2+ projects |
| Context switcher | Efficiency (style) | +12% efficiency on days with 2+ different tasks | −8% on single-project days |
| Morning person | Efficiency | +15% efficiency for work before 13:00 | −10% after 19:00 |
| Night owl | Efficiency | +15% after 19:00 | Sleep cuts cost +1 stress/h more |
| Noise-cancelling headphones | Efficiency (shop) | Interruptions remove 30% less time | 120 |
| Coworking pass | Efficiency (shop) | +10% efficiency on days worked there; −50% pet interruptions | 60/week; pet alone more (care need +0.5 h) |
| CAT-tool subscription | Throughput | +15% throughput on standard & PE jobs | 30/week |
| Direct-client network | Rate | Direct-client offers ×2 | Direct clients request revisions (−1 h per job) |
| Fast invoicer | Cash flow | Slow-agency jobs (14 days) pay in ~7 days | −3% on those payments |
| Morning pages | Stress | −1 stress per day; book hours −3.5 instead of −2.5 | 30 min each morning |
| Walk routine | Pet / stress | Pet care hours also reduce stress (−1/h) | Walks can't be skipped without extra pet penalty |
| Her spreadsheet | Money / relationship | Shows exact upcoming cash low point | Unlocks only after an evening with her; she checks in on it |

## 9. Simulation spec (for the coding agent)

### 9.1 Build
- Python (or TypeScript), **seeded** RNG, deterministic per seed. No UI.
- One module per system: calendar, offers/jobs, payments, costs, stress, time demands, effects, lifelines, book.
- All numbers in one config file so they can be tuned without code changes.

### 9.2 Player strategies (policies) to simulate
Each policy also needs a simple effect-picking rule.

| Policy | Paid hours/weekday | Book | Her / pet | Sleep | Effect picks |
|---|---|---|---|---|---|
| **Careful** | 6–7 | ~1.5 h/day | Meets needs | Rarely cuts | Balanced (highest expected value) |
| **Book-heavy** | 4–5 | ~2.5 h/day | Meets needs | Rarely cuts | Stress/book-leaning |
| **Grinder** | 9–10 + weekends | None | Misses some | Cuts often | Efficiency/rate only |
| **Careless** | 5–6, accepts poorly | Occasional | Inconsistent | Random | Random |
| **Greedy-optimal** | Search-based: maximizes end money value | — | Ignores unless forced | — | Greedy |

Also run **every policy with no effects** as a control.

### 9.3 Runs
- 2,000 seeds per policy × {no effects, with effects} × {book unpaid, small advance}.
- **Starting-cash search first:** sweep starting cash from 800 to 2,400 in steps of 200 (and optionally the pre-move receivable amounts) and pick the value that best meets the acceptance targets in §9.5. Use that value for all other runs and report it.
- Then a **sensitivity sweep** (±25%) on: starting cash, rent, offer rate, PE share, payment delays, late-payment share, size of the week-2 story job, NET, effect sizes, book starting progress.

### 9.4 Metrics
- Bankruptcy rate; crisis rate (cash < 0 before lifelines); lifelines used.
- Day of lowest cash (distribution) and the lowest cash value.
- End money value (cash, receivables, debts).
- Days with stress > 70 (and in weeks 4–5 specifically); illness days.
- Relationship weeks missed; pet-care deficit days.
- Book milestones reached / book finished; book hours spent.
- Effects held at end; offers received by source; pick frequencies; effects over-represented in the top 10% of runs.
- Feedback cadence: median days between a job's delivery and its payment; number of payments received per week.

### 9.5 Acceptance targets (Normal difficulty, with effects)

| Policy | Target |
|---|---|
| Careful | Bankrupt ≤ 8%; lowest cash falls in days 28–35 in ≥ 60% of runs; book finished ≥ 30% |
| Book-heavy | Bankrupt 15–30%; book finished ≥ 70%. Risky, but viable |
| Grinder | Bankrupt ≤ 5%, but stress > 70 on ≥ 40% of days in weeks 4–5 **and** relationship needs missed ≥ 2 weeks |
| Careless | Bankrupt ≥ 60% |
| Greedy-optimal | Must not dominate on the combined ending: it should miss relationship/pet/stress thresholds |
| Effects | No single effect in > 70% of top-decile runs; no combo exceeds caps except designed synergies |
| Feedback | Every policy that works receives at least one payment in each of weeks 1–6 |

Note: an earlier quick pre-check (real-world 7/30/45-day terms, book from 15,000 words, no effects) is **no longer valid** for this version and should not be used as a reference.

### 9.6 Report
Write `SIM_REPORT.md` with:
1. The chosen starting cash (and receivable amounts, if changed) and why.
2. Summary table per policy (both with and without effects, both book variants).
3. Whether each acceptance target is met.
4. Charts: cash over time (median and 10th/90th percentile) per policy; distribution of the lowest-cash day.
5. Effects analysis: offers by source, held count, dominant effects or combos.
6. Sensitivity: which parameters move the results most.
7. **Recommended changes** to the config, with the expected effect of each, and a re-run with the recommendations applied.
8. Open issues found (degenerate strategies, dead effects, exploits).

## 10. Open items this spec does not settle

- Exact difficulty differences (suggested: Gentle +30% starting cash and fewer late payments; Hard −20% starting cash and more late payments).
- Whether the book has a small advance (simulate both).
- Narrative content of events; only their money/time/stress effects are modeled here.
- Currency and city (numbers can be scaled uniformly).

## Sources for the grounding figures

- ATA / ITI / University of Leeds rates surveys and industry summaries (per-word rates, MTPE vs. translation rates)
- ProZ.com forum polls and translator guides (daily output; real-world payment terms of 30/45/60 days and late payment)
- Authors Guild / PEN America (literary translation rates, ~13¢/word average)
- Apartments.com, Zumper, ApartmentAdvisor rent reports 2026 (one-bedroom ~$1,450–1,665)
- Petco, Rover, Pawlicy guides (puppy vet, vaccine and emergency costs)
