"""Calendar: days, weekdays and weeks. Day 1 is a Monday."""


def weekday(day):
    """1 = Monday ... 7 = Sunday."""
    return (day - 1) % 7 + 1


def is_weekend(day):
    return weekday(day) >= 6


def week_of(day):
    return (day - 1) // 7 + 1


def is_week_end(day):
    return weekday(day) == 7


def add_working_days(day, count):
    """The day that is `count` weekdays after `day` (count >= 1)."""
    current = day
    while count > 0:
        current += 1
        if not is_weekend(current):
            count -= 1
    return current


def days_in_range(start, end):
    return range(start, end + 1)
