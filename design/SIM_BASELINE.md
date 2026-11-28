# Paws & Paychecks — Economy baseline & simulation spec (v0.3)

> Purpose: the starting numbers for the v2 financial system (money, time, effects), the ending rules the economy is balanced toward, and the spec for the simulation that tests them. Written so a coding agent can build and run the simulation and write a report without further input. Companion to `STORY_CONCEPT_V2.md` and `DECISIONS.md`.
>
> All numbers are **placeholders anchored in real-world data** (US dollars, US national averages, since the city is unspecified). They are meant to be tuned by the simulation, not treated as final. Anything marked **(tune)** is expected to move.
>
> **Changes in v0.3** (after the first simulation round, `sim/reports/SIM_REPORT.md`; see `DECISIONS.md`, 2026-11-27):
> - **Endings** are defined: five goals, tiers, and targets per strategy (§9). They replace the simulator's temporary "good combined ending".
> - **Bankruptcy becomes the parents' ending:** borrowing from her raises stress, and an unrepaid loan after 7 days ends the run (§6).
> - **Book:** no advance; remaining work varies only ±5% and is tuned to the ending targets; "near-finished" added (§3.4).
> - **Clients:** three regular clients with habits and fixed story commissions (§3.3). The week-2 story job comes from one of them and is declinable at a cost. A fixed day-1 job opens the run (§3.6).
> - **Taxes** fixed at 22% and removed from tuning (§4).
> - **Rush jobs** confirmed, with higher stress (§3.1, §7).
> - **Effects:** pool grows from 12 to 36 (30 offered + 6 shop). Efficiency effects are smaller. The CAT tool is weaker and pricier. Only a few effects help the book. A throughput cap and 3 designed synergies are added. Her spreadsheet becomes UI-only. Work-milestone offers come every 8th job (§8).
> - **Simulation:** the book-advance variant is replaced by a story-job variant; new acceptance targets; NET removed from the sweep; new sweep parameters (§10).

## 1. Design approach

- **The financial system is designed first**, with **time as the shared currency**. Stress, the relationship and the pet are not derived *from* money; they are coupled to it through time and efficiency:
  - Relationship and pet need **hours** (evenings with her, walks, play). Every hour they get is an hour not billed.
  - **Stress** is driven by workload, short sleep, deadlines, money anxiety and debt, and it feeds back into **working efficiency**.
  - Money pressure can **trigger** relationship events (e.g. borrowing from her), but the relationship is not a function of money.
- In the simulation, stress is modeled numerically; relationship and pet are modeled as **time demands with thresholds**, plus a few money-relevant events. Their narrative depth is out of scope here.
- **Game-time scaling:** real-world rates and throughput are kept; **payment delays are compressed** to fit a 42-day run (§3.5).
- **Balance is measured against the endings** (§9): neglect may pay in money, but it must cost in the ending.

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
| Rush job | 310 | base × 1.25 | +25% | **~15% of non-PE random offers**; deadline × 0.5; extra stress (§7) |
| Own book (literary) | **150** | — | 0 (no advance) | Slow, careful work choosing words and phrases; restores stress |

Grounding: agencies expect roughly 2,000–3,000 finished words per day (≈310/h over 8 h); standard agency rates sit around $0.10–0.13/word; MTPE roughly $0.05–0.15 vs. $0.15–0.30 for full translation; a working estimate of ~450–500 words/hour post-editing vs. ~300–350 translating. Literary throughput (150 w/h) is a design assumption.

### 3.2 Job offers (random)

- Random offers arrive on weekdays: **Poisson(0.9)/day** (tune). This is lower than v0.2's 1.3 because regular clients (§3.3) now add about 2.5 jobs a week. Offers show size, rate, deadline and payment terms.
- Sizes:

| Size | Words | ≈ Hours (standard) | Share of offers |
|---|---|---|---|
| Small | 500–1,500 | 2–5 | 50% |
| Medium | 3,000–6,000 | 10–20 | 35% |
| Large | 10,000–20,000 | 32–65 | 15% |

