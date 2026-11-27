"""Report charts (matplotlib, PNG): cash over time and the lowest-cash day, per policy.

Small multiples, one policy per panel, one hue: identity comes from the panel title, not color.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

BLUE, BAND = "#257de0", "#b6d5f8"
TEXT, MUTED, GRID = "#191919", "#666666", "#e6e6e6"
LABELS = {"careful": "Careful", "book_heavy": "Book-heavy", "grinder": "Grinder",
          "careless": "Careless", "greedy_optimal": "Greedy-optimal (search, sees future offers)"}


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def cash_over_time(runs_by_policy, path, title):
    fig, axes = plt.subplots(1, len(runs_by_policy), figsize=(3.2 * len(runs_by_policy), 3.0), sharey=True)
    for ax, (policy, runs) in zip(axes, runs_by_policy.items()):
        series = np.array([r["cash_series"] for r in runs])
        days = np.arange(1, series.shape[1] + 1)
        p10, p50, p90 = (np.percentile(series, q, axis=0) for q in (10, 50, 90))
        ax.fill_between(days, p10, p90, color=BAND, linewidth=0, label="10th-90th percentile")
        ax.plot(days, p50, color=BLUE, linewidth=2, label="median")
        ax.axhline(0, color=MUTED, linewidth=0.8)
        ax.axvspan(29, 35, color="#f2f2f2", zorder=0)
        ax.set_title(LABELS[policy], fontsize=9, color=TEXT, loc="left")
        ax.set_xticks([1, 8, 15, 22, 29, 36, 42])
        ax.set_xlabel("day", fontsize=8, color=MUTED)
        _style(ax)
    axes[0].set_ylabel("cash ($, end of day, before lifelines)", fontsize=8, color=MUTED)
    axes[0].legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle(title + "  (grey band = convergence week)", fontsize=10, color=TEXT, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def lowest_cash_day(runs_by_policy, path, title):
    fig, axes = plt.subplots(1, len(runs_by_policy), figsize=(3.2 * len(runs_by_policy), 2.6), sharey=True)
    for ax, (policy, runs) in zip(axes, runs_by_policy.items()):
        days = [r["min_cash_day"] for r in runs]
        counts = np.bincount(days, minlength=43)[1:43] / len(days)
        ax.bar(np.arange(1, 43), counts, width=0.8, color=BLUE)
        ax.axvspan(27.5, 35.5, color="#f2f2f2", zorder=0)
        share = np.mean([(28 <= d <= 35) for d in days])
        ax.set_title(f"{LABELS[policy]}\n{share:.0%} in days 28-35", fontsize=9, color=TEXT, loc="left")
        ax.set_xticks([1, 8, 15, 22, 29, 36, 42])
        ax.set_xlabel("day of lowest cash", fontsize=8, color=MUTED)
        _style(ax)
    axes[0].set_ylabel("share of runs", fontsize=8, color=MUTED)
    fig.suptitle(title + "  (grey band = days 28-35)", fontsize=10, color=TEXT, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
