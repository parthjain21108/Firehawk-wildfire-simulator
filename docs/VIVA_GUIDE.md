# FireHawk viva guide

## 30-second explanation

“FireHawk simulates a wildfire and a small fleet of firefighting drones. The baseline sends each drone to the nearest active fire. Our method first uses fuzzy logic to estimate hotspot urgency based on fire intensity, distance to buildings, and spread potential. A custom genetic algorithm then assigns multiple drones to different hotspots while balancing urgency, travel distance, duplicate coverage, and battery return feasibility. We run both methods on the exact same seeded environment and compare burned area, building damage, and cumulative building exposure.”

## Why use fuzzy logic?

Wildfire priority is not a binary rule. A cell may be very intense, close to buildings, or likely to spread quickly. Membership functions allow inputs to partially belong to Low, Medium and High categories. The rule base converts these overlapping conditions into an interpretable normalized urgency score.

## Why use a genetic algorithm?

Selecting targets independently can cause redundant drone assignments. The joint assignment space grows as more drones and hotspots exist. A genetic algorithm searches combinations of target assignments using a fitness function, tournament selection, crossover, mutation and elitism.

## What is the baseline?

The nearest-hotspot baseline is a simple greedy dispatch heuristic. It is not intentionally broken: it uses the same drones, battery/water system and suppression model. Its weakness is that distance alone does not encode the relative threat to buildings or likely spread.

## What makes the experiment fair?

Both methods receive the same generated map, initial ignition, weather, number of drones, resources, model and random spread-noise field. The route target selection logic is the intended independent variable.

## How do you interpret results?

Lower burned area, building damage and building exposure are preferred. Drone distance and water use are resource indicators, not stand-alone objectives. If an optimized run travels farther but reduces building exposure, that is a trade-off to explain. There is no guarantee that FireHawk beats the baseline in every scenario; use the multi-seed results to discuss robustness.

## SDG relevance

- **SDG 11 — Sustainable Cities and Communities (primary):** the simulation studies potential reduction of wildfire exposure around buildings.
- **SDG 13 — Climate Action (secondary):** dry and windy scenario types provide an educational setting to explore preparedness under hazardous environmental conditions.

Do not claim the simulator predicts real fires, estimates climate causation, or proves real-world avoided damage.

## Limitations to acknowledge

This is a deterministic-by-seed toy model with simplified spread, suppression, building exposure and drone behaviour. The GA optimizes a fuzzy urgency + distance proxy at periodic dispatch points; it does not solve a full stochastic optimal-control problem. The value of the AAT is the explicit soft-computing implementation, reproducible comparison, and clear evaluation—not operational realism.

## Explaining the live animation

“The app computes the baseline and FireHawk mission histories from the same initial conditions. The Live Simulation tab replays the saved states in sync. Between two saved states, the browser interpolates drone locations along the grid route. At the next simulated tick, the fire state and counters update to show ignitions, suppression, burned area and building damage. This makes the result observable step by step; the browser animation does not change the algorithm's decisions.”

## Showing the demo

1. Choose **Windy & Dry** and seed 7 with two drones, then select **Run both strategies** in the sidebar.
2. Open **Live Simulation** and click **Start live mission**. Keep playback at **Real time · 1 s/tick** for the explanation; use **Slow** if the evaluator wants to inspect a drone's movement.
3. Point out that the simple baseline dispatches based on distance, whereas FireHawk prioritizes urgency using intensity, building threat and spread potential, then the genetic algorithm coordinates targets.
4. Open **Compare Results** after the replay to read burned area, damaged buildings, exposure, containment and movement/resource trade-offs.
5. Open **Project Guide** for the end-to-end flow, algorithm operators, fair comparison conditions and SDG framing.

The map cell and one-second labels are illustrative. Do not present simulation timings as calibrated physical drone speeds or real wildfire predictions.
