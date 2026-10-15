"""Deterministic wildfire-and-drone simulator for the FireHawk AAT demonstration.

This is an educational grid model, not a physical wildfire forecast or operational tool.
"""
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Any

from .scenarios import Scenario, FOREST, SCRUB, FIREBREAK, BUILDING, WATER, BASE
from .fuzzy import fuzzy_urgency
from .genetic import optimize_assignments

NEIGHBORS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
WIND_VEC = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}


@dataclass
class Drone:
    drone_id: int
    x: int
    y: int
    water: float
    water_capacity: float
    battery: float = 100.0
    target: tuple[int, int] | None = None
    status: str = "idle"
    distance_travelled: int = 0
    drops_used: int = 0
    suppression_events: int = 0

    def public(self) -> dict[str, Any]:
        return {
            "id": self.drone_id, "x": self.x, "y": self.y,
            "water": round(self.water, 1), "water_capacity": self.water_capacity,
            "battery": round(self.battery, 1), "target": self.target,
            "status": self.status, "distance_travelled": self.distance_travelled,
            "drops_used": self.drops_used, "suppression_events": self.suppression_events,
        }


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _build_noise(scenario: Scenario) -> list[list[list[float]]]:
    # Separate deterministic stream means the same ignition/noise field is used for both policies.
    rng = random.Random(scenario.seed * 104729 + 731)
    return [[[rng.random() for _ in range(scenario.width)] for _ in range(scenario.height)] for _ in range(scenario.steps)]


def _count_burning(fire_status: list[list[int]]) -> int:
    return sum(1 for row in fire_status for v in row if v == 1)


def _make_snapshot(step, terrain, fire_status, intensity, drones, metrics, scenario):
    return {
        "step": step,
        "terrain": [row[:] for row in terrain],
        "fire_status": [row[:] for row in fire_status],
        "intensity": [[round(v, 2) for v in row] for row in intensity],
        "drones": [d.public() for d in drones],
        "metrics": dict(metrics),
        "base": scenario.base,
    }


def _flammable(terrain_val: int) -> bool:
    return terrain_val in (FOREST, SCRUB)


def _spread_fire(
    t: int,
    scenario: Scenario,
    terrain: list[list[int]],
    fire_status: list[list[int]],
    intensity: list[list[float]],
    fire_age: list[list[int]],
    noise: list[list[list[float]]],
) -> None:
    h, w = scenario.height, scenario.width
    # Aging / burn-out is handled on a copy to avoid order-dependent fire dynamics.
    new_status = [row[:] for row in fire_status]
    new_intensity = [row[:] for row in intensity]
    new_age = [row[:] for row in fire_age]
    spread_prob = [[0.0 for _ in range(w)] for _ in range(h)]
    wx, wy = WIND_VEC.get(scenario.wind_dir, (1, 0))
    for y in range(h):
        for x in range(w):
            if fire_status[y][x] != 1:
                continue
            age = fire_age[y][x] + 1
            new_age[y][x] = age
            new_intensity[y][x] = min(1.0, 0.56 + 0.10 * age)
            max_burn = 6 + int(round(scenario.dryness * 3.0))
            if age >= max_burn:
                new_status[y][x] = 2
                new_intensity[y][x] = 0.0
                continue
            source_intensity = new_intensity[y][x]
            for dx, dy in NEIGHBORS:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                if fire_status[ny][nx] != 0 or not _flammable(terrain[ny][nx]):
                    continue
                align = dx * wx + dy * wy
                wind_factor = 1.0 + scenario.wind_speed * (0.78 if align > 0 else (-0.38 if align < 0 else 0.0))
                fuel_factor = 1.0 if terrain[ny][nx] == FOREST else 0.70
                p = (0.15 + 0.34 * scenario.dryness) * fuel_factor * source_intensity * wind_factor
                p = _clamp(p, 0.0, 0.82)
                # Independent attempts combine into a cumulative ignition probability.
                spread_prob[ny][nx] = 1.0 - (1.0 - spread_prob[ny][nx]) * (1.0 - p)
    for y in range(h):
        for x in range(w):
            if fire_status[y][x] == 0 and _flammable(terrain[y][x]) and noise[y][x] < spread_prob[y][x]:
                new_status[y][x] = 1
                new_intensity[y][x] = 0.58
                new_age[y][x] = 0
    for y in range(h):
        fire_status[y][:] = new_status[y]
        intensity[y][:] = new_intensity[y]
        fire_age[y][:] = new_age[y]


