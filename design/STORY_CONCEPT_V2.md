# Paws & Paychecks — v2 concept (working notes)

> Status: decisions so far for the longer, story-driven version. The v1 documents (`GAME_DESIGN.md`, `TECH_SPEC.md` and the v1 `CLAUDE.md`) describe the submitted class-assignment version and are not in this repo. Economy numbers and the simulation spec live in `SIM_BASELINE.md`; the reasons behind decisions are in `DECISIONS.md`.

## Decided

- Made for human players only; the v1 anti-AI-agent requirements no longer apply.
- Narrative life sim + resource management + roguelike, **42 in-game days** (6 weeks).
- Leaning toward **one turn = one day**, with uneven pacing (quick workdays, longer days off, fully played story days, occasional montage skips).
- No instant-reaction gameplay; small interactions should express feeling rather than test skill.
- Bankruptcy is possible, but it doesn't end the run directly: it leads to the **parents' ending** if a loan from her isn't repaid in time (see "Endings").
- **Endings come from five goals:** keep the pet, a good relationship with her, the book finished, low or medium stress, and a good financial situation. The best ending needs all five; the other four without the book is still a good ending (see "Endings").
- The pet is an **invented creature**. It arrives very young and grows through stages during the game; its growth doesn't have to match any real animal.
- Not necessarily web-only.
- Tone: warm and honest, not complaining about the current state of the world.
- **The character is a freelance translator.**
- **AI is "the weather"** in the narrative: an ambient condition of the world that shapes the work (e.g. clients asking for post-editing), not an antagonist, a plot driver or an argument.
- **The partner is an engineer** (field deliberately unspecified), with a habit of trying to quantify things.
- **Relationship and pet state are never shown as numbers**, only through qualitative indicators (behavior, tone, scenes).
- **Events:** fixed important events, random events drawn by stage, callbacks (including from everyday moments), and choices that change depending on earlier choices (see "Event system").
- **Daily cycle:** a common-sense default day (work 9 am to 5–6 pm, then rest / entertainment / time together, 8 hours of sleep by default) that the player can rearrange freely; sleep can be cut short at a cost; interruptions happen during the working hours the player sets, and not all of them are bad or important; an **imperfect auto-arrangement** plans the day and the player adjusts it easily (see "Daily cycle").
- **Roguelike effects:** effects such as working-efficiency modifiers are chosen by the player from **randomly offered** options; chances to pick come from a **mix** of sources (see "Roguelike effects").
- **The financial system is designed first**, with time as the shared currency; stress, the relationship and the pet are coupled to it through time and efficiency rather than derived from money.
- **Payment timing is compressed to game time** (roughly 2–14 days after delivery, sometimes late), with **one realistic long delay as a fixed story event** landing in the convergence week. Feedback on finished work comes **at delivery** (client reply, reputation, a visible "money owed" list); cash comes later.
- **The book starts with progress already made** (the character has been translating it for months); what remains are the hard parts. Its size is set by the ending targets and varies only a little between runs; it pays **no advance** during the run.
- **Clients:** most are types; **three regular clients** have their own habits, slightly better terms, and fixed story commissions. A **fixed small job on day 1** opens the run, and the **week-2 story job** is a choice that is hard to refuse.

## Premise

The player character has just moved to the partner's city, and money is tight because of the move. On the night they celebrate moving in, the character sends an application to adopt the creature, partly because they really want it and partly because they're not quite sober. They don't expect to be approved. They are, and the creature arrives at their home.

### Living situation
- The partner (she) **does not live with the character** and commutes to her company's office every workday.
- The reason they live apart still needs a short in-story explanation.

### Opening scene
- The game opens with the character **confessing to the partner** that the adoption was half impulsive.
- She is amused but encouraging: over the past year she has seen the character reading about the creature and how to care for it, off and on.

## Narrative lines

Four entangled lines: **the pet's growth**, **the character's career**, **money**, and **her situation / the relationship**.

### Principles
- Every **major** event should touch **at least two lines** (e.g. a client pays late the same week as the first vet visit, and the obvious fix is borrowing from her). Ordinary-day events don't need to (see "Event system").
- Each line has its own arc; the turning points **converge in one week** (week 5). What the player protects that week shapes the ending most.
- Convergence also works the other way: a few days where everything lines up well, to remember fondly.
- She has a life that doesn't revolve around the character; support goes both ways.
- All four lines ask the same question from different angles: can you live and express yourself in your own way?

### 42-day structure (draft)

