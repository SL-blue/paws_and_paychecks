"""Write sim/reports/SIM_REPORT.md (SIM_BASELINE.md §9.6) from saved results.

Tables and target checks are generated from the numbers; the written commentary lives in
sim/reports/commentary.yaml (keyed by section) so it is reviewed like any other text.
"""
from pathlib import Path

import yaml

from . import analysis, charts
from .metrics import aggregate

POLICIES = ["careful", "book_heavy", "grinder", "careless", "greedy_optimal"]
NAMES = {"careful": "Careful", "book_heavy": "Book-heavy", "grinder": "Grinder",
         "careless": "Careless", "greedy_optimal": "Greedy-optimal*"}


def pct(x):
    return f"{x:.0%}" if x == x else "-"


def money(x):
    return f"{x:,.0f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def aggs(matrix, with_effects=True, advance=False):
    return {p: aggregate(matrix[(p, with_effects, advance)]) for p in POLICIES}


# --- sections --------------------------------------------------------------------------------

def section_cash(results, notes):
    rows = []
    for cash, agg in results["cash_search"].items():
        met, dist, _ = analysis.cash_score(agg)
        mark = " **(chosen)**" if cash == results["chosen_cash"] else ""
        rows.append([f"{money(cash)}{mark}", pct(agg["careful"]["bankrupt"]), pct(agg["careful"]["low_day_28_35"]),
                     pct(agg["book_heavy"]["bankrupt"]), pct(agg["grinder"]["bankrupt"]),
                     pct(agg["careless"]["bankrupt"]), f"{met}/5", f"{dist:.3f}"])
    lines = ["## 1. Starting cash", "",
             f"**Chosen starting cash (after day-1 rent): ${money(results['chosen_cash'])}.** "
             "Pre-move receivables are unchanged (600 / 900 / 500 on days 6 / 13 / 24).", "",
             "The search ran every policy with effects and the unpaid book, "
             f"{results['seeds']:,} seeds per point. A value scores by how many of the five cash-sensitive "
             "targets it meets, then by the total distance to the ones it misses, then by how close book-heavy "
             "bankruptcy is to the middle of its 15-30% band.", "",
             table(["Start cash", "Careful bankrupt (<=8%)", "Careful low in d28-35 (>=60%)",
                    "Book-heavy bankrupt (15-30%)", "Grinder bankrupt (<=5%)", "Careless bankrupt (>=60%)",
                    "Met", "Distance"], rows), ""]
    if results["config_file_cash"] != results["chosen_cash"]:
        lines += [f"> Note: `data/economy.yaml` has start.cash = {results['config_file_cash']}, "
                  "which differs from the search result. Update the file.", ""]
    lines += [notes.get("cash", ""), ""]
    return lines


def summary_rows(matrix, with_effects, advance):
    a = aggs(matrix, with_effects, advance)
    return [[NAMES[p], pct(a[p]["bankrupt"]), pct(a[p]["crisis"]), f"{a[p]['lifelines_mean']:.2f}",
             money(a[p]["min_cash_p50"]), pct(a[p]["low_day_28_35"]),
             f"{money(a[p]['end_value_p50'])} ({money(a[p]['end_value_p10'])} / {money(a[p]['end_value_p90'])})",
             f"{a[p]['high_stress_days']:.1f}", pct(a[p]["high_stress_share_w45"]), f"{a[p]['illness_days']:.2f}",
             f"{a[p]['rel_weeks_missed']:.1f}", f"{a[p]['pet_deficit_days']:.1f}",
             f"{a[p]['book_milestones']:.2f}", pct(a[p]["book_finished"]), f"{a[p]['book_hours']:.0f}",
             f"{a[p]['effects_count']:.1f}", f"{a[p]['paid_hours']:.0f}", f"{a[p]['jobs_completed']:.1f}",
             f"{a[p]['jobs_late']:.1f}", pct(a[p]["good_ending"])] for p in POLICIES]