def _building_risk(x, y, buildings):
    if not buildings:
        return 0.0
    d = min(_manhattan((x, y), b) for b in buildings)
    return _clamp((7.0 - d) / 6.0)


def _spread_potential(x, y, scenario, terrain, fire_status):
    unburnt = 0
    for dx, dy in NEIGHBORS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < scenario.width and 0 <= ny < scenario.height:
            if fire_status[ny][nx] == 0 and _flammable(terrain[ny][nx]):
                unburnt += 1
    front = unburnt / 4.0
    return _clamp(0.44 * scenario.dryness + 0.30 * scenario.wind_speed + 0.26 * front)


def hotspot_urgencies(scenario, terrain, fire_status, intensity):
    hotspots = []
    values = {}
    for y in range(scenario.height):
        for x in range(scenario.width):
            if fire_status[y][x] != 1:
                continue
            it = _clamp(intensity[y][x])
            building_threat = _building_risk(x, y, scenario.buildings)
            spread = _spread_potential(x, y, scenario, terrain, fire_status)
            # Explicit fuzzy controller; all three normalized inputs have Low/Medium/High sets.
            risk = fuzzy_urgency(it, building_threat, spread)
            # Slightly reward exposed fire-front cells, not just cells near buildings.
            local_front = sum(1 for dx, dy in NEIGHBORS
                              if 0 <= x + dx < scenario.width and 0 <= y + dy < scenario.height
                              and fire_status[y + dy][x + dx] == 0
                              and _flammable(terrain[y + dy][x + dx])) / 4.0
            risk = _clamp(0.88 * risk + 0.12 * local_front)
            p = (x, y)
            hotspots.append(p)
            values[p] = risk
    return hotspots, values


def _greedy_assignments(drones: list[Drone], hotspots: list[tuple[int, int]]):
    assignments: dict[int, tuple[int, int] | None] = {}
    remaining = hotspots[:]
    # Nearest-fire baseline with a simple duplicate-avoidance rule.
    active = [d for d in drones if d.status not in ("returning", "recharging")]
    for d in active:
        pos = (d.x, d.y)
        candidates = remaining or hotspots
        if not candidates:
            assignments[d.drone_id] = None
            continue
        target = min(candidates, key=lambda p: (_manhattan(pos, p), p[1], p[0]))
        assignments[d.drone_id] = target
        if target in remaining:
            remaining.remove(target)
    for d in drones:
        assignments.setdefault(d.drone_id, None)
    return assignments


def _genetic_assignments(drones, hotspots, urgency, scenario, step):
    active = [d for d in drones if d.status not in ("returning", "recharging")]
    if not active or not hotspots:
        return {d.drone_id: None for d in drones}
    # Bound chromosome size to the highest-urgency burning cells. A small pool keeps dispatch fast.
    candidates = sorted(hotspots, key=lambda p: urgency[p], reverse=True)[:42]
    assignments = optimize_assignments(
        options=candidates,
        drone_positions=[(d.x, d.y) for d in active],
        urgency=urgency,
        battery=[d.battery for d in active],
        base=scenario.base,
        seed=scenario.seed * 1009 + step * 37 + 5,
        population_size=16,
        generations=6,
        current_targets=[d.target for d in active],
    )
    out = {d.drone_id: t for d, t in zip(active, assignments)}
    for d in drones:
        out.setdefault(d.drone_id, None)
    return out


def _move_towards(drone: Drone, target: tuple[int, int], speed: int = 3) -> int:
    moved = 0
    tx, ty = target
    while moved < speed and (drone.x, drone.y) != (tx, ty):
        # Deterministic Manhattan path: horizontal first, then vertical.
        if drone.x != tx:
            drone.x += 1 if tx > drone.x else -1
        elif drone.y != ty:
            drone.y += 1 if ty > drone.y else -1
        moved += 1
    drone.distance_travelled += moved
    drone.battery = max(0.0, drone.battery - 0.78 * moved)
    return moved


def _suppress(drone: Drone, fire_status, intensity, terrain) -> int:
    """One water drop suppresses the target plus its immediate four-neighbour area."""
    if drone.water < 1.0 or drone.battery < 2.0:
        return 0
    affected = []
    for dx, dy in [(0, 0)] + NEIGHBORS:
        x, y = drone.x + dx, drone.y + dy
        if 0 <= y < len(fire_status) and 0 <= x < len(fire_status[0]) and fire_status[y][x] == 1:
            affected.append((x, y))
    if not affected:
        return 0
    drone.water -= 1.0
    drone.battery = max(0.0, drone.battery - 2.8)
    drone.drops_used += 1
    drone.suppression_events += 1
    extinguished = 0
    for x, y in affected:
        # A drop reduces intensity; very intense cells may require another pass.
        intensity[y][x] = max(0.0, intensity[y][x] - (0.78 if (x, y) == (drone.x, drone.y) else 0.66))
        if intensity[y][x] <= 0.22:
            fire_status[y][x] = 2
            intensity[y][x] = 0.0
            extinguished += 1
    return extinguished


