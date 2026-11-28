"""Write sim/reports/SIM_REPORT.md (SIM_BASELINE.md §10.6) from saved results.

Tables and target checks are generated from the numbers; the written commentary lives in
sim/reports/commentary.yaml (keyed by section) so it is reviewed like any other text.
"""
from pathlib import Path

import yaml

from . import analysis, charts
from .book import implied_start_progress
from .metrics import GOALS, TIERS, aggregate

POLICIES = ["careful", "book_heavy", "grinder", "careless", "greedy_optimal"]
PLAYERS = POLICIES[:4]
NAMES = {"careful": "Careful", "book_heavy": "Book-heavy", "grinder": "Grinder",
         "careless": "Careless", "greedy_optimal": "Greedy-optimal*", "effects": "Effects"}
MAIN = (True, False)          # with effects, story job declinable
FORCED = (True, True)         # with effects, story job always taken
VARIANT_NAMES = {(True, False): "With effects, story job declinable (main)",
                 (True, True): "With effects, story job always taken",
                 (False, False): "No effects (control), story job declinable",
                 (False, True): "No effects (control), story job always taken"}


def pct(x):
    return f"{x:.0%}" if x == x else "-"


def pct1(x):
    return f"{x:.1%}" if x == x else "-"


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


# --- 1. tuning ---------------------------------------------------------------------------------

def cash_table(search, chosen):
    rows = []
    for cash, a in search.items():
        met, dist, total = analysis.cash_score(a)
        mark = " **(chosen)**" if cash == chosen else ""
        rows.append([f"{money(cash)}{mark}", pct(a["careful"]["parents"]), pct(a["careful"]["tiers"]["best"]),
                     pct(a["careful"]["good_or_better"]), pct(a["careful"]["low_day_28_35"]),
                     pct(a["book_heavy"]["parents"]), pct(a["book_heavy"]["tiers"]["best"]),
                     pct(a["book_heavy"]["good_or_better"]), pct(a["grinder"]["parents"]),
                     pct(a["careless"]["parents"]), f"{met}/{total}", f"{dist:.3f}"])
    return table(["Start cash", "Careful parents (<=8%)", "Careful best (25-35%)", "Careful good+ (70-80%)",
                  "Careful low d28-35 (>=60%)", "Book-heavy parents (15-30%)", "Book-heavy best (45-55%)",
                  "Book-heavy good+ (60-70%)", "Grinder parents (<=5%)", "Careless parents (>=60%)", "Met", "Distance"], rows)


def section_tuning(results, notes):
    t, cfg = results["tuning"], results["config"]
    h = t["h"]
    lo, hi = h * (1 - cfg["book"]["remaining_hours_variation"]), h * (1 + cfg["book"]["remaining_hours_variation"])
    cat_now = results["config_file"]["effects"]["pool"]["cat_tool"]["price_per_week"]
    lines = ["## 1. Tuning: starting cash, book hours H, CAT price", "",
             f"- **Starting cash (after day-1 rent): ${money(t['cash_2'])}** (first pass: ${money(t['cash_1'])}).",
             f"- **Book: H = {h:g} hours** of hard chapters left (±5% per run: {lo:.1f}–{hi:.1f} h), "
             f"{h * cfg['book']['words_per_hour']:,.0f} words at 150 w/h. With a whole book of "
             f"{cfg['book']['total_hours_reference']} h (sim choice), the implied starting progress is "
             f"**{implied_start_progress(cfg):.0%}** ({implied_start_progress(cfg, hi):.0%}–{implied_start_progress(cfg, lo):.0%}).",
             f"- **CAT tool: ${t['cat_price']}/week**" + (" (unchanged)." if t["cat_price"] == cat_now else f" (was ${cat_now})."), "",
             "Order (§10.3): starting-cash search → tune H for careful's book target → CAT-price check → re-check "
             f"starting cash once. Each point runs the four player policies, with effects and the story job declinable, "
             f"{results['seeds']:,} seeds. A cash value scores by how many of the §9.3 ending targets (book-finish rows "
             "excluded, H sets those) plus careful's low-point target it meets, then by the total distance to the "
             "missed ones, then the lower cash.", "",
             "### Starting-cash search, first pass (H and CAT price from the config file)", "",
             cash_table(t["cash_search_1"], t["cash_1"]), ""]
    rows = [[f"{hh:g}" + (" **(chosen)**" if hh == h else ""), pct(a["careful"]["book_finished"]),
             pct(a["careful"]["book_near_finished"]), pct(a["careful"]["tiers"]["best"]), pct(a["careful"]["good_or_better"]),
             pct(a["book_heavy"]["book_finished"]), pct(a["book_heavy"]["tiers"]["best"]), pct(a["book_heavy"]["parents"])]
            for hh, a in t["h_search"].items()]
    lines += [f"### H search (starting cash ${money(t['cash_1'])}); target: careful finishes ~40–50% (aim 45%)", "",
              table(["H (hours)", "Careful finishes", "Careful near-finished", "Careful best", "Careful good+",
                     "Book-heavy finishes", "Book-heavy best", "Book-heavy parents"], rows), ""]
    rows = [[f"${p}" + (" **(chosen)**" if p == t["cat_price"] else ""), pct(r)] for p, r in t["cat_rates"].items()]
    lines += ["### CAT-tool price check; target: careful picks it 40–60% of the time when offered", "",
              table(["Price/week", "Careful pick rate"], rows), "",
              f"### Starting-cash re-check (H = {h:g}, CAT ${t['cat_price']}/week)", "",
              cash_table(t["cash_search_2"], t["cash_2"]), ""]
    file_cash, file_h = results["config_file"]["start"]["cash"], results["config_file"]["book"]["remaining_hours"]
    if (file_cash, file_h) != (t["cash_2"], h) or cat_now != t["cat_price"]:
        lines += [f"> `data/economy.yaml` has start.cash = {file_cash}, book.remaining_hours = {file_h}, CAT "
                  f"{cat_now}/week. All later sections use the tuned values above; update the file to match.", ""]
    lines += note(notes, "tuning")
    return lines


