# Paws & Paychecks — Economy baseline & simulation spec (v0.4)

> Purpose: the starting numbers for the v2 financial system (money, time, stress, effects), the ending rules the economy is balanced toward, and the spec for the simulation that tests them. Written so a coding agent can build and run the simulation and write a report without further input. Companion to `STORY_CONCEPT_V2.md` and `DECISIONS.md`.
>
> All numbers are **placeholders anchored in real-world data** (US dollars, US national averages, since the city is unspecified). They are meant to be tuned by the simulation, not treated as final. Anything marked **(tune)** is expected to move.
>
> **Changes in v0.4** (after round 2, `sim/reports/SIM_REPORT.md`; see `DECISIONS.md`, 2026-11-27):
> - **Stress has two layers:** short-term (S) and long-term (L), with S converting into L when it runs too high or too long. Total = S + L. Explicit stress targets (§7).
> - **Money:** the "finances good" bar drops to about two weeks of living costs (plus no debt). The loan is capped at $400 and the parents' floor is −$100. A loan still open on day 42 gives a new **"poor"** money tier instead of the parents' ending (§6, §9).
> - **New "imperfect careful" policy.** The careful ending targets now apply to it; the old careful policy stays as an "ideal" reference (§10.2).
> - **Book-heavy targets** restated (finishes ≥ 95%; good or better = best) (§9.3).
> - **Story job** shrinks to ~9,000 words; feedback target 80% (§3.6, §10.5).
> - **Effects:** a "skip" choice on every offer; work-milestone offers every 12th job; effect-boost targets restated; fixes to the Saturday class, deposit terms, the neighbor and Sunday brunch; stress effects mapped to S or L; stress-relief cap +30%; shop buys judged by value (§8).
> - **Round-2 overlay:** partly applied (§10.1).
> - **Carried over from round 2:** H = 67.5 h and the CAT tool at $55/week (re-check both). The book is self-initiated and paid only after the game ends (`DECISIONS.md`).

## 1. Design approach

- **The financial system is designed first**, with **time as the shared currency**. Stress, the relationship and the pet are not derived *from* money; they are coupled to it through time and efficiency:
  - Relationship and pet need **hours** (evenings with her, walks, play). Every hour they get is an hour not billed.
  - **Stress** has a short-term layer (workload, sleep, deadlines, emotions) and a long-term layer (money situation, debt, relationship, the future). It feeds back into **working efficiency** (§7).
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
- Interruptions during work hours remove **0–25%** of planned work time per day (tune); some are pleasant, some neutral, some cost money, add stress or create callbacks.
- Days 41–42: no new paid work starts (wrap-up / ending).

## 3. Work

### 3.1 Work types

| Type | Throughput (finished words/hour, incl. research & checking) | Rate ($/word, gross) | ≈ Gross $/hour | Notes |
|---|---|---|---|---|
| Standard translation (agency) | 310 | 0.10 | ~31 | The default bread-and-butter job |
| Standard translation (direct client) | 310 | 0.14 | ~43 | Rarer offers; fastest payment |
| Post-editing (MTPE) | 470 | 0.055 | ~26 | More words, less per word, lower hourly; share grows over the run ("the weather") |
| Rush job | 310 | base × 1.25 | +25% | ~15% of non-PE random offers; deadline × 0.5; extra stress (§7) |
| Own book (literary) | 150 | — | 0 during the run | Slow, careful work choosing words and phrases; relieves stress. Self-initiated; paid only after the game ends |

Grounding: agencies expect roughly 2,000–3,000 finished words per day (≈310/h over 8 h); standard agency rates sit around $0.10–0.13/word; MTPE roughly $0.05–0.15 vs. $0.15–0.30 for full translation; a working estimate of ~450–500 words/hour post-editing vs. ~300–350 translating. Literary throughput (150 w/h) is a design assumption.

### 3.2 Job offers (random)

- Random offers arrive on weekdays: **Poisson(0.9)/day** (tune). Offers show size, rate, deadline and payment terms.
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

Unchanged from v0.3. Most clients are **types**; three **regular clients** have habits, better terms and fixed story commissions.

