from __future__ import annotations
import time
import streamlit as st
import pandas as pd

from firehawk.scenarios import create_scenario, available_presets
from firehawk.simulation import compare_modes, hotspot_urgencies
from firehawk.visuals import render_map_svg, render_explanation_card, render_animated_mission_html
from firehawk.metrics import winner_summary

st.set_page_config(page_title="FireHawk | Wildfire Response Lab", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")

# ---------- UI theme ----------
st.markdown("""
<style>
:root { color-scheme: dark; }
.stApp { background: radial-gradient(ellipse at 9% 0%, #12263a 0%, #09111b 42%, #080e16 100%); color: #eaf2fb; }
[data-testid="stSidebar"] { background: #0c1723; border-right: 1px solid #21364b; }
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 1500px; }
.hero { border: 1px solid #28425a; background: linear-gradient(115deg, rgba(22,43,63,.98), rgba(12,24,37,.95)); padding: 22px 24px; border-radius: 18px; margin-bottom: 16px; box-shadow: 0 14px 36px rgba(0,0,0,.16); }
.hero-title { font-size: 30px; font-weight: 820; letter-spacing: -.8px; color: #f2f7fd; line-height: 1.1; }
.hero-sub { color: #9eb4c9; font-size: 13px; margin-top: 8px; }
.pill { display:inline-block; border:1px solid #31516d; color:#9edffd; padding:4px 8px; border-radius:999px; font-size:10px; font-weight:700; letter-spacing:.8px; text-transform:uppercase; margin-bottom:11px; }
.kpi { background: linear-gradient(155deg,#14283a,#0f1c29); border:1px solid #263f56; border-radius:14px; padding:14px 16px; min-height:112px; }
.kpi-label { font-size:11px; text-transform:uppercase; letter-spacing:.7px; color:#91a9bf; font-weight:700; }
.kpi-value { font-size:27px; font-weight:800; color:#f1f7fd; margin-top:6px; }
.kpi-note { font-size:11px; color:#9cb1c5; margin-top:4px; }
.section-title { font-size:18px; font-weight:800; color:#edf5fd; margin: 8px 0 4px 0; }
.section-help { color:#91a9bf; font-size:12px; margin-bottom:12px; }
.info-strip { border:1px solid #29445b; border-radius:10px; background:#0e1c2a; padding:10px 13px; color:#b7cadd; font-size:12px; }
.good { color:#9df2ba; font-weight:800; }
.bad { color:#ffbd99; font-weight:800; }
div[data-testid="stMetric"] { background:#122337; border:1px solid #294259; border-radius:12px; padding:12px; }
div[data-testid="stMetricLabel"] p { color:#a9bed2 !important; font-size:11px !important; }
div[data-testid="stMetricValue"] { color:#f0f7ff !important; }
.stButton>button[kind="primary"] { background:#57d6ff; color:#07121c; font-weight:800; border:0; border-radius:10px; }
.stButton>button { border-radius:10px; }
hr { border-color:#1d3347; }
[data-testid="stTabs"] button { font-weight:700; }
.caption { color:#94abc0; font-size:11px; }
</style>
""", unsafe_allow_html=True)


def kpi_html(label, value, note="", color="#eff7ff"):
    return f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value" style="color:{color}">{value}</div><div class="kpi-note">{note}</div></div>'


def pct_improvement(baseline, optimized):
    if baseline == 0:
        return None
    return (baseline - optimized) / abs(baseline) * 100.0


def safe_pct(value):
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def run_signature(preset, seed, drones, steps, manual, dryness, wind, wind_dir):
    return (preset, int(seed), int(drones), int(steps), bool(manual), round(float(dryness), 3), round(float(wind), 3), str(wind_dir))


# ---------- Sidebar scenario form ----------
profile_defaults = {
    "Calm & Clear": (0.34, 0.20, "E", 4),
    "Windy & Dry": (0.91, 0.90, "E", 2),
    "Near Buildings": (0.67, 0.48, "N", 4),
    "Resource Constrained": (0.79, 0.65, "W", 2),
    "Randomized Scenario": (0.73, 0.67, "E", 4),
}

with st.sidebar:
    st.markdown("<div class='pill'>SIMULATION CONTROL</div>", unsafe_allow_html=True)
    st.markdown("## Configure a fire scenario")
    st.caption("Both strategies receive the same terrain, fire start, weather and spread-noise field.")
    with st.form("scenario_form", border=True):
        preset = st.selectbox("Environment type", available_presets(), index=1,
                              help="Choose a repeatable environment or generate weather and ignition conditions from a seed.")
        seed = st.number_input("Scenario seed", min_value=1, max_value=999999, value=7, step=1,
                               help="The same seed reproduces the same randomized map and fire spread.")
        drone_count = st.slider("Firefighting drones", 1, 7, profile_defaults[preset][3])
        steps = st.slider("Simulation duration (ticks)", 30, 100, 65, step=5)
        st.markdown("**Advanced weather overrides**")
        manual_weather = st.checkbox("Manually override preset weather", value=False)
        dryness = st.slider("Fuel dryness", 0.10, 1.00, float(profile_defaults[preset][0]), 0.05)
        wind_speed = st.slider("Wind strength", 0.00, 1.00, float(profile_defaults[preset][1]), 0.05)
        wind_dir = st.selectbox("Wind direction", ["N", "E", "S", "W"], index=["N", "E", "S", "W"].index(profile_defaults[preset][2]))
        submitted = st.form_submit_button("▶ Run both strategies", type="primary", use_container_width=True)

# Create exactly the scenario requested by the current form values.
scenario = create_scenario(
    preset=preset, seed=int(seed), drone_count=int(drone_count), steps=int(steps),
    dryness_override=float(dryness) if manual_weather else None,
    wind_override=float(wind_speed) if manual_weather else None,
    wind_dir_override=wind_dir if manual_weather else None,
)
current_sig = run_signature(preset, seed, drone_count, steps, manual_weather, dryness if manual_weather else scenario.dryness, wind_speed if manual_weather else scenario.wind_speed, wind_dir if manual_weather else scenario.wind_dir)

if "comparison" not in st.session_state:
    # A known, high-signal reference scenario is run on first load so the demo is not an empty shell.
    default_scenario = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=65)
    with st.spinner("Preparing the reference wildfire scenario…"):
        st.session_state.comparison = compare_modes(default_scenario, keep_history=True)
        st.session_state.comparison_sig = run_signature("Windy & Dry", 7, 2, 65, False, default_scenario.dryness, default_scenario.wind_speed, default_scenario.wind_dir)
        st.session_state.last_runtime = 0.0
        st.session_state.run_count = 1

