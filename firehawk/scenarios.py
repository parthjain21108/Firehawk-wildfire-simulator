"""Scenario generation for FireHawk. All environments are deterministic for a given seed."""
from __future__ import annotations
from dataclasses import dataclass
import random
from typing import Tuple

FOREST = 0
SCRUB = 1
FIREBREAK = 2
BUILDING = 3
WATER = 4
BASE = 5
TERRAIN_NAMES = {FOREST: "Forest", SCRUB: "Scrub", FIREBREAK: "Firebreak / road", BUILDING: "Building", WATER: "Water", BASE: "Drone base"}


@dataclass(frozen=True)
class Scenario:
    name: str
    preset: str
    seed: int
    width: int
    height: int
    steps: int
    drone_count: int
    water_capacity: int
    dryness: float
    wind_speed: float
    wind_dir: str
    terrain: Tuple[Tuple[int, ...], ...]
    buildings: Tuple[Tuple[int, int], ...]
    initial_fires: Tuple[Tuple[int, int], ...]
    base: Tuple[int, int]
    notes: str = ""


def _wind_and_dryness(preset: str, rng: random.Random):
    profiles = {
        "Calm & Clear": (0.34, 0.20, "E", 4, "Low wind and moderate fuel dryness; good for learning the controls."),
        "Windy & Dry": (0.91, 0.90, "E", 3, "Strong eastward wind and dry fuel make rapid spread more likely."),
        "Near Buildings": (0.67, 0.48, "N", 3, "The ignition is placed near a cluster of buildings."),
        "Resource Constrained": (0.79, 0.65, "W", 2, "Fewer drones and smaller water loads test resource allocation."),
    }
    if preset == "Randomized Scenario":
        return (rng.uniform(0.35, 0.98), rng.uniform(0.15, 0.95), rng.choice(["N", "E", "S", "W"]), rng.randint(2, 5), "Randomly generated weather and ignition conditions, reproducible using the displayed seed.")
    return profiles.get(preset, profiles["Calm & Clear"])


