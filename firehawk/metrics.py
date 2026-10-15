"""Comparison helpers, report-friendly metrics, and percentage calculations."""
from __future__ import annotations


def delta_pct(baseline: float, optimized: float, lower_is_better: bool = True):
    """Return positive values for improvement; avoid unstable percentages around zero."""
    if abs(baseline) < 1e-9:
        return None
    if lower_is_better:
        return (baseline - optimized) / abs(baseline) * 100.0
    return (optimized - baseline) / abs(baseline) * 100.0


def compare_metrics(baseline: dict, optimized: dict) -> list[dict]:
    specs = [
        ("Burned area (cells)", "burned_area_cells", True, "Ground cells ignited during the run."),
        ("Buildings damaged", "buildings_damaged", True, "Buildings whose cumulative heat exposure crossed the model threshold."),
        ("Building exposure (units)", "building_exposure_units", True, "Cumulative intensity adjacent to buildings; model units, not a physical dose."),
        ("Peak active fire cells", "peak_active_fire_cells", True, "Largest simultaneous burning front."),
        ("Water drops used", "water_drops_used", None, "Resource-use indicator; lower is not automatically better if fire outcomes worsen."),
        ("Drone distance (cells)", "drone_distance_cells", True, "Total grid-cell movement by the fleet."),
    ]
    out = []
    for title, key, lower, description in specs:
        b, o = baseline.get(key, 0), optimized.get(key, 0)
        improvement = None if lower is None else delta_pct(float(b), float(o), lower_is_better=lower)
        out.append({"metric": title, "key": key, "baseline": b, "optimized": o, "improvement_pct": improvement, "description": description})
    return out


def winner_summary(baseline: dict, optimized: dict) -> str:
    # Main outcome is deliberately not one opaque aggregate score.
    b_damage, o_damage = baseline["buildings_damaged"], optimized["buildings_damaged"]
    b_burn, o_burn = baseline["burned_area_cells"], optimized["burned_area_cells"]
    b_exp, o_exp = baseline["building_exposure_units"], optimized["building_exposure_units"]
    wins = int(o_damage < b_damage) + int(o_burn < b_burn) + int(o_exp < b_exp)
    ties = int(o_damage == b_damage) + int(o_burn == b_burn) + int(o_exp == b_exp)
    if o_damage < b_damage and o_burn <= b_burn:
        return "FireHawk protects more buildings and does not increase burned area in this run."
    if wins >= 2:
        return "FireHawk improves at least two of the three primary impact metrics in this run."
    if wins == 0 and ties == 3:
        return "The two strategies are tied on the primary impact metrics in this run."
    return "This scenario is mixed: inspect burned area, building exposure, and resource use separately."