if submitted:
    started = time.perf_counter()
    with st.spinner("Running the same wildfire against nearest-hotspot and fuzzy + genetic strategies…"):
        st.session_state.comparison = compare_modes(scenario, keep_history=True)
        st.session_state.comparison_sig = current_sig
    st.session_state.last_runtime = time.perf_counter() - started
    st.session_state.run_count = st.session_state.get("run_count", 0) + 1
    st.session_state.pop("benchmark_rows", None)

comparison = st.session_state.comparison
run_scenario = comparison["scenario"]
baseline = comparison["baseline"]
optimized = comparison["optimized"]
bm = baseline["metrics"]
om = optimized["metrics"]
stale = st.session_state.get("comparison_sig") != current_sig

# ---------- Header ----------
st.markdown("""
<div class="hero">
  <div class="pill">SOFT COMPUTING · SDG 11 + SDG 13</div>
  <div class="hero-title">🔥 FireHawk <span style="color:#8edfff">Wildfire Response Lab</span></div>
  <div class="hero-sub">Watch a nearest-hotspot baseline compete against a fuzzy-risk + genetic-assignment controller in the exact same simulated environment.</div>
</div>
""", unsafe_allow_html=True)

if stale:
    st.warning("Your sidebar settings have changed, but the displayed run is still the previous result. Press **Run both strategies** to apply the current settings.")

