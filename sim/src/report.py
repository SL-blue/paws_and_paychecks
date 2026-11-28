"""Write sim/reports/SIM_REPORT.md (SIM_BASELINE.md §10.6, v0.4) from saved results.

Tables and target checks are generated from the numbers; the written commentary lives in
sim/reports/commentary.yaml (keyed by section) so it is reviewed like any other text.
"""
from pathlib import Path

import numpy as np
import yaml

from . import analysis, charts
from .book import implied_start_progress
from .config import get_path
from .metrics import GOALS, MONEY_TIERS, TIERS, aggregate

POLICIES = ["imperfect_careful", "careful", "book_heavy", "grinder", "careless", "greedy_optimal"]
PLAYERS = POLICIES[:5]
NAMES = {"imperfect_careful": "Imperfect careful", "careful": "Ideal careful", "book_heavy": "Book-heavy",
         "grinder": "Grinder", "careless": "Careless", "greedy_optimal": "Greedy-optimal*", "effects": "Effects"}
MAIN = (True, False)          # with effects, story job declinable
FORCED = (True, True)         # with effects, story job always taken
VARIANT_NAMES = {(True, False): "With effects, story job declinable (main)",
                 (True, True): "With effects, story job always taken",
                 (False, False): "No effects (control), story job declinable",
                 (False, True): "No effects (control), story job always taken"}


def pct(x):
    return f"{x:.0%}" if x == x else "-"


def money(x):
    return f"{x:,.0f}" if x == x else "-"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def aggs(matrix, variant=MAIN, names=POLICIES):
    return {p: aggregate(matrix[(p, *variant)]) for p in names}


def runs_of(matrix, variant=MAIN, names=POLICIES):
    return {p: matrix[(p, *variant)] for p in names}


def note(notes, key):
    return [notes.get(key, "").strip(), ""] if notes.get(key) else []


def met_text(rows):
    met, _, total = analysis.score(rows)
    return f"{met}/{total}"


# --- 1. tuning ---------------------------------------------------------------------------------

def stress_search_table(steps):
    rows = []
    for st in steps:
        a = st["points"][st["chosen"]]
        met, dist, total = analysis.stress_score(a)
        tried = ", ".join(f"{v:g}" for v in st["points"])
        rows.append([st["pass"], f"`{st['path']}`", f"{st['was']:g}", f"**{st['chosen']:g}**", tried,
                     f"{met}/{total}", f"{dist:.3f}"])
    return table(["Pass", "Parameter", "Before", "Chosen", "Values tried", "§7.6 met", "Distance"], rows)


def cash_table(search, chosen):
    rows = []
    for cash, a in search.items():
        met, dist, total = analysis.cash_score(a)
        mark = " **(chosen)**" if cash == chosen else ""
        ic, bh = a["imperfect_careful"], a["book_heavy"]
        rows.append([f"{money(cash)}{mark}", pct(ic["parents"]), pct(ic["tiers"]["best"]), pct(ic["good_or_better"]),
                     pct(ic["low_day_28_35"]), pct(a["careful"]["parents"]), pct(bh["tiers"]["best"]),
                     pct(bh["tiers"]["good"]), pct(bh["parents_or_poor"]), pct(a["grinder"]["parents"]),
                     pct(a["careless"]["parents_or_poor"]), f"{met}/{total}", f"{dist:.3f}"])
    return table(["Start cash", "Imp. careful parents (<=8%)", "Imp. careful best (25-35%)", "Imp. careful good+ (70-80%)",
                  "Imp. careful low d28-35 (>=60%)", "Ideal careful parents (<=2%)", "Book-heavy best (45-55%)",
                  "Book-heavy good (<=2%)", "Book-heavy parents/poor (15-30%)", "Grinder parents (<=5%)",
                  "Careless parents/poor (>=60%)", "Met", "Distance"], rows)


def changed_from_file(results):
    """(path, file value, tuned value) for every searched number that the tuning moved."""
    from sim.run import STRESS_SEARCH   # local import: run.py imports this module's package
    paths = [p for p, _ in STRESS_SEARCH] + ["start.cash", "book.remaining_hours", "effects.pool.cat_tool.price_per_week"]
    out = []
    for path in paths:
        before, after = get_path(results["config_file"], path), get_path(results["config"], path)
        if before != after:
            out.append((path, before, after))
    return out