- Deadline = estimated hours / 6, in working days, × uniform(1.1, 1.8), min 1 day (tune). Rush: × 0.5.
- Missing a deadline: −20% payment and a reputation hit with that client type (offers from that type dropped with 50% chance and paid × 0.9 for 7 days).
- Offers expire after 1 day if not accepted.

### 3.3 Regular clients

Most clients are **types** (direct / standard agency / slow agency). On top of that, there are **three regular clients**. Each has its own habit, better terms, and fixed story commissions.

| Client | Type | Better terms (vs. its type) | Habit (random work) | Fixed story commissions |
|---|---|---|---|---|
| **A — the regular agency** | Standard agency | Pays in **5 days** (not 7); rate +10% | ~1 job/week, usually offered on Monday (±1 day); mostly medium | The **week-2 story job** (§3.6); A is the client that **switches to post-editing** in week 2–3 |
| **B — the direct client** | Direct | Rate +10% | ~1 small job/week, usually Thursday (±1 day) | The **day-1 job** (§3.6) |
| **C — the slow publisher-side agency** | Slow agency | Pays in **10 days** (not 14); rate +10% | ~1 medium or large job every 2 weeks, any weekday | None (v0.3) |

- Habit draws: each week, each regular client sends a job with the probability given (A 0.9, B 0.8, C 0.45/week; tune) on its usual day ±1.
- **Reputation counts double** for regular clients: a missed deadline drops their offers for **14 days**.
- **Post-editing switch:** client A's offers become PE from a day drawn uniformly in 8–21. Separately, the PE share of random offers rises from ~25% to ~50% by day 36 (as in v0.2).
- Individual habits can differ in the game. This table is the simulation baseline.

### 3.4 The book project

- The character has been translating the book in spare time for months. **What remains are the hard parts:** the chapters the character kept putting off.
- **Remaining work: H hours ± 5%** (random per run), at 150 w/h. **H starts at 70 h and is tuned** so the careful player finishes in ~40–50% of runs (§10.5). Report the chosen H, and the matching starting progress, for the story text.
- **3 milestones** of H/3 each. Each grants an effect offer (§8) and a story beat.
- **No advance.** The book pays nothing during the run.
- **Finished** = all 3 milestones by day 42. **Near-finished** = milestones 1–2 done and ≥ 50% of milestone 3. This counts toward the good ending ("finished it a month later") but not the best one (§9).
- Book hours reduce stress (§7). Only effects marked **📖** in §8.4 change book speed.

### 3.5 Payment terms (compressed to game time)

| Client type | Share of random jobs | Paid … after delivery |
|---|---|---|
| Direct client | 25% | 2–3 days |
| Standard agency | 50% | ~7 days |
| Slow agency | 25% | ~14 days |

- Regular clients pay per §3.3.
- **20% of payments arrive 3–7 days late** (drawn per job; tune).
- Real-world reference (for flavor text only): agencies commonly pay at 30/45/60 days.

### 3.6 Fixed jobs and pre-move receivables

**Fixed jobs**

| Job | Client | Offered | Size | Deadline | Paid |
|---|---|---|---|---|---|
| **Day-1 job** (also the tutorial) | B (direct) | Day 1 | 1,200 words (~4 h) | End of day 2 | 2 days after delivery (≈ day 4) |
| **Week-2 story job** | A (regular agency) | Day 8 | 12,500 words (tune) | Normal formula | Day 33, or 7 days after delivery if later |

- The day-1 job is **always taken** (tutorial).
- The week-2 story job is a **story choice that is hard to refuse**. In the game it is framed as a request from the regular client. **Declining** is allowed, but client A's offers drop by 50% for the rest of the run, and a story beat follows. Simulate both variants (§10.3).

**Pre-move receivables** (invoices for work done before the move; amounts tune):

