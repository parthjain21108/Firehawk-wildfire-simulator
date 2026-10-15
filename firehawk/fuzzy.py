"""Hand-written fuzzy urgency inference used by FireHawk."""
from __future__ import annotations


def shoulder_low(x: float, full_until: float = 0.25, zero_at: float = 0.65) -> float:
    if x <= full_until:
        return 1.0
    if x >= zero_at:
        return 0.0
    return (zero_at - x) / (zero_at - full_until)


def triangle(x: float, left: float, peak: float, right: float) -> float:
    if x <= left or x >= right:
        return 0.0
    if x == peak:
        return 1.0
    if x < peak:
        return (x - left) / (peak - left)
    return (right - x) / (right - peak)


def shoulder_high(x: float, zero_at: float = 0.35, full_from: float = 0.78) -> float:
    if x <= zero_at:
        return 0.0
    if x >= full_from:
        return 1.0
    return (x - zero_at) / (full_from - zero_at)


def memberships(x: float) -> dict[str, float]:
    """Low/medium/high membership degrees on normalized [0, 1] inputs."""
    x = max(0.0, min(1.0, float(x)))
    return {
        "low": shoulder_low(x),
        "medium": triangle(x, 0.18, 0.50, 0.82),
        "high": shoulder_high(x),
    }


# Explicit rule base: (intensity label, building-threat label, spread-potential label, output urgency).
# '*' means the input is not restrictive for that rule. Output is a Sugeno singleton in [0, 1].
_RULES = [
    ("high", "high", "*", 0.99),
    ("*", "high", "high", 0.98),
    ("high", "*", "high", 0.94),
    ("medium", "high", "*", 0.86),
    ("*", "medium", "high", 0.80),
    ("medium", "*", "high", 0.76),
    ("high", "medium", "*", 0.80),
    ("*", "high", "medium", 0.82),
    ("medium", "medium", "medium", 0.56),
    ("low", "high", "*", 0.70),
    ("*", "medium", "medium", 0.50),
    ("low", "low", "low", 0.10),
    ("*", "low", "low", 0.20),
    ("low", "medium", "*", 0.40),
]


def fuzzy_urgency(intensity: float, building_threat: float, spread_potential: float) -> float:
    """Return risk urgency using min rule firing and weighted singleton defuzzification."""
    vals = [max(0.0, min(1.0, float(v))) for v in (intensity, building_threat, spread_potential)]
    mus = [memberships(v) for v in vals]
    num = den = 0.0
    for i_label, b_label, s_label, out in _RULES:
        selected = []
        for label, degree in zip((i_label, b_label, s_label), mus):
            selected.append(1.0 if label == "*" else degree[label])
        firing = min(selected)
        num += firing * out
        den += firing
    # Smooth fallback for uncovered rule combinations, weighted lightly so explicit rules dominate.
    fallback = 0.36 * vals[0] + 0.39 * vals[1] + 0.25 * vals[2]
    return max(0.0, min(1.0, num / den if den > 1e-9 else fallback))


def fuzzy_rule_explanation(intensity: float, building_threat: float, spread_potential: float) -> str:
    """Human-readable labels for the dashboard/viva."""
    def label(v):
        m = memberships(v)
        return max(m, key=m.get)
    i, b, s = label(intensity), label(building_threat), label(spread_potential)
    if b == "high" and (i == "high" or s == "high"):
        return "Protect nearby buildings first"
    if s == "high" and i in ("medium", "high"):
        return "Stop a fast-growing fire front"
    if i == "high":
        return "Suppress intense burning cells"
    if b == "medium" and s == "high":
        return "Limit spread toward populated areas"
    if i == "low" and b == "low" and s == "low":
        return "Low immediate priority"
    return "Balance fire intensity, spread and exposure"