| | Week 1 (days 1–7): Arrival | Weeks 2–3 (days 8–21): Growing | Week 4 (days 22–28): Pressure builds | Week 5 (days 29–35): Convergence | Week 6 (days 36–42): Resolution |
|---|---|---|---|---|---|
| **Pet** | Baby, settling in | Habits emerge; first growth stage around day 14 | Signs of the next change | Transformation or illness | Adult personality shows; inspection on day 42 |
| **Career** | Small jobs; returning to the unfinished book | A regular client moves to post-editing; a large agency job taken | Workload vs. book time | A big standard job vs. a book milestone | Book finished, or not |
| **Money** | Savings runway after the move | Payments start flowing | Getting tight | Monthly rent (around day 31) + vet bill + the long-delayed payment from week 2 | Stable, in debt, or broke |
| **Her** | Normal work rhythm | Her big project ramps up | Her crunch begins | Her deadline + her crossroads | Her decision; the lease / moving-in decision |

- End of week 3 (around day 21): a good day where lines align, as a breather before the pressure.
- Monthly rent is paid from moving savings on day 1 and falls due again inside the convergence week.

## Daily cycle

- **Default workday:** working hours 9 am to 5 or 6 pm; the time after is for rest, entertainment or time together (accompaniment); **8 hours of sleep by default**. The default should match common sense.
- **Free arrangement:** as a freelancer, the player can rearrange the day, e.g. go out in the afternoon and work in the evening.
- **Sleep can be cut into**, with a cost.
- **Interruptions** happen during the working hours the player has arranged. **Not all of them are bad or important**: some are pleasant, some neutral, some matter.
- **Auto-arrangement:** the game proposes the day's plan (when to work and which project to work on), which the player can adjust easily. It is **deliberately imperfect**, so that the player always has something to work on and decide.

## Roguelike effects

- Effects modify the character's play, e.g. **working-efficiency effects**: "doing only one thing in a day boosts efficiency", or "doing at least two things in a day improves it".
- They are part of the roguelike layer: **the options offered are random**, and the player chooses among them.
- Chances to pick come from a **mix**: guaranteed weekly picks, picks earned through play, and effects that can be bought. Expected counts and sizing are in `SIM_BASELINE.md` §8.

## Her career

- **She is an engineer.** The specific field is left unspecified on purpose.
- Her defining habit: **she tries to quantify things**, including things that may not be measurable.
- Office-based, with real deadlines and an arc of her own.
- Her crossroads: **a promotion**, or **going independent**.
- Must **not** be in direct conflict with AI, or affected by AI the way the character is.
- She should show that meaning can exist inside structured, stable work, which also balances the character's "expression vs. standard results" theme: some work matters precisely because it has to be done exactly right.
- (Earlier candidates considered: exhibition designer / curator, architect, urban planner.)

## Themes

### Expression vs. standard results
- AI can replace work that only needs **standard results** ("industrial needs"), but not **self-expression**: in expression, *how* something is said matters as much as what is said.
- AI can help a person achieve what they wanted but couldn't do alone, but their own ideas, decisions and concepts should still be clearly visible and have their own style.
- The game doesn't need to make an argument about AI (AI is the weather). What it should carry are universal feelings: **expressing what we want to say in our own way, the contentment of creating something we like, and spending time with things and people we enjoy.**

### How this could show up (ideas, not decided)
- Translation sits on this line: some jobs only need a correct, standard result (e.g. post-editing), while translating a book is expression; two translators produce two different books.
- The character's daily tension can be *which kind of work am I doing today, and how much of myself goes into it*, managed like money and time, not taught as a lesson.
- The player's phrasing choices in the book project could build up and appear in the finished book at the end, alongside the photo album and the creature's personality, as evidence of how the player chose to live.
- The same idea applies to caring for the creature and the relationship: there's no "correct" standard result; the *how* is the point.

### Requirement
- The game should explain, somewhere in the story, **why the character chose translation, what they wanted to do, and what their own project means to them.**

## The character's own book project

- **Self-initiated** (decided 2026-11-27): no contract and not a commissioned job. If the book is finished, it gets paid **after the game ends**, so the payment never affects money during the run.
- **Starts with progress already made:** the character has been translating it in spare time for months, since before the move. The existing pages anchor the character's voice and partly explain why they chose translation without stating it.
- **What remains are the hard parts:** the chapters the character kept putting off. This justifies a slower, more careful pace (choosing words and phrases) and gives the in-game work emotional weight. Starting progress and which chapters remain can vary per run.
- **Time budget:** finishing should be a real sacrifice, but doable. Its size is tuned so that a balanced (careful) player finishes in about 40–50% of runs; the starting progress varies only a little between runs, so finishing depends on choices, not dice.
- **Near-finished:** if the last part is at least half done, the ending can say the book was finished a month later. That counts toward the good ending, not the best one.
- **No advance:** the book pays nothing during the run (an advance made book-focused play almost risk-free in the simulation).
- Its milestones mainly help **stress relief and emotional state**, not money, because that's closer to reality. Only a few effects (e.g. deep focus, old margin notes, reading aloud) change how fast the book goes. Working on it is a choice that costs time and paid work but restores the character.