def section_tuning(results, notes):
    t, cfg = results["tuning"], results["config"]
    h = t["h"]
    lo, hi = h * (1 - cfg["book"]["remaining_hours_variation"]), h * (1 + cfg["book"]["remaining_hours_variation"])
    from sim.run import PROVISIONAL_CASH, STRESS_SEEDS
    lines = ["## 1. Tuning: stress, starting cash, H, CAT price", "",
             f"- **Starting cash (after day-1 rent): ${money(t['cash_2'])}** (first pass: ${money(t['cash_1'])}).",
             f"- **Book: H = {h:g} hours** of hard chapters left (±5% per run: {lo:.1f}–{hi:.1f} h). With a whole "
             f"book of {cfg['book']['total_hours_reference']} h (sim choice), the implied starting progress is "
             f"**{implied_start_progress(cfg):.0%}**.",
             f"- **CAT tool: ${t['cat_price']}/week.**", "",
             "Order (§10.3): stress parameters → starting cash → H → starting cash again → CAT price.", "",
             "### Step 1: stress parameters (§7.6)", "",
             f"A coordinate search: each parameter in turn (in §7.6's suggested order, then the starting L from §5), "
             f"over the values listed, with the others fixed; two passes. Each point runs imperfect careful, ideal "
             f"careful, book-heavy and grinder at a provisional starting cash of ${money(PROVISIONAL_CASH)} (the "
             f"round-2 probe value, §5), with effects and the story job declinable, {STRESS_SEEDS:,} seeds. A value "
             "is chosen by the smallest total distance to the eight §7.6 targets (shares in points of 100%, stress "
             "levels in points of 100), then by targets met, then by closeness to the current value.", "",
             stress_search_table(t["stress_steps"]), ""]
    lines += note(notes, "tuning_stress")
    lines += ["### Step 2: starting cash, first pass", "",
              "Each point runs the five player policies at the tuned stress numbers, "
              f"{results['seeds']:,} seeds. Scored on the §9.3 rows except book-finish (H sets those), plus imperfect "
              "careful's low-point target: most met, then smallest distance, then lower cash.", "",
              cash_table(t["cash_search_1"], t["cash_1"]), ""]
    rows = [[f"{hh:g}" + (" **(chosen)**" if hh == h else ""), pct(a["imperfect_careful"]["book_finished"]),
             pct(a["imperfect_careful"]["book_near_finished"]), pct(a["imperfect_careful"]["tiers"]["best"]),
             pct(a["imperfect_careful"]["good_or_better"]), pct(a["careful"]["book_finished"]),
             pct(a["book_heavy"]["book_finished"]), pct(a["book_heavy"]["tiers"]["best"])]
            for hh, a in t["h_search"].items()]
    lines += [f"### Step 3: H (starting cash ${money(t['cash_1'])}); target: imperfect careful finishes ~40–50% (aim 45%)", "",
              table(["H (hours)", "Imp. careful finishes", "Imp. careful near-finished", "Imp. careful best",
                     "Imp. careful good+", "Ideal careful finishes", "Book-heavy finishes", "Book-heavy best"], rows), "",
              f"### Step 4: starting cash, re-check (H = {h:g})", "", cash_table(t["cash_search_2"], t["cash_2"]), ""]
    rows = [[f"${p}" + (" **(chosen)**" if p == t["cat_price"] else ""), pct(r)] for p, r in t["cat_rates"].items()]
    lines += ["### Step 5: CAT-tool price; target: imperfect careful picks it 40–60% of the time when offered", "",
              table(["Price/week", "Imp. careful pick rate"], rows), ""]
    moved = changed_from_file(results)
    if moved:
        lines += ["### Values moved by the tuning", "",
                  "Search starting values are the spec's v0.4 numbers (or round 2's, where the spec carries them over).", "",
                  table(["Config key", "Spec / starting value", "Tuned"], [[f"`{p}`", f"{a:g}", f"{b:g}"] for p, a, b in moved]), ""]
    lines += note(notes, "tuning")
    return lines