# --- 2. endings --------------------------------------------------------------------------------

TIER_HEADER = (["Policy"] + [t.capitalize() for t in TIERS] + ["Good or better"]
               + [f"Goal: {g}" for g in GOALS] + ["Most missed goal (share of all runs)", "Book near-finished"])


def tier_rows(a):
    return [[NAMES[p]] + [pct(a[p]["tiers"][t]) for t in TIERS] + [pct(a[p]["good_or_better"])]
            + [pct(a[p]["goals"][g]) for g in GOALS]
            + [f"{a[p]['most_missed']} ({pct(a[p]['most_missed_share'])})", pct(a[p]["book_near_finished"])]
            for p in POLICIES]


def section_endings(results, notes, matrix, heading="## 2. Endings"):
    lines = [heading, "",
             "Tier shares of all runs; goal rates over all runs (a parents' run is measured up to its last day). "
             "\"Most missed\" counts runs that did not end with the parents. *Greedy-optimal is search-based and "
             "reads the run's future offers.", ""]
    for variant in (MAIN, FORCED):
        lines += [f"### {VARIANT_NAMES[variant]}", "", table(TIER_HEADER, tier_rows(aggs(matrix, variant))), ""]
    return lines + note(notes, "endings")


# --- 3. per-policy summary ---------------------------------------------------------------------

SUMMARY_HEADER = ["Policy", "Parents' ending (day, median)", "via loan / floor", "Crisis", "Loan taken (repaid on time)",
                  "Lowest cash (median)", "Low in d28-35", "End value median (p10 / p90)", "Finances good / okay",
                  "Days stress>70", "Stress avg d36-42", "Illness days", "Rel. weeks missed", "Pet deficit days (weighted)",
                  "Book milestones", "Book hours", "Effects held", "Paid hours", "Jobs done", "Jobs late", "Story job taken"]


def summary_rows(matrix, variant):
    a = aggs(matrix, variant)
    return [[NAMES[p], f"{pct(a[p]['parents'])} ({money(a[p]['parents_day_median'])})",
             f"{pct(a[p]['parents_loan'])} / {pct(a[p]['parents_floor'])}", pct(a[p]["crisis"]),
             f"{pct(a[p]['loan_taken'])} ({pct(a[p]['loan_on_time'])})", money(a[p]["min_cash_p50"]),
             pct(a[p]["low_day_28_35"]),
             f"{money(a[p]['end_value_p50'])} ({money(a[p]['end_value_p10'])} / {money(a[p]['end_value_p90'])})",
             f"{pct(a[p]['finance_good'])} / {pct(a[p]['finance_okay'])}",
             f"{a[p]['high_stress_days']:.1f}", f"{a[p]['stress_end_avg']:.0f}", f"{a[p]['illness_days']:.2f}",
             f"{a[p]['rel_weeks_missed']:.1f}", f"{a[p]['pet_deficit_days']:.1f}", f"{a[p]['book_milestones']:.2f}",
             f"{a[p]['book_hours']:.0f}", f"{a[p]['effects_count']:.1f}", f"{a[p]['paid_hours']:.0f}",
             f"{a[p]['jobs_completed']:.1f}", f"{a[p]['jobs_late']:.1f}", pct(a[p]["story_job_taken"])] for p in POLICIES]