### Reading aloud to the creature ⭐ (keep this)
- The character tries out translated passages by **reading them aloud to the creature**.
- The creature reacts to the *sound* rather than the meaning; it becomes the book's first audience.
- A small, private ritual that shows the character's voice without explanation.

### Other ways to reveal the backstory (ideas, not decided)
- The worn original copy of the book on the desk, with the character's old margin notes.
- The partner asking about the parts of the story she doesn't know; the player can open up or deflect.
- The finished book's dedication page at the end, depending on how the run went.

## Core money mechanic

- The character is a **freelance translator**: they can stay home and care for the creature, but they have to choose which jobs to take.
- There's no regular salary. Payment arrives **after a job is finished**, and sometimes **late**.
- **Payment timing is compressed to game time:** direct clients pay within a few days, standard agencies in about a week, slow agencies in about two weeks; some payments run late. One large agency job taken in week 2 is paid only in week 5, as a fixed story event.
- **Clients:** most clients are types (direct, standard agency, slow agency). **Three regular clients** are special: slightly better pay or faster payment, their own habits (e.g. usually sends something on Mondays), reputation that counts more, and one or two **fixed story commissions** on set days. Their other work arrives randomly but follows their habit, so players can learn and plan around it.
- **Day 1:** a fixed small job from the regular direct client opens the run and doubles as the tutorial; it pays around day 4.
- **The week-2 story job** comes from the regular agency and is a choice that is hard to refuse; declining is allowed but hurts that client relationship.
- **Rush jobs** pay more but have short deadlines and a higher stress cost.
- **Taxes** are a fixed 22% of payments; how they are shown (net pay, a tax jar or a tax bill) is still open.
- **Feedback comes at delivery:** the client's reply, a reputation change, and the invoice appearing in a visible "money owed" list with its expected date. Cash comes later.
- The player has to manage how long each job is expected to take against when bills are due.
- Small paid jobs (hours to a few days) keep money moving; the character's own book project mostly doesn't pay (see above).

## Endings

### The five goals
1. **Keep the pet** (the creature is well cared for).
2. **A good relationship with her** (not ignoring her too much; any loan from her repaid on time).
3. **The book finished.**
4. **Low or medium stress.**
5. **A good financial situation:** not in the parents' ending, no debt left, and about a month's rent of safety. "Okay" = solvent but below that.

### Tiers
- **Best:** all five goals.
- **Good:** goals 1, 2, 4 and 5 without the book (a near-finished book can be "finished a month later").
- **Mixed / hard:** fewer goals met; which goals are missed shapes the ending's story.
- **The parents' ending:** borrowing from her raises the character's stress sharply. If the loan isn't repaid within 7 days (Normal; 5 on Hard), the character's parents call and help, and the run ends. It is warm, not a punishment.

### Targets
- A balanced player should reach the best ending in roughly a quarter to a third of runs, and a good ending or better in most runs.
- A player who commits to the book reaches the best ending more often, but risks the parents' ending.
- Exact targets per strategy are in `SIM_BASELINE.md` §9.

## Meters and visibility

- **Relationship** and **pet** (mood, health, growth): never numbers. Shown through behavior, her messages and tone, scenes, and similar qualitative indicators.
- **Money:** exact (bankruptcy has to be plannable).
- **Stress** (and possibly similar personal indicators): may be visible so the player can plan; how visible could depend on the **difficulty setting**. (Open.)

## Event system

- **Fixed important events:** story beats on set days (e.g. the opening confession, the day-1 job, growth stages, the week-2 story job, rent day, the long-delayed payment, the convergence week, day 42).
- **Random events by stage:** drawn from pools tied to the stage the player is in.
- **Callbacks:** some choices schedule later events (e.g. a promise made now comes due days later). **Everyday moments can plant callbacks too**, as in real life (e.g. a neighbor chatted with early on turns out to matter later).
- **Choices that depend on history:** the options offered in an event can change according to choices the player has already made.
- **Ordinary-day events** don't need to touch two storylines. Their job is **immersion** (the texture of daily life with the creature, the city, her) and **small relief**, such as a little stress recovery.
- Still open: whether there are state-triggered events (fired by conditions such as long high stress or low savings), how stages are defined, and how events are tagged/weighted.

## Open questions

- How taxes are shown (net pay, a tax jar or a tax bill).
- Regular clients' individual habits and further fixed story commissions.
- Why the character and partner live apart.
- How stress visibility maps to difficulty levels.
- Remaining event system details (see above).
- Daily cycle details: time unit (hour vs. larger blocks), the exact cost of cutting sleep, how interruptions are answered, what the auto-arrangement prioritizes.
- Exact effect sizes, offer rates and starting cash (to be set by the simulation; see `SIM_BASELINE.md`).
- Platform/engine.