# --- 2. endings --------------------------------------------------------------------------------

TIER_HEADER = (["Policy"] + [t.capitalize() for t in TIERS] + ["Good or better"]
               + [f"Goal: {g}" for g in GOALS] + ["Most missed goal (share of all runs)", "Book near-finished"])
MONEY_HEADER = ["Policy"] + [f"Money: {t}" for t in MONEY_TIERS] + ["Parents or poor", "Loan taken", "Loan after day 35",
                                                                    "Loan open on day 42"]


def tier_rows(a):
    return [[NAMES[p]] + [pct(a[p]["tiers"][t]) for t in TIERS] + [pct(a[p]["good_or_better"])]
            + [pct(a[p]["goals"][g]) for g in GOALS]
            + [f"{a[p]['most_missed']} ({pct(a[p]['most_missed_share'])})", pct(a[p]["book_near_finished"])]
            for p in a]


def money_rows(a):
    return [[NAMES[p]] + [pct(a[p]["money_tiers"][t]) for t in MONEY_TIERS] + [pct(a[p]["parents_or_poor"]),
            pct(a[p]["loan_taken"]), pct(a[p]["loan_after_35"]), pct(a[p]["loan_open_at_end"])] for p in a]


def section_endings(results, notes, matrix, heading="## 2. Endings and money tiers"):
    lines = [heading, "",
             "Tier shares of all runs; goal rates over all runs (a parents' run is measured up to its last day). "
             "\"Most missed\" counts runs that did not end with the parents. *Greedy-optimal is search-based and "
             "reads the run's future offers.", ""]
    for variant in (MAIN, FORCED):
        a = aggs(matrix, variant)
        lines += [f"### {VARIANT_NAMES[variant]}", "", table(TIER_HEADER, tier_rows(a)), "",
                  f"Money tiers ({VARIANT_NAMES[variant].split(' (')[0].lower()}): good = no debt and end value ≥ "
                  f"${money(results['config']['endings']['finance_good_min_value'])}; okay = no debt, less; poor = a loan "
                  "or deferred rent still open on day 42.", "", table(MONEY_HEADER, money_rows(a)), ""]
    return lines + note(notes, "endings")


# --- 3. stress ---------------------------------------------------------------------------------

STRESS_HEADER = ["Policy", "Average T", "Peak T d29-35 (median)", "L on day 42 (median)", "L >= 40 on day 42",
                 "Days T > 70", "Avg T d36-42", "Conversion days", "S moved into L", "Illness days", "Stress goal met"]


def stress_rows_table(a, matrix, variant):
    rows = []
    for p in a:
        runs = matrix[(p, *variant)]
        rows.append([NAMES[p], f"{a[p]['mean_stress']:.1f}", f"{a[p]['peak_stress_w5_p50']:.0f}",
                     f"{a[p]['long_end_p50']:.0f}", pct(a[p]["long_end_40"]), f"{a[p]['high_stress_days']:.1f}",
                     f"{a[p]['stress_end_avg']:.0f}", f"{a[p]['conversion_days']:.1f}",
                     f"{np.mean([r['converted'] for r in runs]):.1f}", f"{a[p]['illness_days']:.2f}",
                     pct(a[p]["goals"]["stress"])])
    return rows


def long_event_rows(matrix):
    labels = sorted({k for p in PLAYERS for r in matrix[(p, *MAIN)] for k in r["long_events"]})
    rows = []
    for label in labels:
        rows.append([label] + [f"{np.mean([r['long_events'].get(label, 0) for r in matrix[(p, *MAIN)]]):+.1f}"
                               for p in PLAYERS])
    return table(["L event (sum per run, mean)"] + [NAMES[p] for p in PLAYERS], rows)