SUMMARY_HEADER = ["Policy", "Bankrupt", "Crisis", "Lifelines used", "Lowest cash (median)", "Low in d28-35",
                  "End value median (p10 / p90)", "Days stress>70", "Stress>70 share wk4-5", "Illness days",
                  "Rel. weeks missed", "Pet deficit days", "Book milestones", "Book finished", "Book hours",
                  "Effects held", "Paid hours", "Jobs done", "Jobs late", "Good combined ending"]


def section_summary(results, notes, matrix, heading="## 2. Summary per policy"):
    lines = [heading, "",
             "All values are means or shares over runs unless marked median. \"End value\" = cash + 0.9 x "
             "receivables - debts. \"Good combined ending\" = not bankrupt, <= 1 relationship week missed, "
             "<= 4 pet-care deficit days, <= 6 days with stress > 70 (simulator definition, see Open issues). "
             "*Greedy-optimal is search-based and reads the run's future offers.", ""]
    for with_effects in (True, False):
        for advance in (False, True):
            label = f"{'With effects' if with_effects else 'No effects (control)'}, book {'small advance' if advance else 'unpaid'}"
            lines += [f"### {label}", "", table(SUMMARY_HEADER, summary_rows(matrix, with_effects, advance)), ""]
    lines += [notes.get("summary", ""), ""]
    return lines


def section_targets(results, notes, matrix, heading="## 3. Acceptance targets (with effects, book unpaid)"):
    a = aggs(matrix)
    eff = analysis.effects_report(pooled_effect_runs(matrix))
    worst = {}   # effect -> (policy, highest top-decile share across policies)
    for pol in POLICIES:
        for e, share in analysis.effects_report(matrix[(pol, True, False)])["top_share"].items():
            if share > worst.get(e, ("", -1))[1]:
                worst[e] = (pol, share)
    rows = analysis.check_targets(a, worst, eff["cap_hit_runs"])
    lines = [heading, "", table(["Policy", "Target", "Result", "Met"],
                                [[NAMES.get(p, p), t, v, "yes" if ok else "**no**"] for p, t, v, ok in rows]), ""]
    adv = aggs(matrix, True, True)
    lines += ["With the small book advance: " + "; ".join(
        f"{NAMES[p]} bankrupt {pct(adv[p]['bankrupt'])}, book finished {pct(adv[p]['book_finished'])}"
        for p in ("careful", "book_heavy")) + ".", ""]
    lines += [notes.get("targets", ""), ""]
    return lines


def section_charts(results, notes, out_dir):
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    m = results["matrix"]
    runs = {p: m[(p, True, False)] for p in POLICIES}
    charts.cash_over_time(runs, charts_dir / "cash_over_time.png", "Cash over time (with effects, book unpaid)")
    charts.lowest_cash_day(runs, charts_dir / "lowest_cash_day.png", "Day of lowest cash (with effects, book unpaid)")
    lines = ["## 4. Charts", "", "![Cash over time](charts/cash_over_time.png)", "",
             "![Day of lowest cash](charts/lowest_cash_day.png)", ""]
    if "recommended" in results:
        rm = results["recommended"]["matrix"]
        rruns = {p: rm[(p, True, False)] for p in POLICIES}
        charts.cash_over_time(rruns, charts_dir / "cash_over_time_recommended.png", "Cash over time, recommended config")
        charts.lowest_cash_day(rruns, charts_dir / "lowest_cash_day_recommended.png", "Day of lowest cash, recommended config")
    lines += [notes.get("charts", ""), ""]
    return lines


def pooled_effect_runs(matrix):
    return [r for p in POLICIES for r in matrix[(p, True, False)]]