| Client | Type | Better terms (vs. its type) | Habit (random work) | Fixed story commissions |
|---|---|---|---|---|
| **A — the regular agency** | Standard agency | Pays in 5 days; rate +10% | ~1 job/week, usually Monday (±1 day); mostly medium | The week-2 story job (§3.6); switches to post-editing in week 2–3 |
| **B — the direct client** | Direct | Rate +10% | ~1 small job/week, usually Thursday (±1 day) | The day-1 job (§3.6) |
| **C — the slow publisher-side agency** | Slow agency | Pays in 10 days; rate +10% | ~1 medium or large job every 2 weeks | None |

- Weekly habit chance: A 0.9, B 0.8, C 0.45 (tune). Reputation counts double: a missed deadline drops their offers for 14 days.
- A's offers become PE from a day drawn uniformly in 8–21. The PE share of random offers rises from ~25% to ~50% by day 36.

### 3.4 The book project

- Self-initiated (no contract). If finished, it is paid **after the game ends**; no book money enters the run.
- **What remains are the hard parts.** Remaining work: **H hours ± 5%** per run, at 150 w/h. Round 2 tuned **H = 67.5 h**; **re-tune** for the imperfect careful policy (§10.3).
- **3 milestones** of H/3. Each grants an effect offer (§8), a story beat, and **long-term stress relief** (§7).
- **Finished** = all 3 milestones by day 42. **Near-finished** = milestones 1–2 done and ≥ 50% of milestone 3 ("finished it a month later"; counts toward the good ending, not the best).
- Book hours relieve short-term stress (§7). Only effects marked **📖** in §8.4 change book speed.

### 3.5 Payment terms (compressed to game time)

| Client type | Share of random jobs | Paid … after delivery |
|---|---|---|
| Direct client | 25% | 2–3 days |
| Standard agency | 50% | ~7 days |
| Slow agency | 25% | ~14 days |

- Regular clients pay per §3.3. **20% of payments arrive 3–7 days late** (tune).

### 3.6 Fixed jobs and pre-move receivables

| Job | Client | Offered | Size | Deadline | Paid |
|---|---|---|---|---|---|
| **Day-1 job** (also the tutorial) | B (direct) | Day 1 | 1,200 words (~4 h) | End of day 2 | 2 days after delivery (≈ day 4) |
| **Week-2 story job** | A (regular agency) | Day 8 | **9,000 words** (was 12,500; tune) | Normal formula | Day 33, or 7 days after delivery if later |

- The day-1 job is always taken. The story job is **hard to refuse but declinable**. Declining drops client A's offers by 50% for the rest of the run. The squeeze in weeks 2–4 is intended; the smaller size leaves room for small jobs around it.

**Pre-move receivables** (net): 600 on day 6, 900 on day 13, 500 on day 24 (originally due day 18). Amounts tune.

### 3.7 Feedback on delivery

On delivery: the client's reply, a reputation change, and the invoice in a visible **"money owed" list** with its expected date. The simulation only needs the reputation effect.

## 4. Costs and taxes

| Item | Amount | When |
|---|---|---|
| Rent (1-bedroom, ~US national average) | 1,500 | Day 1 (paid before start), **day 31** |
| Living costs (groceries, utilities, phone/internet, transport, insurance, misc.) | 48/day | Daily |
| Pet food | 2/day | Daily; +50% after the first growth stage |
| Pet starter supplies | 250 | Day 1 |
| Vet: first exam + vaccines | 150 | Day 3 |
| Vet: booster visits | 100 each | Days 17 and 31 |
| Pet transformation/illness (week 5) | 300 / 500 / 800 (odds depend on pet care; round-1 odds) | ~Day 30 |
| Random small costs | 20–150 | From events (~1 per 4 days) |

**Taxes: fixed at 22%** (NET = 0.78). Not a tuning lever; reference row only in the sweep. Presentation still open.

## 5. Starting state

- **Cash after day-1 rent: re-search** (§10.3). Round 2 chose 1,900 under the old finance bar; the lower bar and smaller loan will move it down. The round-2 probe met both book-heavy's best and careless's parents' targets at ~1,200.
- **Book:** H ± 5% hours remaining.
- **Stress:** S = 5, L = 10 (the move has just happened; tune).
- Relationship: good. Pet: baby, healthy. No effects.

## 6. Money crisis, the loan, and the parents' ending