def section_stress(results, notes, out_dir):
    matrix = results["matrix"]
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    charts.stress_over_time(runs_of(matrix, MAIN, PLAYERS), charts_dir / "stress_over_time.png",
                            "Stress over time (with effects, story job declinable)")
    a = aggs(matrix, MAIN, PLAYERS)
    target = [[NAMES[p], label, v, "yes" if ok else "**no**"] for p, label, v, ok, _ in analysis.stress_rows(a)]
    lines = ["## 3. Stress (two layers)", "",
             "S = short-term, L = long-term, T = min(100, S + L), all at the end of the day before the night's sleep. "
             "\"Peak T d29-35\" = each run's highest T in the convergence week; the table shows the median over runs. "
             "\"Conversion days\" = days on which S above the threshold moved into L.", "",
             "![Stress over time](charts/stress_over_time.png)", "",
             "### Per policy (with effects, story job declinable)", "",
             table(STRESS_HEADER, stress_rows_table(a, matrix, MAIN)), "",
             f"### §7.6 stress targets: {met_text(analysis.stress_rows(a))} met", "",
             table(["Policy", "Target", "Result", "Met"], target), "",
             "### What moves L: events per run", "",
             "Situation drivers (runway, rent due, crunch, loan open, pet deficit, sustained S, calm days) are not "
             "events and are not in this table.", "", long_event_rows(matrix), ""]
    return lines + note(notes, "stress")


# --- 4. per-policy summary ---------------------------------------------------------------------

SUMMARY_HEADER = ["Policy", "Parents' ending (day, median)", "via loan / floor", "Crisis", "Loan taken (repaid on time)",
                  "Lowest cash (median)", "Low in d28-35", "End value median (p10 / p90)", "Money good / okay / poor",
                  "Average T", "Rel. weeks missed", "Pet deficit days (weighted)", "Book milestones", "Book hours",
                  "Effects held", "Paid hours", "Jobs done", "Jobs late", "Story job taken"]


def summary_rows(matrix, variant):
    a = aggs(matrix, variant)
    return [[NAMES[p], f"{pct(a[p]['parents'])} ({money(a[p]['parents_day_median'])})",
             f"{pct(a[p]['parents_loan'])} / {pct(a[p]['parents_floor'])}", pct(a[p]["crisis"]),
             f"{pct(a[p]['loan_taken'])} ({pct(a[p]['loan_on_time'])})", money(a[p]["min_cash_p50"]),
             pct(a[p]["low_day_28_35"]),
             f"{money(a[p]['end_value_p50'])} ({money(a[p]['end_value_p10'])} / {money(a[p]['end_value_p90'])})",
             " / ".join(pct(a[p]["money_tiers"][t]) for t in ("good", "okay", "poor")),
             f"{a[p]['mean_stress']:.0f}", f"{a[p]['rel_weeks_missed']:.1f}", f"{a[p]['pet_deficit_days']:.1f}",
             f"{a[p]['book_milestones']:.2f}", f"{a[p]['book_hours']:.0f}", f"{a[p]['effects_count']:.1f}",
             f"{a[p]['paid_hours']:.0f}", f"{a[p]['jobs_completed']:.1f}", f"{a[p]['jobs_late']:.1f}",
             pct(a[p]["story_job_taken"])] for p in POLICIES]


def section_summary(results, notes, matrix):
    lines = ["## 4. Money, stress, time: summary per policy", "",
             "Means or shares over runs unless marked median. \"End value\" = cash + 0.9 × receivables − debts.", ""]
    for variant in (MAIN, FORCED, (False, False), (False, True)):
        lines += [f"### {VARIANT_NAMES[variant]}", "", table(SUMMARY_HEADER, summary_rows(matrix, variant)), ""]
    return lines + note(notes, "summary")


def section_feedback(results, notes, matrix):
    rows = []
    for variant in (MAIN, FORCED):
        a = aggs(matrix, variant)
        rows += [[NAMES[p] + (" (story forced)" if variant == FORCED else ""), f"{a[p]['pay_delay_median']:.0f}"]
                 + [f"{x:.1f}" for x in a[p]["payments_per_week_job"]]
                 + [pct(a[p]["every_week_paid_job"]), pct(a[p]["every_week_paid_all"])] for p in PLAYERS]
    return ["### Feedback cadence (with effects)", "",
            "Job payments include the day-1 job and deposits; pre-move invoices are excluded. The last column counts "
            "them, for comparison.", "",
            table(["Policy", "Median days delivery→payment", "Job payments wk1", "wk2", "wk3", "wk4", "wk5", "wk6",
                   "Runs with a job payment every week", "...counting pre-move invoices"], rows), ""] + note(notes, "feedback")


