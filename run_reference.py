"""Regenerate the deterministic default reference comparison and per-tick timeline."""
from pathlib import Path
import csv
from firehawk.scenarios import create_scenario
from firehawk.simulation import compare_modes

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
scenario = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=65)
comparison = compare_modes(scenario, keep_history=True)
summary_rows = []
timeline_rows = []
for key in ("baseline", "optimized"):
    run = comparison[key]
    summary_rows.append({
        "scenario": scenario.preset,
        "seed": scenario.seed,
        "steps": scenario.steps,
        "dryness": scenario.dryness,
        "wind_speed": scenario.wind_speed,
        "wind_direction": scenario.wind_dir,
        "drone_count": scenario.drone_count,
        "algorithm": run["mode_label"],
        **run["metrics"],
    })
    for snap in run["history"]:
        timeline_rows.append({"algorithm": run["mode_label"], **snap["metrics"]})
for name, rows in [("reference_comparison.csv", summary_rows), ("reference_timeline.csv", timeline_rows)]:
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
print("FireHawk reference comparison")
for row in summary_rows:
    print(row["algorithm"], "| burned", row["burned_area_cells"], "| buildings damaged", row["buildings_damaged"], "| exposure", row["building_exposure_units"], "| contained", row["contained_by_end"])
print(f"Saved {len(summary_rows)} summary rows and {len(timeline_rows)} timeline rows to results/.")