- **Crisis:** cash < 0 at the end of a day. Lifelines, in this order (each once):
  1. **Pay rent late** (if rent fell due today): +75 fee, due within 7 days.
  2. **Ask a client to pay early:** −10% of the smallest job invoice that covers the gap.
  3. **Borrow from her:** up to **400** (was 800). Shortfall + 200 buffer, within the max. The last lifeline.
- **The loan:**
  - Borrowing: **+10 S** at once (the sting of asking), then **+2 L/day** while it is open (§7).
  - **Repaying it in full: −10 L** (relief).
  - Due **7 days** after borrowing (Normal; 5 on Hard). Policies repay as soon as cash allows, keeping 2 days of costs.
- **The parents' ending** (the run ends that day) happens when:
  - the loan comes due **during the run** and isn't repaid, **or**
  - cash is below **−100** (was −300) at the end of a day with no lifeline left.
- **A loan still open on day 42** (due after the run) does **not** trigger the parents' ending. It puts finances in the **"poor"** tier (§9.1), and the ending text acknowledges that the character still owes her. Deferred rent still unpaid on day 42 counts the same way.
- **End-of-run money value** = cash + 0.9 × outstanding receivables − debts.

## 7. Stress (v0.4: two layers)

### 7.1 The two layers

| Layer | What it represents | Speed | Range |
|---|---|---|---|
| **Short-term stress (S)** | Exhaustion, late nights, deadlines, temporary emotions | Rises and falls quickly | 0–100 |
| **Long-term stress (L)** | The character's situation: money, debt, the relationship, the creature's health, career, expectations of the future | Changes slowly; reduced mainly by resolving causes | 0–100 |

**Total stress T = min(100, S + L).** Efficiency, illness and the stress goal use T; the stress goal also checks L (§9.1).

### 7.2 Short-term stress (S)