def section_summary(results, notes, matrix, heading="## 3. Money, stress, time: summary per policy"):
    lines = [heading, "",
             "Means or shares over runs unless marked median. \"End value\" = cash + 0.9 × receivables − debts. "
             "Finances good = no debt and end value ≥ $1,500; okay = solvent, below that.", ""]
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
            "Job payments include the day-1 job and deposits; pre-move invoices are excluded (owner decision, "
            "2026-11-27). The last column counts them, for comparison.", "",
            table(["Policy", "Median days delivery→payment", "Job payments wk1", "wk2", "wk3", "wk4", "wk5", "wk6",
                   "Runs with a job payment every week", "...counting pre-move invoices"], rows), ""] + note(notes, "feedback")


# --- 4. targets --------------------------------------------------------------------------------

def target_rows(results, matrix, variant):
    a = aggs(matrix, variant)
    eff = analysis.effects_summary(runs_of(matrix, variant), results["config"])
    return [[NAMES.get(p, p), t, v, "yes" if ok else "**no**"] for p, t, v, ok in analysis.check_targets(a, eff)]


def section_targets(results, notes, matrix, heading="## 4. Acceptance targets (§10.5)"):
    main = target_rows(results, matrix, MAIN)
    forced = target_rows(results, matrix, FORCED)
    rows = [m + [f[2], f[3]] for m, f in zip(main, forced)]
    met = sum(1 for r in main if r[3] == "yes")
    lines = [heading, "",
             f"Main variant (with effects, story job declinable): **{met} of {len(main)} met.** "
             "The right-hand columns repeat the check with the story job always taken.", "",
             table(["Policy", "Target", "Result (declinable)", "Met", "Result (always taken)", "Met"], rows), ""]
    return lines + note(notes, "targets")


# --- 5. charts ---------------------------------------------------------------------------------

def section_charts(results, notes, out_dir):
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    runs = runs_of(results["matrix"])
    charts.cash_over_time(runs, charts_dir / "cash_over_time.png", "Cash over time (with effects, story job declinable)")
    charts.lowest_cash_day(runs, charts_dir / "lowest_cash_day.png", "Day of lowest cash (with effects, story job declinable)")
    lines = ["## 5. Charts", "", "![Cash over time](charts/cash_over_time.png)", "",
             "![Day of lowest cash](charts/lowest_cash_day.png)", ""]
    if "recommended" in results:
        rruns = runs_of(results["recommended"]["matrix"])
        charts.cash_over_time(rruns, charts_dir / "cash_over_time_recommended.png", "Cash over time, recommended config")
        charts.lowest_cash_day(rruns, charts_dir / "lowest_cash_day_recommended.png", "Day of lowest cash, recommended config")
    return lines + note(notes, "charts")


# --- 6. effects --------------------------------------------------------------------------------