# --- 5. targets --------------------------------------------------------------------------------

def target_rows(results, matrix, variant):
    a = aggs(matrix, variant)
    eff = analysis.effects_summary(runs_of(matrix, variant), results["config"])
    return [[NAMES.get(p, p), t, v, "yes" if ok else "**no**"] for p, t, v, ok in analysis.check_targets(a, eff)]


def targets_met(results, matrix, variant=MAIN):
    rows = target_rows(results, matrix, variant)
    return sum(1 for r in rows if r[3] == "yes"), len(rows)


def section_targets(results, notes, matrix, heading="## 5. Acceptance targets (§10.5)"):
    main = target_rows(results, matrix, MAIN)
    forced = target_rows(results, matrix, FORCED)
    rows = [m + [f[2], f[3]] for m, f in zip(main, forced)]
    met = sum(1 for r in main if r[3] == "yes")
    lines = [heading, "",
             f"Main variant (with effects, story job declinable): **{met} of {len(main)} met.** "
             "The right-hand columns repeat the check with the story job always taken.", "",
             table(["Policy", "Target", "Result (declinable)", "Met", "Result (always taken)", "Met"], rows), ""]
    return lines + note(notes, "targets")


# --- 6. charts ---------------------------------------------------------------------------------

def section_charts(results, notes, out_dir):
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    runs = runs_of(results["matrix"])
    charts.cash_over_time(runs, charts_dir / "cash_over_time.png", "Cash over time (with effects, story job declinable)")
    charts.lowest_cash_day(runs, charts_dir / "lowest_cash_day.png", "Day of lowest cash (with effects, story job declinable)")
    lines = ["## 6. Cash charts", "", "![Cash over time](charts/cash_over_time.png)", "",
             "![Day of lowest cash](charts/lowest_cash_day.png)", ""]
    if "recommended" in results:
        rruns = runs_of(results["recommended"]["matrix"])
        charts.cash_over_time(rruns, charts_dir / "cash_over_time_recommended.png", "Cash over time, recommended config")
        charts.stress_over_time(runs_of(results["recommended"]["matrix"], MAIN, PLAYERS),
                                charts_dir / "stress_over_time_recommended.png", "Stress over time, recommended config")
    return lines + note(notes, "charts")


# --- 7. effects --------------------------------------------------------------------------------

SOURCES = ("weekly_reflection", "work_milestone", "book_milestone")