| Driver | Δ S |
|---|---|
| Each paid work hour beyond 6 in a day | +2 |
| Each hour of sleep cut | +4 (and next-day efficiency −5% per hour cut) |
| Each consecutive short night (< 7 h) after the first | +3 extra |
| A job due tomorrow with work remaining | +5 per job (+8 if rush) |
| A rush job in progress | +3/day |
| Borrowing from her | +10 once |
| A bad interruption (about 1 in 4 interruptions; tune) | +2 |
| **Sleep** (applied each night, after the day's changes) | **−30% of S** with ≥ 8 h; **−15%** with a short night (tune) |
| Leisure | −2/h for the first 2 h, then −1/h (leisure counted up to 4 h/day) |
| Time with her | −2/h |
| Book hours | −2/h (was −2.5) |
| A day with no paid work | −6 |

### 7.3 Long-term stress (L)

| Driver | Δ L |
|---|---|
| Cash runway < 14 days of costs | +1/day |
| Cash runway < 7 days of costs | +2/day (instead of +1) |
| Rent due within 5 days and cash below the rent | +2/day |
| Her loan open | +2/day |
| A missed week with her (needs not met) | +6 once |
| Her crunch weeks (4–5) | +1/day |
| Each pet-care deficit day | +1 |
| The creature's week-5 illness/transformation | +8 when it starts; −4 when the bill is paid |
| Client A switches to post-editing ("the weather") | +5 once |
| A payment arrives late | +3 once |
| **A payment arrives** | −2 (at most −4/day) |
| **Rent paid** | −5 |
| **Loan repaid** | −10 |
| **A good week with her** (needs met) | −3 at the end of the week |
| **A book milestone** | −8 |
| **Calm-day recovery** (only on days ending with S < 40) | −1 |

### 7.4 Conversion: S becomes L

- **Too much:** at the end of a day, if S > **60**, **25%** of the excess (S − 60) moves from S to L.
- **For too long:** if S > **45** for **3 or more days in a row**, L gains **+2/day** from the third day.

(Both tune.)

### 7.5 Effects of stress
- Efficiency: 1.0 while T ≤ 50, then −1% per point of T above 50.
- Illness: T > 85 for 2+ days → 15%/day chance of an illness day (no work; cost 0–80).

### 7.6 Stress targets (tune the stress parameters to hit these)

| Policy | Target |
|---|---|
| Imperfect careful | Average T over the run 25–40; median of its highest T in days 29–35 between 55 and 75; misses the stress goal in 10–15% of runs |
| Ideal careful (reference) | Average T 15–35; meets the stress goal in ≥ 95% of runs |
| Book-heavy | Average T 20–40 (money worries in L) |
| Grinder | L ≥ 40 on day 42 in ≥ 80% of runs; fails the stress goal in ≥ 80% of runs |

Tunable stress parameters, in suggested order: sleep recovery shares, conversion threshold and rate, L load sizes (runway, rent, crunch), L relief sizes. Keep the drivers' structure.

### 7.7 Relationship and pet (time demands, unchanged)
- **Her:** ≥ 3 evenings (≥ 2 h) per week, or 2 evenings + a weekend half-day (≥ 4 h). Only evenings and weekends. Crunch weeks 4–5: 2 free evenings a week.
- **Pet care:** 2.5 h/day (days 1–13), 2 h (14–27), 1.5 h (28–42). A day below need is a deficit day (raises the week-5 bill tier; 25% chance of a $20–150 damage cost).

## 8. Effects (roguelike layer)

### 8.1 How effects are offered
Each offer = **pick 1 of 3, or skip**.
- **Skip** gives **−3 L** (keeping life simple; tune). Because every effect has a downside, skipping is a real choice. Report the skip rate per policy.
- Drawn at random from the offerable pool, with no duplicates of held effects. From day 22, efficiency and throughput effects are drawn at half weight.

| Source | When | Expected offers / run (careful) |
|---|---|---|
| Weekly reflection (guaranteed) | End of weeks 1–5 | 5 |
| Work milestone (earned) | **Every 12th completed paid job** (was 8th) | ~1–2 |
| Book milestone (earned) | Each book milestone | 0–3 |
| Shop (bought) | Always available | 0–2 |

**Target:** careful (imperfect) holds **7–9** effects at the end; neglectful or narrow policies, report their natural count.

### 8.2 Sizing
Efficiency effects are deliberately small (mostly +5–8%). **Effect-boost targets** (restated for the smaller effects), for the imperfect careful policy: average **+5–12%** over the run, **+10–20%** in the last 5 workdays.

### 8.3 Categories, caps and synergies

| Category | Cap |
|---|---|
| efficiency | +40% |
| throughput | +15% |
| rate | +25% |
| stress_relief (multipliers on S relief) | **+30%** (was +50%) |
| book (book speed) | +20% |

Synergies (may exceed caps), unchanged: **The quiet house** (deep focus + headphones: +4% efficiency on single-project days), **First audience** (reading aloud + walk routine: pet-care overlap 0.5 → 1 h/day), **Steady hands** (loyal client + termbase: regular clients pay 2 days faster).

### 8.4 The pool (36 effects = 30 offered + 6 shop)

As in v0.3, with these changes. All other effects keep their v0.3 definitions (in `data/economy.yaml`).

**Changed effects**

| Id | Change | Why (round 2) |
|---|---|---|
| side_class (Saturday class) | +100 → **+60** net per Saturday | Picked ~97%; in 86% of careful's top decile |
| deposit_terms | 30% on acceptance for **medium and large** jobs (was large only); **no offer penalty** (was −25% large offers). New downside: the remaining 70% is paid 3 days later than normal | Dead (picked < 10% by every policy) |
| neighbor_sitter (the neighbor) | No money cost. Cost: **2 h of help the following Sunday** (time), per use | Dead at $25/use |
| sunday_brunch | A **2 h** weekend slot counts as a half-day (was 3 h); 25 per brunch | Nearly dead (10%) |

**Stress effects mapped to the two layers**

| Id | v0.4 mechanic |
|---|---|
| morning_pages | −1 S/day **and −0.5 L/day** ("processing"); book hours relieve S by 3 (not 2); 0.5 h each morning |
| nap_habit | On days starting with S > 50: a 1 h nap gives −5 S |
| boundaries | Leisure S relief × 1.2; −1 S/day; no paid work after 19:00 (max 8 paid h/day) |
| standing_desk (shop) | Paid hours beyond 6 add +1 S each (not +2); 150 once |
| walk_routine | Pet-care hours also relieve S (−1/h); a skipped walk counts as 2 deficit days |
| reading_aloud | Book hours relieve +0.5 S more; up to 0.5 h/day of book time also counts as pet care; book speed −10% during those hours |
| margin_notes | +8% book speed; book hours relieve S by 1.5 (not 2) |
| writing_group | Weekly 2 h evening book session: +10% book speed that week; the session's S relief is doubled (within the cap) |
| quiet_company | Up to 1 h of book per evening with her counts for both; those hours relieve −1 S (not −2) |
| rush_specialist | Downside: rush jobs add +2 S/day more |

Effects that touch **L directly** are deliberately rare (morning pages, plus the skip choice): long-term stress should mostly move through the situation itself.

**Not in the pool:** her spreadsheet (story/UI only; unlocked by an evening with her).

### 8.5 Implementation notes
- Use the simplest reading where the spec is short; log choices under "Implementation" in `DECISIONS.md` and in the report.
- **Shop buys are judged by value**, like picks: a policy buys an item when its estimated value (the same `effect_value` estimate and weights) exceeds its price. This replaces round 2's fixed cash-threshold rules. Report each shop item's buy rate. Flag items no value-based policy buys.
- **Skip** is valued like any option: a policy skips when no offered effect beats the skip reward.
- **Dead effects:** held by 0% of runs, or picked < 10% of the time when offered by every value-based policy.

## 9. Endings

### 9.1 The five goals (simulation definitions; tune)

| Goal | Met when |
|---|---|
| **Pet kept** | ≤ 4 pet-care deficit days (weighted) over the run |
| **Relationship good** | ≤ 1 week of relationship needs missed, never 2 weeks in a row, and no loan from her that came due unpaid |
| **Book finished** | All 3 milestones by day 42 (near-finished: §3.4) |
| **Stress low/medium** | Average T over days 36–42 ≤ 60, **and** L on day 42 ≤ 40, **and** ≤ 6 days with T > 70 over the run |
| **Finances good** | See the money tiers below |

**Money tiers**

| Tier | Condition |
|---|---|
| **Good** | No debt on day 42 (no open loan, no unpaid deferred rent) and end value ≥ **750** (≈ two weeks of living costs; tune) |
| **Okay** | No debt, end value < 750 |
| **Poor** | Debt still open on day 42 (a loan from her not yet due, or deferred rent) |
| **Parents' ending** | §6 |

Only "good" meets the finance goal.

### 9.2 Ending tiers

| Tier | Condition |
|---|---|
| **Parents' ending** | §6; overrides everything else |
| **Best** | All five goals met |
| **Good** | Pet, relationship, stress and finances met; book not finished (near-finished or not) |
| **Mixed** | At least 3 of the 5 goals met, but not Best or Good |
| **Hard** | 2 or fewer goals met |

### 9.3 Targets (Normal difficulty)

| Policy | Finishes book | Best | Good or better | Parents' ending | Other |
|---|---|---|---|---|---|
| **Imperfect careful** | ~40–50% | ~25–35% | ~70–80% | ≤ 8% | — |
| Ideal careful (reference) | report | report | report | ≤ 2% | Upper bound for a balanced player |
| Book-heavy | **≥ 95%** | ~45–55% | **= best** (no "good" ending expected) | — | **Parents' ending or poor finances: 15–30%** |
| Grinder | ~0% | 0% | ≤ 10% | ≤ 5% | — |
| Careless | ~0–5% | ~0% | ≤ 10% | — | **Parents' ending or poor finances: ≥ 60%** |
| Greedy-optimal | — | 0% | 0% | — | — |

Planned difficulty spread (not simulated yet): imperfect careful's best rate ~45% on Gentle, ~30% on Normal, ~15% on Hard.

## 10. Simulation spec (for the coding agent)

### 10.1 Build
- Extend the existing simulator. Keep it seeded and deterministic; all numbers stay in `data/economy.yaml` and `data/policies.yaml`.
- **New or changed systems:**
  - two-layer stress;
  - money tiers, the poor tier and the new loan rules;
  - the skip choice;
  - value-based shop buys;
  - the changed effects;
  - the imperfect careful policy.
- **From round 2's `data/economy.recommended.yaml`, apply only:**
  - `lifelines.parents_floor: -100`
  - `lifelines.borrow_max: 400`
  - `effects.work_milestone_every: 12`
  - `side_class` income 60

  Don't apply: starting cash 2,000 (re-searched instead) or the neighbor at $0 (redefined in §8.4). Then delete the overlay file.

### 10.2 Player strategies (policies)
- **New: imperfect careful.** It's the careful policy, plus realistic slips under pressure:
  - On a day starting with T > 55, or with a deadline at risk, it skips a planned evening with her with **30%** chance. It also drops 0.5 h of pet care with **20%** chance.
  - With **15%** chance per week it accepts one job that doesn't fit its schedule check.
  - Everything else is as careful.

  Probabilities tune only if the stress targets are met and the ending targets are still far off. Report any change.
- **Careful** stays as **"ideal careful"** (reference).
- Book-heavy, grinder, careless and greedy-optimal are unchanged, except:
  - all repay her loan as soon as cash allows;
  - all take the day-1 job;
  - the story job is declinable (main) or always taken (check);
  - the pick and shop rules follow §8.5.
- Don't change policies' book hours to hit book targets; tune H instead.

### 10.3 Runs
**Tuning, in this order:**
1. **Stress parameters** (§7.6), with imperfect careful, ideal careful, book-heavy and grinder.
2. **Starting cash:** sweep 800–2,400 in steps of 100, scored on the §9.3 rows except book-finish.
3. **H** for imperfect careful's book target.
4. Re-check starting cash once.
5. CAT price re-check (target: imperfect careful picks it 40–60% of the time when offered).

**Main runs:** 2,000 seeds × policies × {effects, no effects}, story job declinable. Also run the story job **always taken** for the main policy table only.

**Sensitivity sweep** (±25% unless noted):
- **New in v0.4:** S sleep-recovery shares; the conversion threshold and rate; the sustained-S days; L load sizes (runway, rent, crunch, loan); L relief sizes (payment, milestone, good week); the finance-good bar; the loan cap; the skip reward.
- **Kept from round 2:** starting cash, rent, random and regular offer rates, effect sizes, H, the loan window (5/7/9 days), the parents' floor, the transformation odds.
- **NET:** reference row only.

### 10.4 Metrics
Everything from round 2, plus:
- **Stress:** S, L and T over time (median and 10th/90th percentile per policy); the average T; the peak T in days 29–35; L on day 42; days with T > 70; conversion events per run; illness days.
- **Money tiers:** good / okay / poor / parents' ending per policy.
- **Loans:** loans opened after day 35.
- **Effects:** skip rate per policy and per offer source; shop buy rates.

### 10.5 Acceptance targets (Normal, with effects, story job declinable)

| Area | Target |
|---|---|
| Endings | The §9.3 table |
| Stress | The §7.6 table |
| Imperfect careful | Lowest cash in days 28–35 in ≥ 60% of runs |
| Effects | Imperfect careful holds 7–9 at the end; no single offered effect in > 70% of any policy's top decile; CAT tool picked 40–60% by imperfect careful when offered; no dead effects; every shop item bought by at least one value-based policy in ≥ 10% of runs |
| Effect boost | Imperfect careful: average +5–12%, last 5 workdays +10–20% |
| Feedback | Imperfect careful, book-heavy and grinder each get at least one job payment in each of weeks 1–6 in **≥ 80%** of runs |
| Story job | Accepted by imperfect careful in ≥ 70% of runs |

### 10.6 Report
- Rename the round-2 report to `sim/reports/SIM_REPORT_round2.md` (with its charts and headline data) before writing the new `SIM_REPORT.md`.
- Same structure as round 2. Add:
  - a **stress section**: S/L/T charts, conversion, and the targets;
  - **money tiers** in the endings section;
  - a **comparison with round 2**.
- End with recommended config changes (an overlay, not merged), a re-run with them, and open issues needing owner decisions.

## 11. Open items this spec does not settle

- How taxes are shown (net pay, a tax jar or a tax bill).
- How visible S and L are at each difficulty (idea: Gentle shows both layers, Normal one total level, Hard only body language).
- Exact difficulty presets (Gentle / Hard).
- Individual habits for regular clients beyond the baseline; more fixed story commissions.
- Narrative content of events and endings (including the "poor" ending text); currency and city.

## Sources for the grounding figures

- ATA / ITI / University of Leeds rates surveys and industry summaries (per-word rates, MTPE vs. translation rates)
- ProZ.com forum polls and translator guides (daily output; real-world payment terms of 30/45/60 days and late payment)
- Authors Guild / PEN America (literary translation rates, ~13¢/word average)
- Apartments.com, Zumper, ApartmentAdvisor rent reports 2026 (one-bedroom ~$1,450–1,665)
- Petco, Rover, Pawlicy guides (puppy vet, vaccine and emergency costs)