def section_effects(results, notes, matrix, heading="## 5. Effects"):
    lines = [heading, ""]
    src_rows, held_rows = [], []
    reports = {p: analysis.effects_report(matrix[(p, True, False)]) for p in POLICIES}
    for p, rep in reports.items():
        s = rep["sources"]
        src_rows.append([NAMES[p], f"{s.get('weekly_reflection', 0):.1f}", f"{s.get('work_milestone', 0):.1f}",
                         f"{s.get('book_milestone', 0):.1f}", f"{s.get('shop', 0):.1f}", f"{rep['held_mean']:.1f}",
                         f"{rep['pool_exhausted']:.2f}",
                         f"{aggregate(matrix[(p, True, False)])['avg_effect_boost']:+.0%} / {aggregate(matrix[(p, True, False)])['end_effect_boost']:+.0%}"])
    lines += ["### Offers by source and effects held (per run, mean)", "",
              table(["Policy", "Weekly", "Work milestone", "Book milestone", "Shop buys", "Held at end",
                     "Offers with empty pool", "Effect boost avg / last 5 workdays"], src_rows),
              "", "Target: careful holds 7-9 effects, neglectful/narrow 5-6; effect boost +15-25% on average, "
              "+30-50% at the end (§8.2). \"Effect boost\" = the effects' multiplier on paid-work output "
              "(efficiency x throughput), averaged over hours worked.", ""]
    effect_ids = sorted({e for rep in reports.values() for e in rep["offered"]} |
                        {e for rep in reports.values() for e in rep["bought"]})
    rows = []
    for e in effect_ids:
        row = [e]
        for p in POLICIES:
            rep = reports[p]
            rate = rep["pick_rate"].get(e)
            row.append(f"{rate:.0%}" if rate is not None else ("shop " + pct(rep["bought"][e] / len(matrix[(p, True, False)])) if rep["bought"].get(e) else "-"))
        for p in POLICIES:
            row.append(f"{reports[p]['all_share'].get(e, 0):.0%} / {reports[p]['top_share'].get(e, 0):.0%}")
        rows.append(row)
    lines += ["### Pick rate (when offered) and share of runs holding each effect", "",
              "Left block: how often the effect is picked when it is one of the three offered (shop items: share "
              "of runs that bought it). Right block: share of all runs / of top-decile runs (by end value) that "
              "hold it at the end.", "",
              table(["Effect"] + [f"pick: {NAMES[p]}" for p in POLICIES] + [f"held all/top10: {NAMES[p]}" for p in POLICIES], rows), ""]
    pair_rows = [[NAMES[p], ", ".join(f"{a}+{b} (x{lift:.2f})" for (a, b), lift in reports[p]["top_pairs"][:3]) or "-"]
                 for p in POLICIES]
    lines += ["### Combos over-represented in the top decile (lift = share in top 10% / share overall)", "",
              table(["Policy", "Top combos"], pair_rows), "", notes.get("effects", ""), ""]
    return lines


def section_sensitivity(results, notes):
    base = results["matrix"]
    base_agg = aggs(base)
    sens = results["sensitivity"]
    rank = analysis.sensitivity_rank(base_agg, sens)
    rows = []
    for param, swing, vswing in rank:
        lo, hi = sens[param]["-25%"], sens[param]["+25%"]
        cell = lambda p, k, f=pct: f"{f(lo[p][k])} / {f(base_agg[p][k])} / {f(hi[p][k])}"  # noqa: E731
        rows.append([param, f"{swing * 100:.0f} pp", cell("careful", "bankrupt"), cell("book_heavy", "bankrupt"),
                     cell("grinder", "bankrupt"), cell("careless", "bankrupt"), cell("careful", "low_day_28_35"),
                     cell("careful", "book_finished"), cell("careful", "end_value_p50", money),
                     cell("grinder", "high_stress_share_w45")])
    lines = ["## 6. Sensitivity (each parameter -25% / baseline / +25%)", "",
             "With effects, book unpaid, chosen starting cash, "
             f"{results['seeds']:,} seeds per point. Sorted by the largest change in any policy's bankruptcy rate.", "",
             table(["Parameter", "Max bankrupt swing", "Careful bankrupt", "Book-heavy bankrupt", "Grinder bankrupt",
                    "Careless bankrupt", "Careful low d28-35", "Careful book finished", "Careful end value (median)",
                    "Grinder stress>70 wk4-5"], rows), "", notes.get("sensitivity", ""), ""]
    return lines