def section_effects(results, notes, matrix, heading="## 6. Effects"):
    cfg = results["config"]
    summary = analysis.effects_summary(runs_of(matrix), cfg)
    reports = summary["reports"]
    a = aggs(matrix)
    src_rows = []
    for p, rep in reports.items():
        s = rep["sources"]
        src_rows.append([NAMES[p], f"{s.get('weekly_reflection', 0):.1f}", f"{s.get('work_milestone', 0):.2f}",
                         f"{s.get('book_milestone', 0):.2f}", f"{s.get('shop', 0):.2f}", f"{rep['held_mean']:.1f}",
                         f"{a[p]['avg_effect_boost']:+.1%} / {a[p]['end_effect_boost']:+.1%}"])
    lines = [heading, ""] + note(notes, "effects_method") + [
        "### Offers by source and effects held (per run, mean)", "",
        table(["Policy", "Weekly", "Work milestone", "Book milestone", "Shop buys", "Held at end",
               "Effect boost avg / last 5 workdays"], src_rows), "",
        "Targets: careful holds 7–9, neglectful/narrow 5–6 (§8.1); careful's boost +10–20% on average and "
        "+20–35% in the last 5 workdays (§8.2). \"Effect boost\" = the effects' multiplier on pay per paid "
        "hour (efficiency × throughput × rate effects), averaged over the hours worked.", ""]
    pool = cfg["effects"]["pool"]
    rows = []
    for e in pool:
        shop = pool[e].get("shop")
        row = [e + (" (shop)" if shop else ""), pool[e]["category"] + (" 📖" if pool[e].get("book_speed") else "")]
        for p in POLICIES:
            rep = reports[p]
            if shop:
                row.append("bought " + pct(rep["bought"].get(e, 0) / len(matrix[(p, *MAIN)])))
            else:
                rate = rep["pick_rate"].get(e)
                row.append(pct(rate) if rate is not None else "-")
        for p in POLICIES:
            top = "·" if shop else pct(reports[p]["top_share"].get(e, 0))
            row.append(f"{pct(reports[p]['all_share'].get(e, 0))} / {top}")
        rows.append(row)
    lines += ["### Pick rate when offered, and share of runs holding each effect", "",
              "Left block: pick rate when the effect is one of the three offered (shop items: share of runs that "
              "bought it). Right block: share of all runs holding it at the end / share of top-decile runs (by end "
              "value) that picked it from an offer. Careless picks at random.", "",
              table(["Effect", "Category"] + [f"pick: {NAMES[p]}" for p in POLICIES]
                    + [f"held all / top10: {NAMES[p]}" for p in POLICIES], rows), ""]
    dead = summary["dead"]
    lines += [f"**Dead effects** (held by no run of any policy, or picked < 10% of the time when offered by every "
              f"value-based policy): {', '.join(dead) if dead else 'none'}.", ""]
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


# --- 7. regular clients and the story job ------------------------------------------------------

def section_clients(results, notes, matrix):
    rows = []
    for variant in (MAIN, FORCED):
        a = aggs(matrix, variant)
        rows += [[NAMES[p] + (" (story forced)" if variant == FORCED else ""),
                  f"{a[p]['regular_jobs']['A']:.1f}", f"{a[p]['regular_jobs']['B']:.1f}", f"{a[p]['regular_jobs']['C']:.1f}",
                  pct(a[p]["story_job_taken"]), pct(a[p]["story_declined"])] for p in POLICIES]
    return ["## 7. Regular clients and the story job", "",
            "Jobs accepted per run from each regular client (B includes the day-1 job; A includes the story job).", "",
            table(["Policy", "Client A jobs", "Client B jobs", "Client C jobs", "Story job taken", "Story job declined"], rows),
            ""] + note(notes, "clients")


# --- 8. sensitivity ----------------------------------------------------------------------------

def sens_rows(base, sweep, ranked):
    rows = []
    for param, sw in ranked:
        (l1, lo), (l2, hi) = sweep[param].items()

        def cell(p, k):
            return f"{pct(analysis.metric(lo[p], k))} / {pct(analysis.metric(base[p], k))} / {pct(analysis.metric(hi[p], k))}"
        rows.append([f"{param} ({l1} / {l2})", f"{sw * 100:.0f} pp" if sw is not None else "(reference)",
                     cell("careful", "parents"), cell("careful", "best"), cell("careful", "good_or_better"),
                     cell("careful", "book_finished"), cell("book_heavy", "parents"), cell("book_heavy", "best"),
                     cell("grinder", "parents"), cell("careless", "parents")])
    return rows


def section_sensitivity(results, notes):
    base = aggs(results["matrix"], MAIN, PLAYERS)
    sweep, ref = results["sensitivity"], results["reference_rows"]
    ranked = analysis.sensitivity_rank(base, sweep)
    rows = sens_rows(base, sweep, ranked) + sens_rows(base, ref, [(k, None) for k in ref])
    return ["## 8. Sensitivity", "",
            "Each parameter at its low / baseline / high value (±25% unless stated), all else at the tuned config, "
            f"with effects and the story job declinable, {results['seeds']:,} seeds per point. Sorted by the largest "
            "change in any player policy's parents' / best / good-or-better share. NET is fixed (§4) and shown as a "
            "reference row only.", "",
            table(["Parameter", "Max swing", "Careful parents", "Careful best", "Careful good+", "Careful finishes book",
                   "Book-heavy parents", "Book-heavy best", "Grinder parents", "Careless parents"], rows), ""] + note(notes, "sensitivity")


# --- 9. comparison with round 1 ------------------------------------------------------------------

