"""Run reproducible multi-seed benchmarks without launching the UI."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from firehawk.scenarios import create_scenario, available_presets
from firehawk.simulation import compare_modes

DEFAULT_DRONES = {"Calm & Clear": 4, "Windy & Dry": 2, "Near Buildings": 4, "Resource Constrained": 2, "Randomized Scenario": 4}


def main():
    parser = argparse.ArgumentParser(description="FireHawk multi-seed comparison benchmark")
    parser.add_argument("--presets", nargs="+", choices=available_presets(), default=available_presets())
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 13, 29, 47, 71])
    parser.add_argument("--steps", type=int, default=65)
    parser.add_argument("--out", default="results/multi_seed_benchmark.csv")
    args = parser.parse_args()
    rows = []
    for preset in args.presets:
        for seed in args.seeds:
            scenario = create_scenario(preset, seed=seed, drone_count=DEFAULT_DRONES[preset], steps=args.steps)
            compared = compare_modes(scenario, keep_history=False)
            for key in ("baseline", "optimized"):
                result = compared[key]
                rows.append({"preset": preset, "seed": seed, "steps": args.steps,
                    "dryness": scenario.dryness, "wind_speed": scenario.wind_speed, "wind_dir": scenario.wind_dir,
                    "drone_count": scenario.drone_count, "algorithm": result["mode_label"], **result["metrics"]})
            b, o = compared["baseline"]["metrics"], compared["optimized"]["metrics"]
            print(f"{preset:22s} seed={seed:5d} | burned {b['burned_area_cells']:3d}->{o['burned_area_cells']:3d} | buildings {b['buildings_damaged']}->{o['buildings_damaged']} | exposure {b['building_exposure_units']:.1f}->{o['building_exposure_units']:.1f}")
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} result rows to {target}")

if __name__ == "__main__":
    main()