def create_scenario(
    preset: str = "Calm & Clear",
    seed: int = 42,
    drone_count: int | None = None,
    steps: int = 65,
    dryness_override: float | None = None,
    wind_override: float | None = None,
    wind_dir_override: str | None = None,
    width: int = 24,
    height: int = 16,
) -> Scenario:
    """Create a deterministic environment. Same scenario object is used by both algorithms."""
    rng = random.Random(int(seed))
    dryness, wind_speed, wind_dir, profile_drones, notes = _wind_and_dryness(preset, rng)
    if dryness_override is not None:
        dryness = max(0.1, min(1.0, float(dryness_override)))
    if wind_override is not None:
        wind_speed = max(0.0, min(1.0, float(wind_override)))
    if wind_dir_override is not None:
        if wind_dir_override not in ("N", "E", "S", "W"):
            raise ValueError("wind_dir_override must be one of N, E, S, W")
        wind_dir = wind_dir_override
    drones = int(drone_count if drone_count is not None else profile_drones)
    drones = max(1, min(7, drones))
    width = max(16, min(32, int(width)))
    height = max(12, min(22, int(height)))
    steps = max(25, min(100, int(steps)))

    # A mixed forest/scrub map, then deterministic road/firebreak corridors.
    terrain = [[(SCRUB if rng.random() < 0.22 else FOREST) for _ in range(width)] for _ in range(height)]
    for y in [height // 3, (2 * height) // 3]:
        for x in range(width):
            if rng.random() > 0.18:
                terrain[y][x] = FIREBREAK
    for x in [width // 3, (2 * width) // 3]:
        for y in range(height):
            if rng.random() > 0.30:
                terrain[y][x] = FIREBREAK
    # Small ponds act as non-flammable barriers.
    for _ in range(max(2, width // 8)):
        cx, cy = rng.randrange(2, width - 2), rng.randrange(2, height - 2)
        if terrain[cy][cx] != FIREBREAK:
            terrain[cy][cx] = WATER
            if rng.random() < 0.45 and cx + 1 < width - 1 and terrain[cy][cx + 1] != FIREBREAK:
                terrain[cy][cx + 1] = WATER

    base = (1, height - 2)
    bx, by = base
    terrain[by][bx] = BASE
    # Ensure a small launch clearing around the base.
    for nx, ny in [(bx + 1, by), (bx, by - 1), (bx + 1, by - 1)]:
        if 0 <= nx < width and 0 <= ny < height and terrain[ny][nx] not in (BUILDING, WATER):
            terrain[ny][nx] = FIREBREAK

    # Buildings cluster in the right/central-right sector, away from the launch pad.
    candidates = []
    for y in range(1, height - 1):
        for x in range(width // 2, width - 1):
            if terrain[y][x] in (FOREST, SCRUB) and abs(x - bx) + abs(y - by) > 7:
                candidates.append((x, y))
    rng.shuffle(candidates)
    buildings = []
    target_buildings = 9
    for pos in candidates:
        if all(abs(pos[0] - q[0]) + abs(pos[1] - q[1]) >= 2 for q in buildings):
            buildings.append(pos)
            terrain[pos[1]][pos[0]] = BUILDING
            if len(buildings) >= target_buildings:
                break
    # Ensure a minimum number of buildings on very constrained maps.
    if len(buildings) < 5:
        for y in range(2, height - 2, 3):
            x = width - 3
            if terrain[y][x] not in (WATER, BASE):
                terrain[y][x] = BUILDING
                if (x, y) not in buildings:
                    buildings.append((x, y))

    fuel_cells = [(x, y) for y in range(1, height - 1) for x in range(1, width - 1) if terrain[y][x] in (FOREST, SCRUB)]
    # Choose fire start according to the environment type.
    if preset == "Near Buildings" and buildings:
        candidates = sorted(fuel_cells, key=lambda p: min(abs(p[0]-b[0]) + abs(p[1]-b[1]) for b in buildings))
        # Randomize among the nearest several eligible cells to keep scenarios varied by seed.
        near = candidates[:max(5, min(18, len(candidates)))]
        fire_start = rng.choice(near)
    elif preset == "Windy & Dry":
        left = [p for p in fuel_cells if p[0] < width * 0.34]
        fire_start = rng.choice(left or fuel_cells)
    elif preset == "Resource Constrained":
        remote = [p for p in fuel_cells if p[0] > width * 0.48 and p[1] < height * 0.45]
        fire_start = rng.choice(remote or fuel_cells)
    else:
        center_left = [p for p in fuel_cells if width * 0.22 < p[0] < width * 0.56 and height * 0.2 < p[1] < height * 0.75]
        fire_start = rng.choice(center_left or fuel_cells)

    initial_fires = [fire_start]
    # Select additional ignition cells nearby to create a small, visible initial front.
    nearby = [p for p in fuel_cells if p != fire_start and abs(p[0]-fire_start[0]) + abs(p[1]-fire_start[1]) <= 3]
    rng.shuffle(nearby)
    initial_count = 4 if preset == "Windy & Dry" else (2 if preset == "Calm & Clear" else 3)
    for p in nearby:
        if len(initial_fires) >= initial_count:
            break
        if all(abs(p[0]-q[0]) + abs(p[1]-q[1]) >= 2 for q in initial_fires):
            initial_fires.append(p)
    for x, y in initial_fires:
        terrain[y][x] = FOREST if terrain[y][x] not in (SCRUB,) else SCRUB

    return Scenario(
        name=preset,
        preset=preset,
        seed=int(seed),
        width=width,
        height=height,
        steps=steps,
        drone_count=drones,
        water_capacity=5 if preset == "Resource Constrained" else 7,
        dryness=round(float(dryness), 3),
        wind_speed=round(float(wind_speed), 3),
        wind_dir=wind_dir,
        terrain=tuple(tuple(row) for row in terrain),
        buildings=tuple(buildings),
        initial_fires=tuple(initial_fires),
        base=base,
        notes=notes,
    )


def random_scenario(seed: int, **kwargs) -> Scenario:
    return create_scenario("Randomized Scenario", seed=seed, **kwargs)


def available_presets():
    return ["Calm & Clear", "Windy & Dry", "Near Buildings", "Resource Constrained", "Randomized Scenario"]