def section_round1(results, notes, out_dir):
    path = out_dir / "round1_headline.yaml"
    if not path.exists():
        return []
    r1 = yaml.safe_load(path.read_text())
    a = aggs(results["matrix"])
    rows = []
    for p in POLICIES:
        old, new = r1["policies"][p], a[p]
        rows.append([NAMES[p], f"{pct(old['bankrupt'])} → {pct(new['parents'])}",
                     f"{pct(old['book_finished'])} → {pct(new['book_finished'])}",
                     f"{money(old['end_value_p50'])} → {money(new['end_value_p50'])}",
                     f"{pct(old['low_day_28_35'])} → {pct(new['low_day_28_35'])}",
                     f"{old['effects_count']:.1f} → {new['effects_count']:.1f}",
                     f"{old['avg_effect_boost']:+.0%} → {new['avg_effect_boost']:+.0%}",
                     f"{pct(old['every_week_paid_job'])} → {pct(new['every_week_paid_job'])}",
                     f"{pct(old['story_job_taken'])} → {pct(new['story_job_taken'])}",
                     f"{old['paid_hours']:.0f} → {new['paid_hours']:.0f}"])
    return ["## 9. Comparison with round 1", "",
            f"Round 1 (spec v0.2, `SIM_REPORT_round1.md`): starting cash ${money(r1['chosen_cash'])}, book unpaid, "
            "with effects. Round 2: tuned config, with effects, story job declinable. Round 1's \"bankrupt\" is "
            "compared with round 2's parents' ending; the two rules differ (§6). Round 1's effect boost counted "
            "efficiency × throughput only; round 2's also counts rate effects.", "",
            table(["Policy", "Bankrupt → parents' ending", "Book finished", "End value (median)", "Low in d28-35",
                   "Effects held", "Effect boost (avg)", "Job payment every week", "Story job taken", "Paid hours"], rows),
            ""] + note(notes, "round1")


# --- 10. recommended changes and re-run ------------------------------------------------------------

def section_recommended(results, notes):
    if "recommended" not in results:
        return ["## 10. Recommended changes", "", "(No `data/economy.recommended.yaml` found.)", ""]
    rec = results["recommended"]
    rows = [[c["key"], c["from"], c["to"], c["why"], c["expected"]] for c in rec["overlay"]["rationale"]]
    lines = ["## 10. Recommended changes and re-run", "",
             "The changes live in `data/economy.recommended.yaml` as an overlay on the tuned config. They are "
             "**not** merged into `economy.yaml`, pending the owner's review.", "",
             table(["Config key", "Tuned value", "Recommended", "Why", "Expected effect"], rows), ""]
    lines += note(notes, "recommended_intro")
    lines += section_targets(results, {}, rec["matrix"], "### Acceptance targets with the recommendations")
    lines += section_endings(results, {}, rec["matrix"], "### Endings with the recommendations")
    lines += ["![Cash over time, recommended](charts/cash_over_time_recommended.png)", "",
              "![Lowest cash day, recommended](charts/lowest_cash_day_recommended.png)", ""]
    return lines + note(notes, "recommended")


def write(results, out_dir):
    out_dir = Path(out_dir)
    notes_path = out_dir / "commentary.yaml"
    notes = yaml.safe_load(notes_path.read_text()) if notes_path.exists() else {}
    lines = ["# Paws & Paychecks: economy simulation report — round 2 (spec v0.3)", ""]
    lines += note(notes, "intro")
    lines += [f"Reproduce with `python -m sim.run --all` ({results['seeds']:,} seeds per policy and variant; "
              "deterministic per (config, policy, seed)). Round 1 is archived in `SIM_REPORT_round1.md`.", ""]
    lines += note(notes, "toc")
    lines += section_tuning(results, notes)
    lines += section_endings(results, notes, results["matrix"])
    lines += section_summary(results, notes, results["matrix"])
    lines += section_feedback(results, notes, results["matrix"])
    lines += section_targets(results, notes, results["matrix"])
    lines += section_charts(results, notes, out_dir)
    lines += section_effects(results, notes, results["matrix"])
    lines += section_clients(results, notes, results["matrix"])
    lines += section_sensitivity(results, notes)
    lines += section_round1(results, notes, out_dir)
    lines += section_recommended(results, notes)
    lines += ["## 11. Open issues", ""] + note(notes, "open_issues")
    text = "\n".join(lines)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    (out_dir / "SIM_REPORT.md").write_text(text)


__all__ = ["write"]
