"""Seeded random streams.

Every random draw comes from a named stream derived from (seed, name, keys). Streams that
must not depend on the player's choices (offers, interruptions, costs, payment lateness)
are keyed by day or job id, so all policies see the same world for the same seed
("common random numbers"). Python's str seeding is deterministic across runs.
"""
import math
import random


def stream(seed, name, *keys):
    return random.Random("|".join(str(part) for part in (seed, name, *keys)))


def poisson(rng, mean):
    """Knuth's method; fine for small means."""
    limit = math.exp(-mean)
    count, product = 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count


def weighted_choice(rng, items, weights):
    total = sum(weights)
    pick = rng.random() * total
    for item, weight in zip(items, weights):
        pick -= weight
        if pick < 0:
            return item
    return items[-1]