def section_effects(results, notes, matrix, heading="## 7. Effects"):
    cfg = results["config"]
    summary = analysis.effects_summary(runs_of(matrix), cfg)
    reports = summary["reports"]
    a = aggs(matrix)
    src_rows = []
    for p, rep in reports.items():
        s = rep["sources"]
        src_rows.append([NAMES[p], f"{s.get('weekly_reflection', 0):.1f}", f"{s.get('work_milestone', 0):.2f}",
                         f"{s.get('book_milestone', 0):.2f}", f"{s.get('shop', 0):.2f}", pct(rep["skip_rate"]),
                         " / ".join(pct(rep["skip_by_source"].get(src, float("nan"))) for src in SOURCES),
                         f"{rep['held_mean']:.1f}",
                         f"{a[p]['avg_effect_boost']:+.1%} / {a[p]['end_effect_boost']:+.1%}"])
    lines = [heading, ""] + note(notes, "effects_method") + [
        "### Offers by source, skips and effects held (per run, mean)", "",
        table(["Policy", "Weekly", "Work milestone", "Book milestone", "Shop buys", "Skip rate",
               "Skip rate: weekly / work / book", "Held at end", "Effect boost avg / last 5 workdays"], src_rows), "",
        "Targets: imperfect careful holds 7–9 (§8.1); its boost is +5–12% on average and +10–20% in the last 5 "
        "workdays (§8.2). \"Effect boost\" = the effects' multiplier on pay per paid hour (efficiency × throughput × "
        "rate effects), averaged over the hours worked. Careless never skips (it picks at random).", ""]
    pool = cfg["effects"]["pool"]
    rows = []
    for e in pool:
        if pool[e].get("shop"):
            continue
        row = [e, pool[e]["category"] + (" 📖" if pool[e].get("book_speed") else "")]
        for p in POLICIES:
            rate = reports[p]["pick_rate"].get(e)
            row.append(pct(rate) if rate is not None else "-")
        for p in POLICIES:
            row.append(f"{pct(reports[p]['all_share'].get(e, 0))} / {pct(reports[p]['top_share'].get(e, 0))}")
        rows.append(row)
    lines += ["### Offered effects: pick rate when offered, and share of runs holding each", "",
              "Left block: pick rate when the effect is one of the three offered. Right block: share of all runs holding "
              "it at the end / share of top-decile runs (by end value) that picked it from an offer.", "",
              table(["Effect", "Category"] + [f"pick: {NAMES[p]}" for p in POLICIES]
                    + [f"held all / top10: {NAMES[p]}" for p in POLICIES], rows), ""]
    shop_rows = [[e, pool[e]["category"], f"${pool[e].get('price', 0)}" + (f" + ${pool[e]['price_per_week']}/wk"
                  if pool[e].get("price_per_week") else "")] + [pct(reports[p]["buy_rate"][e]) for p in POLICIES]
                 for e in analysis.effects_shop(cfg)]
    lines += ["### Shop items: share of runs that bought each", "",
              "Value-based policies buy when the item's estimated value exceeds its price (§8.5), keeping a cash reserve. "
              "Careless buys at random.", "",
              table(["Item", "Category", "Price"] + [NAMES[p] for p in POLICIES], shop_rows), ""]
    dead, unsold = summary["dead"], summary["unsold_shop"]
    lines += [f"**Dead effects** (held by no run of any policy, or picked < 10% of the time when offered by every "
              f"value-based policy): {', '.join(dead) if dead else 'none'}.", "",
              f"**Shop items no value-based policy buys in ≥ 10% of runs:** {', '.join(unsold) if unsold else 'none'}.", ""]
    syn_rows = [[NAMES[p]] + [pct(reports[p]["synergy_share"][s]) for s in cfg["effects"]["synergies"]] for p in POLICIES]
    lines += ["### Synergies: share of runs holding both effects", "",
              table(["Policy"] + list(cfg["effects"]["synergies"]), syn_rows), ""]
    cats = ["efficiency", "throughput", "rate", "stress_relief", "book"]
    cap_rows = [[NAMES[p]] + [pct(reports[p]["cap_hit_share"][c]) for c in cats] for p in POLICIES]
    lines += ["### Cap hits: share of runs where a category's summed bonus went over its cap at least once", "",
              table(["Policy"] + [f"{c} (cap +{cfg['effects']['caps'][c]:.0%})" for c in cats], cap_rows), ""]
    pair_rows = [[NAMES[p], ", ".join(f"{x}+{y} (×{lift:.2f})" for (x, y), lift in reports[p]["top_pairs"][:3]) or "-"]
                 for p in POLICIES]
    lines += ["### Combos over-represented in the top decile (lift = share in top 10% / share overall)", "",
              table(["Policy", "Top combos"], pair_rows), ""]
    return lines + note(notes, "effects")


# --- 8. clients, story job, imperfect careful's slips -------------------------------------------