def _metrics_snapshot(scenario, terrain, fire_status, intensity, drones, exposure_total, building_heat, step, peak_fire, suppression_count):
    burned_area = sum(1 for y in range(scenario.height) for x in range(scenario.width)
                      if fire_status[y][x] in (1, 2) and _flammable(terrain[y][x]))
    burning = _count_burning(fire_status)
    damaged = sum(1 for b in scenario.buildings if building_heat[b[1]][b[0]] >= 2.5)
    return {
        "step": step,
        "burned_area_cells": burned_area,
        "active_fire_cells": burning,
        "peak_active_fire_cells": peak_fire,
        "buildings_damaged": damaged,
        "buildings_saved": len(scenario.buildings) - damaged,
        "building_exposure_units": round(exposure_total, 2),
        "water_drops_used": sum(d.drops_used for d in drones),
        "drone_distance_cells": sum(d.distance_travelled for d in drones),
        "suppression_actions": suppression_count,
        "remaining_water": round(sum(d.water for d in drones), 1),
        "remaining_battery_pct": round(sum(d.battery for d in drones) / max(1, len(drones)), 1),
    }


def run_simulation(scenario: Scenario, mode: str = "firehawk", keep_history: bool = True) -> dict[str, Any]:
    """Run one policy. mode is 'nearest' or 'firehawk'. Same scenario seed gives paired spread noise."""
    if mode not in ("nearest", "firehawk"):
        raise ValueError("mode must be 'nearest' or 'firehawk'")
    terrain = [list(row) for row in scenario.terrain]
    w, h = scenario.width, scenario.height
    fire_status = [[0 for _ in range(w)] for _ in range(h)]
    intensity = [[0.0 for _ in range(w)] for _ in range(h)]
    fire_age = [[0 for _ in range(w)] for _ in range(h)]
    for x, y in scenario.initial_fires:
        fire_status[y][x] = 1
        intensity[y][x] = 0.58
        fire_age[y][x] = 0
    drones = [Drone(i + 1, scenario.base[0], scenario.base[1], float(scenario.water_capacity), float(scenario.water_capacity)) for i in range(scenario.drone_count)]
    noise = _build_noise(scenario)
    building_heat = [[0.0 for _ in range(w)] for _ in range(h)]
    exposure_total = 0.0
    peak_fire = _count_burning(fire_status)
    suppression_count = 0
    first_suppression_step = None
    containment_step = None
    history = []
    metrics = _metrics_snapshot(scenario, terrain, fire_status, intensity, drones, exposure_total, building_heat, 0, peak_fire, suppression_count)
    if keep_history:
        history.append(_make_snapshot(0, terrain, fire_status, intensity, drones, metrics, scenario))

    for step in range(scenario.steps):
        _spread_fire(step, scenario, terrain, fire_status, intensity, fire_age, noise[step])
        active_count = _count_burning(fire_status)
        peak_fire = max(peak_fire, active_count)
        # Account for cumulative exposure and persistent building damage.
        for bx, by in scenario.buildings:
            adjacent_intensity = 0.0
            for dx, dy in NEIGHBORS:
                nx, ny = bx + dx, by + dy
                if 0 <= nx < w and 0 <= ny < h and fire_status[ny][nx] == 1:
                    adjacent_intensity = max(adjacent_intensity, intensity[ny][nx])
            exposure_total += adjacent_intensity
            building_heat[by][bx] += adjacent_intensity * 0.65

        # Resource management: return when water is out or battery reserve cannot cover a safe return.
        for d in drones:
            distance_home = _manhattan((d.x, d.y), scenario.base)
            if d.status not in ("returning", "recharging") and (d.water < 1.0 or d.battery < distance_home * 0.78 + 14.0):
                d.status = "returning"
                d.target = scenario.base

        # Dispatch every three ticks, or immediately when an assigned target stops burning.
        targets_valid = all((d.target is None or _target_has_fire(d.target, fire_status)) for d in drones if d.status not in ("returning", "recharging"))
        dispatch_now = (step % 6 == 0) or not targets_valid
        if dispatch_now:
            hotspots, urgency = hotspot_urgencies(scenario, terrain, fire_status, intensity)
            if mode == "nearest":
                assignments = _greedy_assignments(drones, hotspots)
            else:
                assignments = _genetic_assignments(drones, hotspots, urgency, scenario, step)
            for d in drones:
                if d.status in ("returning", "recharging"):
                    continue
                assigned = assignments.get(d.drone_id)
                d.target = assigned
                d.status = "idle" if assigned is None else "enroute"

        # Move and suppress. Drones can fly over terrain; fire spread remains ground-constrained.
        for d in drones:
            if d.status == "returning":
                _move_towards(d, scenario.base, speed=3)
                if (d.x, d.y) == scenario.base:
                    d.status = "recharging"
                    d.target = None
                continue
            if d.status == "recharging":
                d.water = min(d.water_capacity, d.water + 1.8)
                d.battery = min(100.0, d.battery + 16.0)
                if d.water >= d.water_capacity - 0.01 and d.battery >= 99.5:
                    d.water = d.water_capacity
                    d.battery = 100.0
                    d.status = "idle"
                continue
            if d.target is None:
                d.status = "idle"
                continue
            if not _target_has_fire(d.target, fire_status):
                d.target = None
                d.status = "idle"
                continue
            if _manhattan((d.x, d.y), d.target) > 1:
                _move_towards(d, d.target, speed=3)
            if _manhattan((d.x, d.y), d.target) <= 1:
                d.status = "suppressing"
                before = _count_burning(fire_status)
                extinguished = _suppress(d, fire_status, intensity, terrain)
                after = _count_burning(fire_status)
                if extinguished > 0:
                    suppression_count += extinguished
                    if first_suppression_step is None:
                        first_suppression_step = step + 1
                if d.water < 1.0 or d.battery < _manhattan((d.x, d.y), scenario.base) * 0.78 + 14.0:
                    d.status = "returning"
                    d.target = scenario.base
                elif not _target_has_fire(d.target, fire_status):
                    d.target = None
                    d.status = "idle"

        burning_after = _count_burning(fire_status)
        if burning_after == 0 and containment_step is None:
            containment_step = step + 1
        metrics = _metrics_snapshot(scenario, terrain, fire_status, intensity, drones, exposure_total, building_heat, step + 1, peak_fire, suppression_count)
        if keep_history:
            history.append(_make_snapshot(step + 1, terrain, fire_status, intensity, drones, metrics, scenario))

    final_metrics = _metrics_snapshot(scenario, terrain, fire_status, intensity, drones, exposure_total, building_heat, scenario.steps, peak_fire, suppression_count)
    final_metrics["first_suppression_step"] = first_suppression_step
    final_metrics["containment_step"] = containment_step
    final_metrics["contained_by_end"] = _count_burning(fire_status) == 0
    final_metrics["total_buildings"] = len(scenario.buildings)
    final_metrics["total_drones"] = len(drones)
    # Single composite index for quick display only; individual metrics always remain visible.
    final_metrics["impact_score"] = round(
        0.50 * final_metrics["burned_area_cells"]
        + 5.5 * final_metrics["buildings_damaged"]
        + 0.025 * final_metrics["building_exposure_units"]
        + 0.10 * final_metrics["drone_distance_cells"], 2
    )
    return {
        "mode": mode,
        "mode_label": "Fuzzy + Genetic Algorithm" if mode == "firehawk" else "Nearest-Hotspot Baseline",
        "scenario": scenario,
        "metrics": final_metrics,
        "history": history,
        "final_terrain": terrain,
        "final_fire_status": fire_status,
        "final_intensity": intensity,
        "drones": [d.public() for d in drones],
    }


def _target_has_fire(target, fire_status):
    if target is None:
        return False
    x, y = target
    return 0 <= y < len(fire_status) and 0 <= x < len(fire_status[0]) and fire_status[y][x] == 1


def compare_modes(scenario: Scenario, keep_history: bool = True) -> dict[str, Any]:
    """Run the baseline and FireHawk under exactly the same starting conditions/noise field."""
    baseline = run_simulation(scenario, "nearest", keep_history=keep_history)
    optimized = run_simulation(scenario, "firehawk", keep_history=keep_history)
    return {"scenario": scenario, "baseline": baseline, "optimized": optimized}


def comparison_rows(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, label in [("baseline", "Nearest-hotspot baseline"), ("optimized", "FireHawk fuzzy + GA")]:
        m = comparison[key]["metrics"]
        rows.append({"Controller": label, **m})
    return rows