def section_recommended(results, notes):
    if "recommended" not in results:
        return ["## 7. Recommended changes", "", "(No `data/economy.recommended.yaml` found.)", ""]
    rec = results["recommended"]
    overlay = rec["overlay"]
    rows = [[c["key"], c["from"], c["to"], c["why"], c["expected"]] for c in overlay["rationale"]]
    lines = ["## 7. Recommended changes and re-run", "",
             "The changes live in `data/economy.recommended.yaml` as an overlay on `data/economy.yaml`. "
             "They are **not** merged into `economy.yaml` yet, pending the owner's review.", "",
             table(["Config key", "Baseline", "Recommended", "Why", "Expected effect"], rows), "",
             notes.get("recommended_intro", ""), ""]
    lines += section_targets(results, notes, rec["matrix"], "### Acceptance targets with the recommendations")
    lines += section_summary(results, {}, rec["matrix"], "### Summary per policy with the recommendations")
    lines += ["![Cash over time, recommended](charts/cash_over_time_recommended.png)", "",
              "![Lowest cash day, recommended](charts/lowest_cash_day_recommended.png)", ""]
    lines += section_effects_short(rec["matrix"])
    lines += [notes.get("recommended", ""), ""]
    return lines


def section_effects_short(matrix):
    rows = []
    for p in POLICIES:
        rep = analysis.effects_report(matrix[(p, True, False)])
        a = aggregate(matrix[(p, True, False)])
        top = max(sorted(rep["top_share"].items()), key=lambda kv: kv[1])   # ties: first by name
        rows.append([NAMES[p], f"{rep['held_mean']:.1f}", f"{a['avg_effect_boost']:+.0%} / {a['end_effect_boost']:+.0%}",
                     f"{top[0]} {top[1]:.0%}"])
    return ["### Effects with the recommendations", "",
            table(["Policy", "Held at end", "Boost avg / end", "Most common effect in top decile"], rows), ""]


def section_feedback(results, notes):
    a = aggs(results["matrix"])
    rows = [[NAMES[p], f"{a[p]['pay_delay_median']:.0f}"] + [f"{x:.1f}" for x in a[p]["payments_per_week_job"]]
            + [pct(a[p]["every_week_paid_job"]), pct(a[p]["every_week_paid_all"])] for p in POLICIES]
    return ["### Feedback cadence (with effects, book unpaid)", "",
            table(["Policy", "Median days delivery->payment", "Job payments wk1", "wk2", "wk3", "wk4", "wk5", "wk6",
                   "Runs with a job payment every week", "...counting pre-move invoices"], rows), "",
            notes.get("feedback", ""), ""]


def write(results, out_dir):
    out_dir = Path(out_dir)
    notes_path = out_dir / "commentary.yaml"
    notes = yaml.safe_load(notes_path.read_text()) if notes_path.exists() else {}
    lines = ["# Paws & Paychecks: economy simulation report", "",
             notes.get("intro", ""), "",
             f"Reproduce with `python -m sim.run --all` ({results['seeds']:,} seeds per policy and variant; "
             "deterministic per (config, policy, seed)).", ""]
    lines += notes.get("toc", "").splitlines() + [""]
    lines += section_cash(results, notes)
    lines += section_summary(results, notes, results["matrix"])
    lines += section_feedback(results, notes)
    lines += section_targets(results, notes, results["matrix"])
    lines += section_charts(results, notes, out_dir)
    lines += section_effects(results, notes, results["matrix"])
    lines += section_sensitivity(results, notes)
    lines += section_recommended(results, notes)
    lines += ["## 8. Open issues", "", notes.get("open_issues", ""), ""]
    (out_dir / "SIM_REPORT.md").write_text("\n".join(lines).replace("\n\n\n", "\n\n"))


__all__ = ["write"]