def section_clients(results, notes, matrix):
    rows = []
    for variant in (MAIN, FORCED):
        a = aggs(matrix, variant)
        rows += [[NAMES[p] + (" (story forced)" if variant == FORCED else ""),
                  f"{a[p]['regular_jobs']['A']:.1f}", f"{a[p]['regular_jobs']['B']:.1f}", f"{a[p]['regular_jobs']['C']:.1f}",
                  pct(a[p]["story_job_taken"]), pct(a[p]["story_declined"])] for p in POLICIES]
    ic = matrix[("imperfect_careful", *MAIN)]
    slips = {k: np.mean([r["slips"].get(k, 0) for r in ic]) for k in ("her", "pet", "job")}
    return ["## 8. Regular clients, the story job and imperfect careful's slips", "",
            "Jobs accepted per run from each regular client (B includes the day-1 job; A includes the story job).", "",
            table(["Policy", "Client A jobs", "Client B jobs", "Client C jobs", "Story job taken", "Story job declined"], rows),
            "", f"**Imperfect careful's slips per run (main variant):** {slips['her']:.2f} skipped evenings with her, "
            f"{slips['pet']:.2f} days with 0.5 h less pet care, {slips['job']:.2f} jobs accepted that didn't fit.", ""] \
        + note(notes, "clients")


# --- 9. sensitivity ----------------------------------------------------------------------------

def sens_rows(base, sweep, ranked):
    rows = []
    for param, sw in ranked:
        (l1, lo), (l2, hi) = sweep[param].items()

        def cell(p, k):
            return f"{pct(analysis.metric(lo[p], k))} / {pct(analysis.metric(base[p], k))} / {pct(analysis.metric(hi[p], k))}"
        rows.append([f"{param} ({l1} / {l2})", f"{sw * 100:.0f} pp" if sw is not None else "(reference)",
                     cell("imperfect_careful", "best"), cell("imperfect_careful", "good_or_better"),
                     cell("imperfect_careful", "stress_goal_missed"), cell("imperfect_careful", "book_finished"),
                     cell("careful", "stress_goal_missed"), cell("book_heavy", "best"), cell("book_heavy", "parents_or_poor"),
                     cell("grinder", "stress_goal_missed"), cell("careless", "parents_or_poor")])
    return rows


def section_sensitivity(results, notes):
    base = aggs(results["matrix"], MAIN, PLAYERS)
    sweep, ref = results["sensitivity"], results["reference_rows"]
    ranked = analysis.sensitivity_rank(base, sweep)
    rows = sens_rows(base, sweep, ranked) + sens_rows(base, ref, [(k, None) for k in ref])
    return ["## 9. Sensitivity", "",
            "Each parameter at its low / baseline / high value (±25% unless stated), all else at the tuned config, "
            f"with effects and the story job declinable, {results['seeds']:,} seeds per point. Sorted by the largest "
            "change in any player policy's parents' / best / good-or-better / stress-goal-missed share. NET is fixed "
            "(§4) and shown as a reference row only. \"Stress missed\" = share of runs missing the stress goal.", "",
            table(["Parameter", "Max swing", "Imp. careful best", "Imp. careful good+", "Imp. careful stress missed",
                   "Imp. careful finishes book", "Ideal careful stress missed", "Book-heavy best",
                   "Book-heavy parents/poor", "Grinder stress missed", "Careless parents/poor"], rows), ""] \
        + note(notes, "sensitivity")


# --- 10. comparison with round 2 ----------------------------------------------------------------

def section_round2(results, notes, out_dir):
    path = out_dir / "round2_headline.yaml"
    if not path.exists():
        return []
    r2 = yaml.safe_load(path.read_text())
    a = aggs(results["matrix"])
    rows = []
    for p in POLICIES:
        old, new = r2["policies"]["careful" if p == "imperfect_careful" else p], a[p]
        rows.append([NAMES[p] + (" (vs. round-2 careful)" if p in ("imperfect_careful", "careful") else ""),
                     f"{pct(old['parents'])} → {pct(new['parents'])}", f"{pct(old['best'])} → {pct(new['tiers']['best'])}",
                     f"{pct(old['good_or_better'])} → {pct(new['good_or_better'])}",
                     f"{pct(old['book_finished'])} → {pct(new['book_finished'])}",
                     f"{pct(old['finance_good'])} → {pct(new['finance_good'])}",
                     f"{pct(old['stress_goal'])} → {pct(new['goals']['stress'])}",
                     f"{old['mean_stress']:.0f} → {new['mean_stress']:.0f}",
                     f"{money(old['end_value_p50'])} → {money(new['end_value_p50'])}",
                     f"{old['effects_count']:.1f} → {new['effects_count']:.1f}",
                     f"{old['avg_effect_boost']:+.0%} → {new['avg_effect_boost']:+.0%}",
                     f"{pct(old['every_week_paid_job'])} → {pct(new['every_week_paid_job'])}",
                     f"{pct(old['story_job_taken'])} → {pct(new['story_job_taken'])}"])
    return ["## 10. Comparison with round 2", "",
            f"Round 2 (spec v0.3, `SIM_REPORT_round2.md`): starting cash ${money(r2['chosen_cash'])}, H = {r2['h']:g} h, "
            "one stress layer, finance bar $1,500. Round 3: tuned v0.4 config. Both: with effects, story job declinable. "
            "Round 2 had one careful policy; both careful policies here are compared with it. Round 2's stress was a "
            "single level; here \"average stress\" is T.", "",
            table(["Policy", "Parents' ending", "Best", "Good or better", "Book finished", "Finances good", "Stress goal met",
                   "Average stress", "End value (median)", "Effects held", "Effect boost (avg)",
                   "Job payment every week", "Story job taken"], rows), ""] + note(notes, "round2")