st.caption(run_scenario.notes)

# Scenario context line
col_a, col_b, col_c, col_d = st.columns([1.3, 1, 1, 1])
with col_a:
    st.markdown(kpi_html("Environment", run_scenario.preset, f"Seed {run_scenario.seed}", "#91e2ff"), unsafe_allow_html=True)
with col_b:
    st.markdown(kpi_html("Wind / dryness", f"{run_scenario.wind_speed:.2f} / {run_scenario.dryness:.2f}", f"Wind toward {run_scenario.wind_dir}"), unsafe_allow_html=True)
with col_c:
    st.markdown(kpi_html("Fleet size", str(run_scenario.drone_count), f"{run_scenario.water_capacity:g} water units per drone"), unsafe_allow_html=True)
with col_d:
    status = "Contained" if om["contained_by_end"] else "Active at end"
    st.markdown(kpi_html("FireHawk status", status, f"{run_scenario.steps} ticks simulated", "#9df2ba" if om["contained_by_end"] else "#ffbd99"), unsafe_allow_html=True)

# ---------- Main tabs ----------
tab_live, tab_results, tab_explain, tab_guide = st.tabs(["🎮  Live Simulation", "📊  Compare Results", "🧠  Algorithm Details", "📘  Project Guide"])

with tab_live:
    st.markdown("<div class='section-title'>Watch the mission unfold, one simulated second at a time</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-help'>Press Start live mission. Drones visibly travel to their targets, active fire grows or is suppressed, and the metrics update at each tick. Both strategies start from the same generated forest and fire.</div>", unsafe_allow_html=True)
    import streamlit.components.v1 as components
    components.html(render_animated_mission_html(comparison), height=980, scrolling=False)
    st.markdown("#### What to try during your demo")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown(render_explanation_card("1 · Start the mission", "Press Start live mission. Use the speed selector to show movement slowly for explanation or speed up the simulation for a quick comparison.", "#72dcff"), unsafe_allow_html=True)
    with d2:
        st.markdown(render_explanation_card("2 · Change the conditions", "Choose Windy & Dry or Near Buildings in the sidebar, change the seed or drone count, then press Run both strategies to create a new paired mission.", "#ffbd70"), unsafe_allow_html=True)
    with d3:
        st.markdown(render_explanation_card("3 · Explain the difference", "The baseline chooses nearby fire. FireHawk scores urgency from fire intensity, building threat and spread potential, then the genetic algorithm coordinates assignments.", "#91efb0"), unsafe_allow_html=True)
    st.info("Playback runs in the browser using snapshots computed by the Python simulator. One tick is displayed as one simulated second at 1×; the simulation is an educational model, not a real wildfire forecast.")

