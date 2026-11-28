"""The character's own book (SIM_BASELINE.md §3.4, v0.3): H hours of hard chapters left, +-5%."""
from dataclasses import dataclass, field

from .rng import stream


@dataclass
class Book:
    remaining_hours_nominal: float     # hours left at the start, at the base 150 w/h
    words_total_remaining: float
    words_left: float
    milestone_marks: list              # words_left values at which milestones are reached
    milestones_done: int = 0
    hours: float = 0.0
    milestone_days: list = field(default_factory=list)

    @property
    def finished(self):
        return self.milestones_done >= len(self.milestone_marks)

    def last_milestone_share(self):
        """Share of the current (next) milestone already done."""
        n = len(self.milestone_marks)
        if self.finished:
            return 1.0
        size = self.words_total_remaining / n
        start = self.words_total_remaining * (1 - self.milestones_done / n)
        return (start - self.words_left) / size

    def near_finished(self, last_share):
        """All but the last milestone done and at least `last_share` of the last one."""
        n = len(self.milestone_marks)
        return not self.finished and self.milestones_done == n - 1 and self.last_milestone_share() >= last_share - 1e-9


def new_book(cfg, seed):
    b = cfg["book"]
    variation = b["remaining_hours_variation"]
    hours = b["remaining_hours"] * stream(seed, "book").uniform(1 - variation, 1 + variation)
    words = hours * b["words_per_hour"]
    n = b["milestones"]
    marks = [words * (1 - (i + 1) / n) for i in range(n)]
    return Book(hours, words, words, marks)


def implied_start_progress(cfg, hours=None):
    """Share of the book done at the start, for the story text (whole book = total_hours_reference)."""
    b = cfg["book"]
    return 1 - (b["remaining_hours"] if hours is None else hours) / b["total_hours_reference"]


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