# --- 11. recommended changes and re-run ------------------------------------------------------------

def section_recommended(results, notes):
    if "recommended" not in results:
        return ["## 11. Recommended changes", "", "(No `data/economy.recommended.yaml` found.)", ""]
    rec = results["recommended"]
    rows = [[f"`{c['key']}`", c["from"], c["to"], c["why"], c["expected"]] for c in rec["overlay"]["rationale"]]
    met, total = targets_met(results, rec["matrix"])
    base_met, _ = targets_met(results, results["matrix"])
    a = aggs(rec["matrix"], MAIN, PLAYERS)
    lines = ["## 11. Recommended changes and re-run", "",
             "The changes live in `data/economy.recommended.yaml` as an overlay on the tuned config. They are "
             "**not** merged into `economy.yaml`, pending the owner's review.", "",
             table(["Config key", "Tuned value", "Recommended", "Why", "Expected effect"], rows), "",
             f"**Result:** {met} of {total} targets met (tuned config: {base_met}).", ""]
    lines += note(notes, "recommended_intro")
    lines += section_targets(results, {}, rec["matrix"], "### Acceptance targets with the recommendations")
    lines += section_endings(results, {}, rec["matrix"], "### Endings with the recommendations")
    lines += ["### Stress with the recommendations", "", table(STRESS_HEADER, stress_rows_table(a, rec["matrix"], MAIN)), "",
              "![Stress over time, recommended](charts/stress_over_time_recommended.png)", "",
              "![Cash over time, recommended](charts/cash_over_time_recommended.png)", ""]
    return lines + note(notes, "recommended")


def write(results, out_dir):
    out_dir = Path(out_dir)
    notes_path = out_dir / "commentary.yaml"
    notes = yaml.safe_load(notes_path.read_text()) if notes_path.exists() else {}
    lines = ["# Paws & Paychecks: economy simulation report — round 3 (spec v0.4)", ""]
    lines += note(notes, "intro")
    lines += [f"Reproduce with `python -m sim.run --all` ({results['seeds']:,} seeds per policy and variant; "
              "deterministic per (config, policy, seed)). Earlier rounds: `SIM_REPORT_round1.md`, `SIM_REPORT_round2.md`.", ""]
    lines += note(notes, "toc")
    lines += section_tuning(results, notes)
    lines += section_endings(results, notes, results["matrix"])
    lines += section_stress(results, notes, out_dir)
    lines += section_summary(results, notes, results["matrix"])
    lines += section_feedback(results, notes, results["matrix"])
    lines += section_targets(results, notes, results["matrix"])
    lines += section_charts(results, notes, out_dir)
    lines += section_effects(results, notes, results["matrix"])
    lines += section_clients(results, notes, results["matrix"])
    lines += section_sensitivity(results, notes)
    lines += section_round2(results, notes, out_dir)
    lines += section_recommended(results, notes)
    lines += ["## 12. Open issues", ""] + note(notes, "open_issues")
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    (out_dir / "SIM_REPORT.md").write_text(text)


__all__ = ["write"]
