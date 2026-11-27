"""The character's own book (SIM_BASELINE.md §3.3): starts with progress, sized by hours."""
from dataclasses import dataclass, field

from .rng import stream


@dataclass
class Book:
    start_progress: float
    remaining_hours_nominal: float
    words_total_remaining: float
    words_left: float
    milestone_marks: list          # words_left values at which milestones are reached
    milestones_done: int = 0
    hours: float = 0.0
    milestone_days: list = field(default_factory=list)

    @property
    def finished(self):
        return self.milestones_done >= len(self.milestone_marks)


def remaining_hours(cfg, progress):
    """Linear: max progress -> remaining_hours_min, min progress -> remaining_hours_max."""
    b, s = cfg["book"], cfg["start"]
    lo, hi = s["book_progress_min"], s["book_progress_max"]
    share = 0.5 if hi == lo else (hi - progress) / (hi - lo)
    hours = b["remaining_hours_min"] + share * (b["remaining_hours_max"] - b["remaining_hours_min"])
    return hours * b["remaining_hours_scale"]


def new_book(cfg, seed):
    s = cfg["start"]
    progress = stream(seed, "book").uniform(s["book_progress_min"], s["book_progress_max"])
    hours = remaining_hours(cfg, progress)
    words = hours * cfg["book"]["words_per_hour"]
    n = cfg["book"]["milestones"]
    marks = [words * (1 - (i + 1) / n) for i in range(n)]
    return Book(progress, hours, words, words, marks)


def work(book, words, hours, day):
    """Add finished words; return the number of milestones newly reached."""
    book.hours += hours
    book.words_left = max(0.0, book.words_left - words)
    reached = 0
    while not book.finished and book.words_left <= book.milestone_marks[book.milestones_done] + 1e-9:
        book.milestones_done += 1
        book.milestone_days.append(day)
        reached += 1
    return reached
