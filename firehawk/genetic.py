"""A small manually implemented genetic algorithm for drone-to-hotspot assignments."""
from __future__ import annotations
import random
from typing import Sequence


def _fitness(chromosome: Sequence[int], options: Sequence[tuple[int, int]], drone_positions: Sequence[tuple[int, int]], urgency: dict[tuple[int, int], float], battery: Sequence[float], base: tuple[int, int], current_targets: Sequence[tuple[int, int] | None] | None = None) -> float:
    score = 0.0
    chosen = []
    for idx, gene in enumerate(chromosome):
        if gene < 0 or gene >= len(options):
            score -= 4.0
            chosen.append(None)
            continue
        target = options[gene]
        x, y = drone_positions[idx]
        distance = abs(target[0] - x) + abs(target[1] - y)
        return_distance = abs(target[0] - base[0]) + abs(target[1] - base[1])
        # Prioritize fuzzy urgency, but avoid targets beyond safe battery range.
        urgency_value = urgency[target]
        if current_targets is not None and idx < len(current_targets) and current_targets[idx] is not None:
            # Retain a still-burning assignment unless a new target is meaningfully more urgent.
            score += 18.0 if target == current_targets[idx] else -4.0
        battery_margin = battery[idx] - (distance + return_distance) * 1.05 - 12.0
        if battery_margin < 0:
            score -= 60.0 + abs(battery_margin)
        score += 128.0 * urgency_value - 1.15 * distance - 0.18 * return_distance
        chosen.append(target)
    # Encourage useful coverage while discouraging redundant assignments to the same patch.
    for i in range(len(chosen)):
        for j in range(i + 1, len(chosen)):
            if chosen[i] is None or chosen[j] is None:
                continue
            d = abs(chosen[i][0] - chosen[j][0]) + abs(chosen[i][1] - chosen[j][1])
            if d == 0:
                score -= 20.0
            elif d <= 2:
                score -= 5.0
    score += 12.0 * len(set(c for c in chosen if c is not None))
    return score


def optimize_assignments(
    options: Sequence[tuple[int, int]],
    drone_positions: Sequence[tuple[int, int]],
    urgency: dict[tuple[int, int], float],
    battery: Sequence[float],
    base: tuple[int, int],
    seed: int,
    population_size: int = 18,
    generations: int = 7,
    current_targets: Sequence[tuple[int, int] | None] | None = None,
) -> list[tuple[int, int] | None]:
    """Return one target cell per drone. All GA operators are implemented here, no optimizer library."""
    n_drones = len(drone_positions)
    if not options or n_drones == 0:
        return [None] * n_drones
    rng = random.Random(seed)
    pop_size = max(6, int(population_size))
    gens = max(1, int(generations))
    chromosome_len = n_drones
    # Seed the population with a fuzzy-risk-biased heuristic, then diversify randomly.
    # The fitness penalizes redundant assignments; the GA can still coordinate multiple
    # drones on the same critical patch when that scores better than spreading them out.
    population: list[list[int]] = []
    greedy = []
    for pos in drone_positions:
        gene = min(range(len(options)), key=lambda k: (
            -urgency[options[k]] * 0.7
            + (abs(options[k][0]-pos[0]) + abs(options[k][1]-pos[1])) / 50.0
        ))
        greedy.append(gene)
    population.append(greedy)
    for _ in range(pop_size - 1):
        population.append([rng.randrange(len(options)) for _ in range(chromosome_len)])

    def score(ch):
        return _fitness(ch, options, drone_positions, urgency, battery, base, current_targets)

    best = max(population, key=score)[:]
    best_score = score(best)
    for _ in range(gens):
        scored = sorted(((score(ch), ch) for ch in population), key=lambda item: item[0], reverse=True)
        if scored[0][0] > best_score:
            best_score, best = scored[0][0], scored[0][1][:]
        # Elitism retains the two best candidates.
        next_pop = [scored[0][1][:], scored[min(1, len(scored)-1)][1][:]]
        while len(next_pop) < pop_size:
            # Tournament selection.
            def tournament():
                contestants = rng.sample(population, k=min(3, len(population)))
                return max(contestants, key=score)
            p1, p2 = tournament(), tournament()
            child = p1[:]
            # Uniform crossover across assignment genes.
            if rng.random() < 0.85:
                child = [p1[i] if rng.random() < 0.5 else p2[i] for i in range(chromosome_len)]
            # Mutation changes one or more drone targets.
            for i in range(chromosome_len):
                if rng.random() < 0.18:
                    child[i] = rng.randrange(len(options))
            next_pop.append(child)
        population = next_pop
    final_best = max(population + [best], key=score)
    return [options[g] if 0 <= g < len(options) else None for g in final_best]
