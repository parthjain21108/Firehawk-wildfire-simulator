# FireHawk project specification

## 1. Precise problem statement

Develop a grid-based, simulation-only decision support prototype that dispatches a finite fleet of firefighting drones to suppress a wildfire spreading across forest and scrub cells. Drones have finite water and battery. Non-burning building cells are placed in exposed parts of the map. Wind and dryness change the spread probability. The project compares a nearest-active-hotspot baseline against a fuzzy-urgency plus genetic-assignment policy under identical initial conditions.

The aim is to reduce burned area, building damage and cumulative building exposure while tracking movement and resource use. The project is not a real wildfire prediction or operational command system.

## 2. Scenario and state representation

- Default map: 24 × 16 cells.
- Simulation: 65 discrete ticks by default.
- Terrain: forest, scrub, firebreak/road, building, water/pond, drone base.
- Fire status per cell: no fire, burning, or burned/extinguished.
- Fire state includes normalized intensity and age.
- Drones maintain grid position, selected hotspot, water, battery, and operational state (idle, enroute, suppressing, returning, recharging).
- Same seeded terrain, building coordinates, initial ignition, wind/dryness and pre-generated spread-noise values are reused in both policy runs.

## 3. Simplified fire spread equation

For a target cell, an adjacent burning source has ignition probability

\[
 p_{i\to j,t}=\operatorname{clip}\left((0.15+0.34D)F_j I_{i,t}W_{i\to j},0,0.82\right),
\]

where `D` is normalized fuel dryness, `F_j` is the target-cell fuel factor (forest higher than scrub), `I` is source intensity, and `W` is a directional wind multiplier. Independent adjacent-source attempts combine as

\[
P_{j,t}=1-\prod_{i\in N(j),\;i\;burning}(1-p_{i\to j,t}).
\]

One deterministic random number per grid cell and timestep decides ignition. The random field is fixed by scenario seed, keeping paired controller comparisons reproducible. A drone's drop reduces intensity in the target cell and its immediate four-neighbour suppression area.

These equations are intentionally simplified educational approximations; they are not calibrated wildfire science.

## 4. Fuzzy urgency engine

Three normalized inputs are calculated for every active burning cell:

1. **Intensity**: current normalized fire intensity.
2. **Building threat**: a decreasing function of Manhattan distance to the nearest building.
3. **Spread potential**: weighted combination of dryness, wind strength and the number of adjacent unburned fuel cells.

Each input has Low, Medium and High membership functions. The hand-written rule base includes statements such as:

- IF building threat is High AND intensity is High, THEN urgency is Very High.
- IF building threat is High AND spread potential is High, THEN urgency is Very High.
- IF intensity is High AND spread potential is High, THEN urgency is High.
- IF intensity, building threat and spread potential are Low, THEN urgency is Low.

Each rule uses minimum membership degree as its firing strength. Weighted singleton output aggregation returns a crisp urgency in [0, 1]. See `firehawk/fuzzy.py` for exact membership breakpoints and rules.

## 5. Genetic assignment

A chromosome contains one hotspot-candidate index for each available drone. The candidate pool is bounded to the highest-urgency active hotspots, making search light enough to run at multiple dispatch points.

For a candidate chromosome, the implemented fitness is a sum of per-drone utility terms plus fleet-assignment terms:

```text
F = sum_d(128*R_d - 1.15*D_d - 0.18*H_d + K_d - P_d)
    + 12*U - 20*Q0 - 5*Q2
```

Here `R_d` is fuzzy urgency of drone d's target, `D_d` is its Manhattan distance to target, `H_d` is target-to-base return distance, `K_d` is the continuity reward (+18 for retaining an active target, −4 for switching), `P_d` penalizes targets beyond the model's battery safety margin, `U` is the number of distinct assigned hotspots, `Q0` counts duplicate target pairs, and `Q2` counts pairs assigned within Manhattan distance two. The constants are tunable fitness weights, not physical units.

The manually implemented genetic operators are:

- seeded-greedy plus random population initialization;
- tournament selection of up to 3 candidates;
- uniform crossover with probability 0.85;
- per-gene mutation with probability 0.18;
- two-member elitism;
- 16 individuals and 6 generations per dispatch, with deterministic per-dispatch seeds.

The GA is a short-horizon assignment heuristic, not a proof of globally optimal firefighting. Fuzzy risk is the proxy that links environmental conditions to genetic fitness; simulation outcome metrics evaluate the resulting policy independently.

## 6. Policies and fair comparison

**Nearest-hotspot baseline:** assigns each available drone to a nearest burning cell, avoiding duplicate targets where possible. Resource-return and suppression dynamics are the same as the hybrid method.

**FireHawk:** uses the fuzzy urgency and custom GA to select a joint set of hotspot targets.

Both methods use the same scenario object and the same pre-generated ignition noise field, drone count, water capacity, battery model, speed, map and time horizon. Only dispatch logic differs.

## 7. Metrics

- Burned area: number of fuel cells ignited during the run.
- Buildings damaged: count where accumulated adjacent-fire heat exceeds the simulator threshold.
- Building exposure: sum of intensity in cells adjacent to each building across time (model units).
- Peak active fire cells.
- Drone distance in grid-cell movements.
- Water drops used, remaining water/battery, first suppression tick, containment tick, and whether active fire remains at the end.

Primary outcomes are shown separately. No single composite metric hides trade-offs.

## 8. Initial reference scenario

The default demonstration uses `Windy & Dry`, seed `7`, two drones, and 65 ticks. It is chosen to make risk-based dispatch effects visible while remaining reproducible. Metrics are generated by the current source and saved under `results/`. They are simulation-specific; do not generalize the one reference result to real fires. Use multi-seed benchmark runs to evaluate robustness.

## 9. Limitations

- Grid-based spread and fuel structure are simplified.
- Buildings are exposed to adjacent cells; the model does not simulate structural fire physics.
- Drones have simplified movement and suppression footprints.
- The GA optimizes an urgency/distance proxy, not full future stochastic trajectories.
- The model does not account for real flight regulations, smoke, terrain elevation, payload physics, communications, or fire-service doctrine.
- A strategy can perform worse in some seeds; the dashboard keeps those results visible.


## 10. Animated mission player and project guide

The Live Simulation page replays both precomputed policy histories in synchronized side-by-side maps. The browser animates drone markers along the cell-by-cell path between successive saved states. At each simulated tick, fire status/intensity, mission metrics, and per-drone status/resource readouts advance. The player provides Play/Pause, step backward/forward, Reset, a timeline scrubber, and playback speeds (including 1×, displayed as one simulated second per saved model tick).

This is a visualization of simulator-computed outcomes, not a second independent simulation implemented in JavaScript. Both policy histories are computed in Python with the same scenario and noise field before replay begins. A cell is a model/grid unit rather than a calibrated physical distance; the one-second label is for presentation and is not a claim about real drone speed or wildfire timing.

The dashboard has four pages/tabs: Live Simulation, Compare Results, Algorithm Details, and Project Guide. The Project Guide explains the problem, per-tick simulation sequence, fuzzy inputs/rules, genetic operators and fitness, metrics, fairness checks, SDG relevance, limits, and a short viva explanation.