| Day | Amount (net) |
|---|---|
| 6 | 600 |
| 13 | 900 |
| 24 | 500 (originally due day 18; arrives late) |

The first round's recommended move of the day-6 invoice to day 4 is **not** applied, because the day-1 job now covers week 1.

### 3.7 Feedback on delivery (separate from cash)

When a job is delivered, the player gets immediate feedback even though cash comes later:
- The client's reply (quality/tone reaction; occasionally a revision request).
- A reputation change with that client.
- The invoice appears in a visible **"money owed" list** with its expected payment date (and a late flag if overdue).

The simulation only needs the reputation effect; the rest is UI/narrative.

## 4. Costs and taxes

| Item | Amount | When |
|---|---|---|
| Rent (1-bedroom, ~US national average) | 1,500 | Day 1 (paid before start), **day 31** |
| Living costs (groceries, utilities, phone/internet, transport, insurance, misc.) | 48/day | Daily (game can bill weekly) |
| Pet food | 2/day | Daily; rises 50% after the first growth stage |
| Pet starter supplies | 250 | Day 1 |
| Vet: first exam + vaccines | 150 | Day 3 (fixed) |
| Vet: booster visits | 100 each | Days 17 and 31 (fixed) |
| Pet transformation/illness (week 5) | 300 / 500 / 800 (odds depend on pet care; keep the round-1 odds) | ~Day 30 |
| Random small costs (breakages, a gift, a dinner out) | 20–150 | From events (~1 per 4 days) |

**Taxes: fixed at 22%** (NET = 0.78 on all payments). This is **not a tuning lever**. Keep it out of the sensitivity sweep, except for one reference row. How the game shows it (net pay, a tax jar or a tax bill) is open.

## 5. Starting state

- **Cash after day-1 rent: re-search** (§10.3). Round 1 chose 1,400. v0.3 changes (day-1 job, regular clients, no book advance, smaller efficiency effects) will shift it.
- **Book:** H ± 5% hours remaining (§3.4).
- Stress: low. Relationship: good. Pet: baby, healthy.
- No effects at start.

## 6. Money crisis, the loan, and the parents' ending

- **Crisis:** cash < 0 at the end of a day. Lifelines, in this order (each once):
  1. **Pay rent late** (if rent fell due today): +75 fee, due within 7 days.
  2. **Ask a client to pay early:** −10% of the smallest job invoice that covers the gap.
  3. **Borrow from her:** up to 800 (shortfall + 200 buffer, within the max). This is the last lifeline.
- **The loan:**
  - Borrowing raises stress by **+15** at once, then **+3/day** until the loan is repaid.
  - It must be **repaid in full within 7 days** (Normal; 5 on Hard). In the game, she mentions it around day 5 (story beat; no mechanic).
  - Policies repay as soon as cash allows (keeping 2 days of costs).
- **The parents' ending** (replaces "bankrupt") happens when:
  - the loan isn't repaid by its deadline, **or**
  - cash is below **−300** at the end of a day with no lifeline left.

  The character's parents call and help. **The run ends that day** (ending tier: parents, §9). In the simulation, record the day and compute metrics up to it.
- **End-of-run money value** = cash + 0.9 × outstanding receivables − debts.

## 7. Stress (v0.3) and other time demands

### Stress
Internal 0–100 (shown per difficulty, see `STORY_CONCEPT_V2.md`). Daily change:

| Driver | Δ stress |
|---|---|
| Each paid work hour beyond 6 in a day | +2 |
| Each hour of sleep cut | +4 (and next-day efficiency −5% per hour cut) |
| Each consecutive short night (<7 h) after the first | +3 extra |
| A job due tomorrow with work remaining | +5 per job (**+8** if it's a rush job) |
| Cash runway < 7 days of costs | +4/day |
| **A rush job in progress** | **+3/day** (was +2) |
| **Borrowing from her** | **+15** once, then **+3/day until repaid** |
| Each leisure / time-with-her hour | −2 (leisure counted up to 4 h/day; keep the round-1 rule) |
| Each book hour | −2.5 |
| A day with no paid work | −6 |
| Natural recovery | −3/day |

Efficiency multiplier from stress: **1.0** below 50, then **−1% per point above 50**. Above 85 for 2+ days: illness risk 15%/day (lose a day's work; cost 0–80).

### Relationship (time demand)
- Needs **≥3 evenings with her per week (≥2 h each)**, or 2 evenings + a weekend half-day (≥4 h). She is only available evenings and weekends.
- Her crunch in weeks 4–5: 2 free evenings a week.
- A missed week → a negative relationship event.

### Pet care (time demand)
- Daily care: **2.5 h** (days 1–13), **2 h** (days 14–27), **1.5 h** (days 28–42).
- Each day below need is a **deficit day**. Deficit days raise the week-5 bill tier and the chance of small damage costs (25% per deficit day, $20–150).

## 8. Effects (roguelike layer)

### 8.1 How effects are offered (mixed)
Each offer = **pick 1 of 3**, drawn at random from the offerable pool (no duplicates of held effects).

| Source | When | Expected offers / run (careful player) |
|---|---|---|
| Weekly reflection (guaranteed) | End of weeks 1–5 | 5 |
| Work milestone (earned) | **Every 8th completed paid job** (was every 4th) | ~2–3 |
| Book milestone (earned) | Each book milestone | 0–3 (only if pursued) |
| Shop (bought) | Always available; items cost money | 0–2 |

**Target:** a careful player holds **7–9** effects by the end; a neglectful or narrowly focused one, **5–6**.

### 8.2 Sizing
An effect's total value ≈ its strength × the work-days left after it's taken:

> avg boost ≈ Σ eᵢ × (42 − tᵢ) / 42

Efficiency effects are **individually smaller** in v0.3 (mostly +5–8%), so less work time is needed to earn the same money. Targets for a well-built careful character (tune):
- average effect boost on paid work over the run: **+10–20%** (was +15–25%);
- in the last 5 workdays: **+20–35%** (was +30–50%).

Early effects are worth more than late ones. From day 22, efficiency and throughput effects are drawn at half weight (keep the round-1 rule).

### 8.3 Categories, caps and synergies
- Within a category, bonuses **add**, up to a cap. Categories **multiply** with each other.

| Category | Cap |
|---|---|
| efficiency | +40% |
| throughput (new) | +15% |
| rate | +25% |
| stress_relief (multipliers) | +50% |
| book (book speed, new) | +20% |

- **Designed synergies** (v0.3) may go above the caps. When both effects are held:

| Synergy | Effects | Bonus |
|---|---|---|
| **The quiet house** | Deep focus + Noise-cancelling headphones | +4% efficiency on single-project days, above the cap |
| **First audience** | Reading aloud + Walk routine | Reading aloud's pet-care overlap rises from 0.5 to 1 h/day |
| **Steady hands** | Loyal client + Termbase | Regular clients pay 2 days faster |

### 8.4 The pool (v0.3: 36 effects = 30 offered + 6 shop)

Legend: **📖** = changes book speed. **(shop)** = bought, never drawn in offers. "Time" means the effect takes hours from the day; take them from free time first, then from paid time.

**Work style and efficiency** (efficiency cap +40%)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| deep_focus | Deep focus 📖 | +8% efficiency (paid **and** book) on days with only one paid project | −6% on days with 2+ paid projects |
| context_switcher | Context switcher | +7% efficiency on days with 2+ tasks (paid projects + book) | −5% on single-task days |
| morning_person | Morning person | +8% on the first 4 work hours | −6% on work hours beyond 8 |
| night_owl | Night owl | +10% on work hours beyond 8 (evenings) | −5% on the first 4 work hours |
| pomodoro | Pomodoro timer | +6% on days with ≤ 7 paid hours | −6% on paid hours beyond 8 |
| sunday_planning | Sunday planning | +5% efficiency all next week | 1 h every Sunday (time) |
| coworking | Coworking pass (shop) | +6% on days worked there; −50% pet interruptions | 60/week from purchase; +0.5 h pet care on those days |
| headphones | Noise-cancelling headphones (shop) | Interruptions remove 30% less time (paid and book) | 120 once |

**Throughput** (throughput cap +15%)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| cat_tool | CAT-tool subscription | **+10%** throughput on standard & PE jobs (was +15%) | **60/week** (was 30; tune toward the pick-rate target) |
| second_monitor | Second monitor (shop) | +5% throughput on standard jobs | 180 once |
| termbase | Termbase | +8% throughput on regular-client jobs | The first job from each regular client after taking it costs +2 h |
| pe_veteran | Post-editing veteran 📖 | +15% throughput on PE jobs | −4% efficiency on standard translation; **−5% book speed** ("the machine's voice creeps in") |

**Rate and clients** (rate cap +25%)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| direct_network | Direct-client network | Direct-client random offers ×2 | +1 h unpaid revision per direct job |
| specialist_niche | Specialist niche | +15% rate on standard translation | Random offers −20% |
| rush_specialist | Rush specialist | Rush offers ×2; rush rate ×1.4 (not 1.25) | Rush jobs add +2 stress/day more |
| loyal_client | Loyal client | Regular clients send +50% more jobs | −10% rate on regular-client jobs (loyalty discount) |

**Cash flow and money**

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| fast_invoicer | Fast invoicer | Slow-agency jobs (14 days) pay in 7 days (**no fee**, was −3%) | 0.5 h of admin every Monday (time) |
| invoice_reminders | Invoice reminders | Late payments arrive half as late (rounded up) | A missed deadline for a regular client drops their offers for 21 days (not 14) |
| deposit_terms | Deposit terms | Large jobs pay 30% on acceptance (rest on normal terms) | Large-job offers −25% |
| side_class | Saturday class | +100 net every Saturday | 4 h every Saturday (time; counts as paid hours for stress) |
| frugal_cooking | Frugal cooking | Living costs −6/day | 0.5 h/day (time) |

**Stress and rest** (stress_relief cap +50%)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| morning_pages | Morning pages | −1 stress/day; book hours relieve 3.5 (not 2.5) | 0.5 h every morning (time) |
| nap_habit | Afternoon nap | On days with stress > 50: a 1 h nap gives −5 stress | That 1 h (time) |
| boundaries | Work boundaries | Leisure relieves ×1.2; −1 stress/day | No paid work after 19:00 (hours beyond 8 impossible) |
| standing_desk | Standing desk (shop) | Paid hours beyond 6 add +1 stress each (not +2) | 150 once |

**Her** (relationship)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| shared_calendar | Shared calendar | In her crunch weeks she has 3 free evenings (not 2) | A planned evening that is skipped counts as a missed week |
| sunday_brunch | Sunday brunch | A 3 h weekend slot counts as a half-day (not 4 h) | 25 per brunch |
| quiet_company | Quiet company 📖 | Up to 1 h of book per evening with her counts for both | Those hours relieve −1 stress (not −2) |
| evening_walks | Evening walks together | Up to 1 h/day of pet care can overlap with time with her | Pet care need +0.25 h/day |

**The creature** (pet)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| walk_routine | Walk routine | Pet care hours also reduce stress (−1/h) | A skipped walk counts as 2 deficit days |
| reading_aloud | Reading aloud 📖 | Up to 0.5 h/day of book time also counts as pet care; book hours relieve +0.5 more | Book speed −10% during those hours |
| neighbor_sitter | The neighbor | Once a week, one day's pet care need can be covered | 25 per use, or 2 h of help on Sunday |
| puppy_class | Puppy class (shop) | Pet care need −0.5 h/day from day 14 | 120 once; 2 h every Saturday in weeks 2–4 |
| sturdy_toys | Sturdy toys (shop) | Pet damage chance halved | 40 once |

**The book** (book cap +20%)

| Id | Effect | Upside | Downside / cost |
|---|---|---|---|
| margin_notes | Old margin notes 📖 | +8% book speed | Book hours relieve 2 (not 2.5) |
| writing_group | Writing group 📖 | Once a week, a 2 h book session that evening: +10% book speed that week, and the session relieves double | The session takes one evening (it can't be with her) |

**Not in the pool:** **Her spreadsheet** is a story and UI feature with no mechanical effect: it helps the player see the character's state and upcoming cash. In the game, it is unlocked by a story event (an evening with her), not by a pick. Remove it from the simulation's offer pool.

### 8.5 Notes for implementation
- Effects that need data the simulator lacks (e.g. "the first job from each regular client") should use the simplest reading. Log it under "Implementation" in `DECISIONS.md` and in the report's open issues.
- **Policy pick rules** must handle the new effects. Value-based policies can use hand-set weights per effect in `data/policies.yaml` or a short look-ahead. Document the method.
- Effects held by **0% of runs** across all policies, or picked **< 10% of the time** when offered by every policy, are "dead". Report them.

## 9. Endings

### 9.1 The five goals (simulation definitions; tune)

| Goal | Met when |
|---|---|
| **Pet kept** | ≤ 4 pet-care deficit days over the run |
| **Relationship good** | ≤ 1 week of relationship needs missed, never 2 weeks in a row, and any loan from her repaid on time |
| **Book finished** | All 3 milestones by day 42 (near-finished: see §3.4) |
| **Stress low/medium** | Average stress over days 36–42 ≤ 60, **and** ≤ 6 days with stress > 70 over the run |
| **Finances good** | Not the parents' ending, no debt left, end money value ≥ **1,500** (≈ one month's rent). "Okay" = solvent but below 1,500 |

### 9.2 Ending tiers

| Tier | Condition |
|---|---|
| **Parents' ending** | Triggered as in §6; overrides everything else |
| **Best** | All five goals met |
| **Good** | Pet, relationship, stress and finances all met; book **not** finished (near-finished or not) |
| **Mixed** | At least 3 of the 5 goals met, but not Best or Good |
| **Hard** | 2 or fewer goals met |

Which goals are missed shapes the ending's text. That's a writing task; the simulation reports the counts.

### 9.3 Targets (Normal difficulty)

| Policy | Finishes book | Best | Good or better | Parents' ending |
|---|---|---|---|---|
| Careful | ~40–50% | ~25–35% | ~70–80% | ≤ 8% |
| Book-heavy | ~85–95% | ~45–55% | ~60–70% | 15–30% |
| Grinder | ~0% | 0% | ≤ 10% | ≤ 5% |
| Careless | ~0–5% | ~0% | ≤ 10% | ≥ 60% |
| Greedy-optimal | — | 0% | 0% | — |

Planned difficulty spread (not simulated yet): careful's best-ending rate ~45% on Gentle, ~30% on Normal, ~15% on Hard.

## 10. Simulation spec (for the coding agent)

### 10.1 Build
- Extend the existing simulator in `sim/`. Keep it seeded and deterministic. All numbers stay in `data/economy.yaml` (economy) and `data/policies.yaml` (player behaviour).
- New or changed systems: regular clients and habits, fixed jobs, the loan and the parents' ending, endings, the new effects, categories, caps and synergies.
- **Apply** from round 1's `data/economy.recommended.yaml` only `work_milestone_every: 8`. Don't apply the day-6 → day-4 invoice move or the starting cash of 1,450 (both superseded). Then delete the overlay file.

### 10.2 Player strategies (policies)
Keep the five policies and their definitions from round 1 (`data/policies.yaml`), with these changes:
- All policies repay her loan as soon as cash allows (§6).
- All policies take the day-1 job.
- The story job is handled per variant (§10.3).
- Update the effect-pick rules for the new pool (§8.5).
- Don't change the policies' book hours to hit the book target. Tune H (§3.4) instead.

### 10.3 Runs
- **Starting-cash search first:** sweep 800–2,400 in steps of 100. Pick the value that best meets the §10.5 targets. Then **tune H** for careful's book-finish target, re-check starting cash once, and report both.
- **Main runs:** 2,000 seeds per policy × {effects, no effects} × {story job always taken, story job declinable}.
- **Sensitivity sweep** (±25%): starting cash, rent, random offer rate, regular-client job rate, regular-client terms (rate bonus, payment days), PE share, payment delays, late-payment share, story job size, effect sizes, book remaining hours H, leisure cap, loan repayment window (5 / 7 / 9 days), parents'-ending cash floor, transformation-bill odds. **Not NET** (fixed; one reference row only).

### 10.4 Metrics
- Ending tier distribution per policy; goal-by-goal success rates; the most common missed goal per policy.
- Parents' ending rate and day; crisis rate; lifelines used; loan taken / repaid on time.
- Lowest cash day (distribution) and value; end money value (cash, receivables, debts); finance tier (good / okay).
- Stress: days > 70, average in days 36–42; illness days.
- Relationship weeks missed; pet deficit days.
- Book: milestones, finished, near-finished, hours.
- Effects: held at end; offers by source; pick rates; share held in all runs vs. top decile; dead effects; synergy frequency; cap hits per category.
- Regular clients: jobs per client per run; story job accepted (declinable variant).
- Feedback cadence: job payments per week (day-1 job included; pre-move invoices excluded).

### 10.5 Acceptance targets (Normal, with effects, story job declinable)

| Area | Target |
|---|---|
| Endings | The §9.3 table (finishes book, best, good or better, parents' ending) |
| Careful | Lowest cash in days 28–35 in ≥ 60% of runs |
| Effects | Careful holds 7–9 at the end, grinder/careless 5–6 or the policy's natural count (report); no single effect in > 70% of top-decile runs for any policy; CAT tool picked 40–60% of the time when offered by careful; no dead effects (§8.5) |
| Effect boost | Careful: average +10–20%, last 5 workdays +20–35% |
| Feedback | Careful, book-heavy and grinder each get at least one **job** payment in each of weeks 1–6 in ≥ 90% of runs |
| Story job | Accepted by careful in ≥ 70% of runs (declinable variant); if lower, report why |

Also report the "always taken" variant against the same targets.

### 10.6 Report
- Rename the round-1 report to `sim/reports/SIM_REPORT_round1.md` (and its charts) before writing the new `sim/reports/SIM_REPORT.md`.
- Same structure as round 1. Add:
  - an **ending section**: tier distribution, goal rates, and the most common missed goal per policy;
  - a **comparison with round 1** (what changed and why);
  - the chosen starting cash, H and implied starting progress, and any CAT price change.
- End with recommended config changes (as an overlay file, not merged), a re-run with them applied, and open issues needing owner decisions.

## 11. Open items this spec does not settle

- How taxes are shown (net pay, a tax jar or a tax bill).
- Exact difficulty differences (Gentle / Hard): starting cash, late payments, loan window (5 days on Hard is decided).
- Individual habits for regular clients beyond the baseline; more fixed story commissions.
- Narrative content of events and endings; only their money/time/stress effects are modeled here.
- Currency and city (numbers can be scaled uniformly).

## Sources for the grounding figures

- ATA / ITI / University of Leeds rates surveys and industry summaries (per-word rates, MTPE vs. translation rates)
- ProZ.com forum polls and translator guides (daily output; real-world payment terms of 30/45/60 days and late payment)
- Authors Guild / PEN America (literary translation rates, ~13¢/word average)
- Apartments.com, Zumper, ApartmentAdvisor rent reports 2026 (one-bedroom ~$1,450–1,665)
- Petco, Rover, Pawlicy guides (puppy vet, vaccine and emergency costs)