with tab_results:
    st.markdown("<div class='section-title'>Did the optimized strategy do better?</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-help'>The scorecard separates primary outcomes from resource use. Lower burned area and building exposure are better; resource use is contextual rather than a win by itself.</div>", unsafe_allow_html=True)
    burned_imp = pct_improvement(bm["burned_area_cells"], om["burned_area_cells"])
    damage_imp = pct_improvement(bm["buildings_damaged"], om["buildings_damaged"])
    exp_imp = pct_improvement(bm["building_exposure_units"], om["building_exposure_units"])
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_html("Burned area change", safe_pct(burned_imp), "Lower is better", "#9df2ba" if burned_imp is not None and burned_imp > 0 else "#ffbd99"), unsafe_allow_html=True)
    c2.markdown(kpi_html("Damaged buildings", f"{bm['buildings_damaged']} → {om['buildings_damaged']}", f"Saved: {om['buildings_saved']} of {om['total_buildings']}", "#9df2ba" if om['buildings_damaged'] < bm['buildings_damaged'] else "#eaf2fb"), unsafe_allow_html=True)
    c3.markdown(kpi_html("Building exposure change", safe_pct(exp_imp), "Lower is better", "#9df2ba" if exp_imp is not None and exp_imp > 0 else "#ffbd99"), unsafe_allow_html=True)
    c4.markdown(kpi_html("Containment", f"{'Yes' if om['contained_by_end'] else 'Not yet'}", f"Baseline: {'Yes' if bm['contained_by_end'] else 'Not yet'}", "#9df2ba" if om['contained_by_end'] else "#ffbd99"), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(render_explanation_card("Result interpretation", winner_summary(bm, om), "#84e8a4" if (bm['burned_area_cells'] > om['burned_area_cells'] and bm['buildings_damaged'] >= om['buildings_damaged']) else "#ffbe72"), unsafe_allow_html=True)

    result_rows = [
        {"Metric": "Burned area (cells)", "Nearest baseline": bm["burned_area_cells"], "FireHawk fuzzy + GA": om["burned_area_cells"], "Preferred": "Lower"},
        {"Metric": "Buildings damaged", "Nearest baseline": bm["buildings_damaged"], "FireHawk fuzzy + GA": om["buildings_damaged"], "Preferred": "Lower"},
        {"Metric": "Building exposure (model units)", "Nearest baseline": bm["building_exposure_units"], "FireHawk fuzzy + GA": om["building_exposure_units"], "Preferred": "Lower"},
        {"Metric": "Peak active fire cells", "Nearest baseline": bm["peak_active_fire_cells"], "FireHawk fuzzy + GA": om["peak_active_fire_cells"], "Preferred": "Lower"},
        {"Metric": "Drone distance (grid cells)", "Nearest baseline": bm["drone_distance_cells"], "FireHawk fuzzy + GA": om["drone_distance_cells"], "Preferred": "Contextual"},
        {"Metric": "Water drops used", "Nearest baseline": bm["water_drops_used"], "FireHawk fuzzy + GA": om["water_drops_used"], "Preferred": "Contextual"},
        {"Metric": "Remaining battery (average %)", "Nearest baseline": bm["remaining_battery_pct"], "FireHawk fuzzy + GA": om["remaining_battery_pct"], "Preferred": "Higher"},
    ]
    st.dataframe(pd.DataFrame(result_rows), use_container_width=True, hide_index=True)

    # Time-series chart: data are actual simulation snapshots.
    history_rows = []
    for name, run in [("Nearest baseline", baseline), ("FireHawk fuzzy + GA", optimized)]:
        for snap in run["history"]:
            m = snap["metrics"]
            history_rows.append({"Tick": snap["step"], "Strategy": name, "Burned area (cells)": m["burned_area_cells"], "Active fire cells": m["active_fire_cells"], "Building exposure": m["building_exposure_units"]})
    hist_df = pd.DataFrame(history_rows)
    chart_choice = st.selectbox("Progress metric", ["Burned area (cells)", "Active fire cells", "Building exposure"], index=0)
    chart_df = hist_df.pivot(index="Tick", columns="Strategy", values=chart_choice)
    st.line_chart(chart_df, use_container_width=True, height=280)
    st.caption("The curves are generated from this run's snapshots, not hard-coded sample data.")

    st.markdown("#### Multi-seed robustness check")
    st.markdown("Run the same environment type across five different seeds. Each seed is still a paired test: both controllers see the identical generated map, weather, ignition and spread-noise field for that seed.")
    if st.button("Run 5-seed benchmark", key="benchmark_button", use_container_width=False, disabled=stale):
        sig = st.session_state.get("comparison_sig", ())
        manual_flag = bool(sig[4]) if len(sig) >= 8 else False
        fixed_dry = run_scenario.dryness if manual_flag else None
        fixed_wind = run_scenario.wind_speed if manual_flag else None
        fixed_dir = run_scenario.wind_dir if manual_flag else None
        bench_rows = []
        base_seed = int(run_scenario.seed)
        with st.spinner("Running ten paired simulations across five scenario seeds…"):
            for seed_i in [base_seed, base_seed + 1, base_seed + 2, base_seed + 3, base_seed + 4]:
                bench_scenario = create_scenario(
                    run_scenario.preset, seed=seed_i, drone_count=run_scenario.drone_count,
                    steps=run_scenario.steps, dryness_override=fixed_dry,
                    wind_override=fixed_wind, wind_dir_override=fixed_dir,
                )
                bench = compare_modes(bench_scenario, keep_history=False)
                b, o = bench["baseline"]["metrics"], bench["optimized"]["metrics"]
                def reduction(a, z):
                    return None if abs(float(a)) < 1e-9 else (float(a) - float(z)) / abs(float(a)) * 100.0
                bench_rows.append({
                    "Seed": seed_i,
                    "Burned cells · baseline": b["burned_area_cells"],
                    "Burned cells · FireHawk": o["burned_area_cells"],
                    "Burned area reduction %": None if reduction(b["burned_area_cells"], o["burned_area_cells"]) is None else round(reduction(b["burned_area_cells"], o["burned_area_cells"]), 2),
                    "Damaged buildings · baseline": b["buildings_damaged"],
                    "Damaged buildings · FireHawk": o["buildings_damaged"],
                    "Exposure · baseline": b["building_exposure_units"],
                    "Exposure · FireHawk": o["building_exposure_units"],
                    "FireHawk contained by end": o["contained_by_end"],
                    "Strict primary-metric win": (o["burned_area_cells"] <= b["burned_area_cells"] and o["buildings_damaged"] <= b["buildings_damaged"] and o["building_exposure_units"] <= b["building_exposure_units"] and (o["burned_area_cells"] < b["burned_area_cells"] or o["buildings_damaged"] < b["buildings_damaged"] or o["building_exposure_units"] < b["building_exposure_units"])),
                })
        st.session_state.benchmark_rows = bench_rows
    if st.session_state.get("benchmark_rows"):
        bdf = pd.DataFrame(st.session_state.benchmark_rows)
        strict_wins = int(bdf["Strict primary-metric win"].sum())
        avg_reduction = bdf["Burned area reduction %"].dropna().mean()
        z1, z2, z3 = st.columns(3)
        z1.metric("Paired seeds", len(bdf))
        z2.metric("Strict primary-metric wins", f"{strict_wins}/{len(bdf)}")
        z3.metric("Mean burned-area reduction", "—" if pd.isna(avg_reduction) else f"{avg_reduction:.1f}%")
        st.dataframe(bdf, use_container_width=True, hide_index=True)
        st.download_button("⬇ Download 5-seed benchmark CSV", bdf.to_csv(index=False).encode("utf-8"), file_name="firehawk_5_seed_benchmark.csv", mime="text/csv")
        st.caption("A strict win means FireHawk is no worse on burned area, damaged buildings, and building exposure, and is strictly better on at least one. This is intentionally harder than counting any single-metric improvement.")

    # Download exact run metrics and per-tick history.
    summary_csv = pd.DataFrame([
        {"Scenario": run_scenario.preset, "Seed": run_scenario.seed, "Algorithm": baseline["mode_label"], **bm},
        {"Scenario": run_scenario.preset, "Seed": run_scenario.seed, "Algorithm": optimized["mode_label"], **om},
    ]).to_csv(index=False).encode("utf-8")
    hist_csv = hist_df.to_csv(index=False).encode("utf-8")
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("⬇ Download comparison metrics CSV", summary_csv, file_name="firehawk_comparison_metrics.csv", mime="text/csv", use_container_width=True)
    with d2:
        st.download_button("⬇ Download time-series CSV", hist_csv, file_name="firehawk_timeline.csv", mime="text/csv", use_container_width=True)

with tab_explain:
    st.markdown("<div class='section-title'>Algorithm details</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-help'>FireHawk combines a transparent fuzzy risk score with a genetic algorithm that allocates drones to fire hotspots.</div>", unsafe_allow_html=True)
    expl1, expl2 = st.columns(2)
    with expl1:
        st.markdown(render_explanation_card("1 · Simple baseline", "For every dispatch cycle, an available drone selects the nearest active burning cell. The policy is easy to explain, but distance alone does not reflect whether a fire is moving toward buildings or across a fast-spreading front.", "#ffbf72"), unsafe_allow_html=True)
        st.markdown(render_explanation_card("2 · Fuzzy inference", "Three normalized inputs are evaluated: fire intensity, proximity to buildings, and spread potential. Each input has Low / Medium / High membership functions. A hand-written rule base fires with min-membership strength; weighted singleton defuzzification produces a risk urgency from 0 to 1.", "#9edfff"), unsafe_allow_html=True)
        st.markdown(render_explanation_card("3 · Genetic algorithm", "A chromosome encodes one hotspot choice per available drone. Fitness rewards high fuzzy urgency and distinct hotspot coverage, while penalizing travel distance, unsafe battery range, and multiple drones chasing the same small patch. The custom GA uses tournament selection, uniform crossover, mutation, and elitism.", "#a4f2bb"), unsafe_allow_html=True)
    with expl2:
        st.markdown("#### Example fuzzy rules")
        st.markdown("- IF building threat is **high** AND intensity is **high**, THEN urgency is **very high**.\n- IF building threat is **high** AND spread potential is **high**, THEN urgency is **very high**.\n- IF intensity and spread potential are **high**, THEN urgency is **high**.\n- IF intensity, threat, and spread are **low**, THEN urgency is **low**.")
        st.markdown("#### Why use both methods?")
        st.markdown("Fuzzy logic converts uncertain environmental signals into an interpretable urgency score. The genetic algorithm searches combinations of drone assignments instead of choosing each target independently. The baseline and hybrid controller are evaluated under the same starting map and pre-generated spread-noise field.")
        st.markdown("#### What is modeled?")
        st.markdown("- Grid-based forest / scrub fuel, roads and firebreaks, ponds, and non-burning building cells.\n- Wind and dryness change the probability of spread.\n- Drones move, drop water on nearby burning cells, consume water and battery, and return to a base for refilling.\n- Building heat accumulation, burned area, active fire, exposure, movement, and resource use are recorded each tick.")
        st.warning("This is a teaching simulator, not a real wildfire prediction or drone dispatch system. Results depend on simplified grid assumptions and are not suitable for operational emergency decisions.")
    st.markdown("#### SDG relevance")
    sdg1, sdg2 = st.columns(2)
    with sdg1:
        st.markdown(render_explanation_card("SDG 11 · Sustainable Cities and Communities", "The project explores reducing exposure to wildfire hazards for built areas and supporting community resilience through emergency-response planning.", "#f59e0b"), unsafe_allow_html=True)
    with sdg2:
        st.markdown(render_explanation_card("SDG 13 · Climate Action", "The simulator provides a testbed for exploring preparedness under dry and windy conditions. It does not estimate climate causation or real-world emissions.", "#79c84a"), unsafe_allow_html=True)
    st.markdown("#### Experimental fairness checklist")
    st.markdown("- Same terrain, building coordinates, launch base, initial ignition cells, weather, and random spread field for both runs.\n- Same drone count, water capacity, battery model, speed, and suppressant rules.\n- Only dispatch logic differs: nearest-hotspot versus fuzzy-risk + GA assignment.\n- All measured outcomes are shown, including scenarios where FireHawk does not improve every metric.")


with tab_guide:
    st.markdown("<div class='section-title'>FireHawk · Complete project guide</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-help'>Use this page to understand the problem, explain the algorithms in a viva, and interpret the live comparison without needing to read the source code first.</div>", unsafe_allow_html=True)

    st.markdown("### 1. What problem are we solving?")
    st.markdown("A wildfire can spread while response resources are limited. A simple dispatcher may send each drone to the closest burning cell, but distance alone does not tell us whether a hotspot threatens buildings or is likely to spread quickly. FireHawk is a small simulation that investigates whether risk-aware, coordinated assignments can improve outcomes compared with that nearest-hotspot baseline.")
    st.markdown("### 2. The two modes")
    a, b = st.columns(2)
    with a:
        st.markdown(render_explanation_card("Mode A · Nearest-hotspot baseline", "At each dispatch, every available drone targets a nearby active fire. The strategy is fast and easy to understand, but it does not explicitly prioritize building threat and predicted spread potential.", "#ffbd70"), unsafe_allow_html=True)
    with b:
        st.markdown(render_explanation_card("Mode B · FireHawk hybrid", "First, fuzzy logic estimates each active hotspot's urgency. Then the genetic algorithm searches for a coordinated set of drone targets, considering urgency, travel distance, remaining battery, and redundant coverage.", "#91efb0"), unsafe_allow_html=True)

    st.markdown("### 3. What happens during one simulated second?")
    st.markdown("""1. **Fire spreads:** wind direction, wind strength, fuel dryness, fuel type, and seeded random values determine whether neighboring fuel cells ignite.
2. **Risk is evaluated:** active cells receive a fuzzy urgency score using burning intensity, proximity to buildings, and spread potential.
3. **Drones are assigned:** the baseline picks nearby fires; FireHawk uses its GA at dispatch cycles to pick targets.
4. **Drones move:** each drone moves toward its target or returns to the base when its battery or water reserve is low.
5. **Suppression occurs:** a drone close enough to a hotspot drops water; cell intensity can fall and a fire cell may be extinguished.
6. **Metrics update:** burned cells, active fire, building damage/exposure, resource use, and drone position are saved into the next frame.""")
    st.caption("The animation precomputes both policies and then replays their saved states. At 1×, it presents one model tick per second and interpolates drone positions between snapshots; the model's fire/weather rules remain a simplified educational approximation.")

    st.markdown("### 4. How fuzzy logic works")
    st.markdown("Fuzzy logic turns measurements into overlapping linguistic categories instead of forcing every value into a hard low/high threshold.")
    st.dataframe(pd.DataFrame([
        {"Input": "Fire intensity", "Question answered": "How strongly is this cell burning?", "Fuzzy labels": "Low / Medium / High"},
        {"Input": "Building threat", "Question answered": "How close is the hotspot to buildings?", "Fuzzy labels": "Low / Medium / High"},
        {"Input": "Spread potential", "Question answered": "How much flammable fuel is nearby under the current wind/dryness?", "Fuzzy labels": "Low / Medium / High"},
    ]), use_container_width=True, hide_index=True)
    st.markdown("Examples of rules: **IF building threat is high AND intensity is high, THEN urgency is very high.** **IF intensity, building threat, and spread potential are low, THEN urgency is low.** Rule firing strengths are combined with a hand-written weighted-singleton defuzzification step, producing an urgency score from 0 to 1.")

    st.markdown("### 5. How the genetic algorithm works")
    st.markdown("Each candidate chromosome contains one target-hotspot choice for each available drone. The algorithm repeatedly evaluates candidates, keeps strong ones, selects parents using tournament selection, combines assignment genes through uniform crossover, mutates some targets, and retains the best candidates through elitism. After several generations, it returns the highest-scoring assignment it found.")
    st.markdown("The fitness rewards high-urgency hotspots and useful coverage. It penalizes excessive travel, assignments that do not leave enough battery to return, and multiple drones clustering on the same small patch. This is a heuristic assignment optimizer, not a proof of globally optimal firefighting.")
    st.markdown("**Simplified fitness structure** (larger is better):")
    st.code("F = Σ_d (128·R_d − 1.15·D_d − 0.18·H_d + K_d − P_d) + 12·U − 20·Q₀ − 5·Q₂", language="text")
    st.markdown("`R_d` is fuzzy urgency, `D_d` is distance to the target, `H_d` estimates the target-to-base return distance, `K_d` rewards keeping a valid existing assignment, and `P_d` penalizes an unsafe battery margin. `U` counts distinct targets, `Q₀` counts duplicate-target pairs, and `Q₂` penalizes pairs assigned very close together. These are tunable heuristic weights, not physical units.")

    st.markdown("### 6. How do we compare the methods fairly?")
    st.markdown("Both modes receive the **same terrain, buildings, initial ignition points, weather, drone count, resource limits, simulation duration, and pre-generated spread-noise field** for a given seed. Only the dispatch assignment logic changes. Use the Compare Results page to view outcome metrics and progress curves, and run the five-seed benchmark to see whether results generalize beyond one lucky map.")
    st.dataframe(pd.DataFrame([
        {"Metric": "Burned area", "Meaning": "Number of forest/scrub cells that caught fire during the mission", "Preferred direction": "Lower"},
        {"Metric": "Buildings damaged", "Meaning": "Buildings whose modelled accumulated heat crosses the damage threshold", "Preferred direction": "Lower"},
        {"Metric": "Building exposure", "Meaning": "Cumulative model units of fire intensity next to buildings over time", "Preferred direction": "Lower"},
        {"Metric": "Active fire cells", "Meaning": "How many cells are still burning at the shown moment", "Preferred direction": "Lower"},
        {"Metric": "Drone distance / water use", "Meaning": "Resources spent by the fleet", "Preferred direction": "Interpret with outcomes"},
    ]), use_container_width=True, hide_index=True)
    st.warning("Do not claim FireHawk always wins. The genetic algorithm optimizes an urgency/distance proxy; a different random map or dispatch sequence can change the result. State the measured outcome and acknowledge trade-offs.")

    st.markdown("### 7. SDG connection")
    sdg1, sdg2 = st.columns(2)
    with sdg1:
        st.markdown(render_explanation_card("SDG 11 · Sustainable Cities and Communities", "Primary connection: explore emergency response approaches that may reduce wildfire exposure around built areas and help communities become more resilient.", "#f59e0b"), unsafe_allow_html=True)
    with sdg2:
        st.markdown(render_explanation_card("SDG 13 · Climate Action", "Secondary connection: test response strategies under dry and windy hazard conditions. The project does not model climate causation or predict real-world wildfire behaviour.", "#79c84a"), unsafe_allow_html=True)
    st.markdown("### 8. What is implemented manually?")
    st.markdown("""- Membership functions and Low/Medium/High fuzzy degrees.
- Fuzzy rule evaluation and weighted-singleton defuzzification.
- Genetic-algorithm chromosome representation, fitness evaluation, tournament selection, crossover, mutation, and elitism.
- Fire spread, drone assignment, movement, suppression, battery/water constraints, metrics, and seeded paired experiments.
- Streamlit and pandas are used for the app interface and tabular presentation, not to supply the fuzzy or genetic algorithm.""")
    st.markdown("### 9. A 30-second viva explanation")
    st.code("FireHawk compares a nearest-hotspot drone dispatcher with a hybrid fuzzy-logic and genetic-algorithm controller. Fuzzy logic estimates how urgently each fire cell needs attention using intensity, building threat, and spread potential. A custom genetic algorithm then searches coordinated assignments for the drones while accounting for travel, battery return feasibility, and duplicate coverage. Both modes run on the same seeded map and fire-spread noise, and we compare burned area, building damage, exposure, containment, and resource use. The model is educational and not intended for real emergency decisions.", language="text")

st.markdown("---")
st.markdown("<div class='caption'>FireHawk AAT · Custom fuzzy and genetic algorithms · Deterministic seeded experiments · Simulation-only research prototype</div>", unsafe_allow_html=True)
