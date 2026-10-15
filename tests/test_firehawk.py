import unittest

from firehawk.scenarios import create_scenario, random_scenario, FOREST, SCRUB
from firehawk.fuzzy import fuzzy_urgency, memberships, triangle
from firehawk.genetic import optimize_assignments
from firehawk.simulation import compare_modes, run_simulation, hotspot_urgencies
from firehawk.visuals import render_map_svg, render_animated_mission_html


class FuzzyTests(unittest.TestCase):
    def test_memberships_are_bounded(self):
        for x in [i / 100 for i in range(101)]:
            m = memberships(x)
            self.assertEqual(set(m), {"low", "medium", "high"})
            self.assertTrue(all(0 <= v <= 1 for v in m.values()))

    def test_triangle_peak(self):
        self.assertEqual(triangle(0.5, 0.0, 0.5, 1.0), 1.0)
        self.assertEqual(triangle(0.0, 0.0, 0.5, 1.0), 0.0)

    def test_high_risk_urgency_is_higher_than_low(self):
        urgent = fuzzy_urgency(0.92, 0.95, 0.92)
        low = fuzzy_urgency(0.15, 0.10, 0.10)
        self.assertGreater(urgent, low)
        self.assertTrue(0 <= urgent <= 1)
        self.assertTrue(0 <= low <= 1)


class ScenarioTests(unittest.TestCase):
    def test_same_seed_reproduces_map_and_fire(self):
        a = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=40)
        b = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=40)
        self.assertEqual(a.terrain, b.terrain)
        self.assertEqual(a.initial_fires, b.initial_fires)
        self.assertEqual((a.dryness, a.wind_speed, a.wind_dir), (b.dryness, b.wind_speed, b.wind_dir))

    def test_random_scenario_seed_changes_conditions(self):
        a = random_scenario(7)
        b = random_scenario(8)
        self.assertNotEqual((a.dryness, a.wind_speed, a.wind_dir, a.initial_fires),
                            (b.dryness, b.wind_speed, b.wind_dir, b.initial_fires))

    def test_environment_has_terrain_and_buildings(self):
        s = create_scenario("Near Buildings", seed=19)
        self.assertGreaterEqual(len(s.buildings), 5)
        self.assertGreaterEqual(len(s.initial_fires), 2)
        self.assertTrue(all(s.terrain[y][x] in (FOREST, SCRUB) for x, y in s.initial_fires))

    def test_bad_wind_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            create_scenario("Calm & Clear", wind_dir_override="SE")


class GeneticTests(unittest.TestCase):
    def test_assignment_is_valid_and_repeatable(self):
        opts = [(1, 1), (4, 2), (2, 6)]
        urgency = {opts[0]: 0.3, opts[1]: 0.9, opts[2]: 0.7}
        args = dict(options=opts, drone_positions=[(0, 0), (3, 5)], urgency=urgency,
                    battery=[100, 100], base=(0, 0), seed=77, population_size=10, generations=4)
        a = optimize_assignments(**args)
        b = optimize_assignments(**args)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 2)
        self.assertTrue(all(x in opts for x in a))


class SimulationTests(unittest.TestCase):
    def test_runs_have_history_for_every_tick(self):
        s = create_scenario("Calm & Clear", seed=42, drone_count=2, steps=30)
        run = run_simulation(s, "nearest", keep_history=True)
        self.assertEqual(len(run["history"]), s.steps + 1)
        self.assertEqual(run["history"][0]["step"], 0)
        self.assertEqual(run["history"][-1]["step"], s.steps)

    def test_resource_values_never_negative(self):
        s = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=45)
        result = run_simulation(s, "firehawk")
        for d in result["drones"]:
            self.assertGreaterEqual(d["water"], 0)
            self.assertGreaterEqual(d["battery"], 0)
            self.assertLessEqual(d["water"], d["water_capacity"])
            self.assertLessEqual(d["battery"], 100)

    def test_paired_comparison_starts_identically(self):
        s = create_scenario("Near Buildings", seed=19, drone_count=3, steps=35)
        c = compare_modes(s, keep_history=True)
        self.assertEqual(c["baseline"]["history"][0]["terrain"], c["optimized"]["history"][0]["terrain"])
        self.assertEqual(c["baseline"]["history"][0]["fire_status"], c["optimized"]["history"][0]["fire_status"])
        self.assertEqual(len(c["baseline"]["history"]), len(c["optimized"]["history"]))

    def test_reference_windy_dry_scenario_shows_concrete_gain(self):
        s = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=65)
        c = compare_modes(s, keep_history=False)
        b, o = c["baseline"]["metrics"], c["optimized"]["metrics"]
        self.assertLess(o["burned_area_cells"], b["burned_area_cells"])
        self.assertLess(o["buildings_damaged"], b["buildings_damaged"])
        self.assertLess(o["building_exposure_units"], b["building_exposure_units"])
        self.assertTrue(o["contained_by_end"])

    def test_no_negative_fire_metric_and_known_modes(self):
        s = create_scenario("Resource Constrained", seed=31, drone_count=2, steps=30)
        c = compare_modes(s, keep_history=False)
        self.assertEqual(c["baseline"]["mode"], "nearest")
        self.assertEqual(c["optimized"]["mode"], "firehawk")
        for k in ["burned_area_cells", "active_fire_cells", "buildings_damaged", "building_exposure_units"]:
            self.assertGreaterEqual(c["baseline"]["metrics"][k], 0)
            self.assertGreaterEqual(c["optimized"]["metrics"][k], 0)

    def test_hotspot_urgency_only_for_burning_cells(self):
        s = create_scenario("Windy & Dry", seed=7, drone_count=2, steps=30)
        r = run_simulation(s, "firehawk")
        snap = r["history"][12]
        hot, urg = hotspot_urgencies(s, snap["terrain"], snap["fire_status"], snap["intensity"])
        self.assertEqual(set(hot), set(urg))
        self.assertTrue(all(0 <= v <= 1 for v in urg.values()))

    def test_svg_includes_title_and_timestep(self):
        s = create_scenario("Calm & Clear", seed=42, drone_count=2, steps=30)
        r = run_simulation(s, "nearest")
        svg = render_map_svg(r["history"][0], s, "TEST MAP")
        self.assertIn("TEST MAP", svg)
        self.assertIn("T+0", svg)
        self.assertIn("<svg", svg)


class AnimationViewerTests(unittest.TestCase):
    def test_animated_viewer_contains_controls_and_both_policies(self):
        scenario = create_scenario("Calm & Clear", seed=19, drone_count=2, steps=25)
        comparison = compare_modes(scenario, keep_history=True)
        html = render_animated_mission_html(comparison)
        self.assertIn("Start live mission", html)
        self.assertIn("Nearest-hotspot baseline", html)
        self.assertIn("Fuzzy + GA", html)
        self.assertIn("id=\"timeline\"", html)
        self.assertIn("requestAnimationFrame", html)
        self.assertNotIn("__DATA__", html)
        self.assertIn('"steps":25', html)


if __name__ == "__main__":
    unittest.main()
