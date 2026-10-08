"""Sprint 01 — building engine objects from specs: same results as the kami 0.1 API (AC01-1, AC01-2)."""
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from kami.behavior import BehaviorSuite, ModelRegistry
from kami.behavior.models import AlwaysAccept, HazardScaler, LogitBooking, LogitBookingParams
from kami.cli import main
from kami.config import (BehaviorSpec, FleetComposition, FleetSpec, PolicyGroupMember, PolicyGroupSpec, PolicySpec,
                         Ref, RunSpec, SpecError, VehicleTypeSpec, build_behavior, build_policy, build_run,
                         build_scenario, load_run_spec, run_spec)
from kami.core.engine import SimConfig, Simulation
from kami.policy import POLICIES, Baseline, Composite, HeatmapReposition, PoolAfterWait, SurgePricing
from kami.scenario import PRESETS
from tests.helpers import BUILDER, assert_metrics_equal, small_run_spec

ROOT = Path(__file__).resolve().parents[1]


def api_run(preset, policy, args=None, seed=1, behavior=None):
    """The kami 0.1 Python code equivalent to ``small_run_spec``."""
    sc = BUILDER.preset(preset, seed=seed, demand_per_hour=120, n_drivers=40,
                        t_end=PRESETS[preset]["t_start"] + 3600)
    return Simulation(sc, POLICIES[policy](**(args or {})), behavior or BehaviorSuite()).run()


class TestSameAsPythonApi(unittest.TestCase):
    def test_spec_equals_python_api(self):
        args = {"wait_threshold": 120, "surcharge": 0, "include_matched": True}
        a = api_run("accident", "pool_after_wait", args, seed=3)
        b = run_spec(small_run_spec("accident", "pool_after_wait", args, seed=3))
        assert_metrics_equal(self, a.metrics(), b.metrics())
        self.assertEqual(a.events_processed, b.events_processed)
        self.assertEqual(a.log.rows, b.log.rows)

    def test_all_presets_and_policies(self):
        """AC01-2: every preset × every policy, through JSON, gives the 0.1 metrics."""
        for preset in PRESETS:
            for policy in POLICIES:
                with self.subTest(preset=preset, policy=policy):
                    doc = json.loads(small_run_spec(preset, policy).to_json())
                    b = run_spec(RunSpec.from_dict(doc))
                    a = api_run(preset, policy)
                    assert_metrics_equal(self, a.metrics(), b.metrics())
                    self.assertEqual(a.events_processed, b.events_processed)

    def test_cli_spec_equals_cli_flags(self):
        """AC01-1 through the CLI: ``kami spec`` + ``run --spec`` == ``run`` with the 0.1 flags."""
        flags = ["--preset", "rain", "--seed", "2", "--policy", "surge", "--arg", "every=60", "--demand", "100",
                 "--drivers", "50", "--grid-km", "5"]
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["run", *flags, "--out", f"{d}/old"]), 0)
                self.assertEqual(main(["spec", *flags, "--out", f"{d}/run.json"]), 0)
                self.assertEqual(main(["run", "--spec", f"{d}/run.json", "--out", f"{d}/new"]), 0)
            old = json.loads(Path(f"{d}/old/metrics.json").read_text())
            new = json.loads(Path(f"{d}/new/metrics.json").read_text())
            assert_metrics_equal(self, old, new)
            self.assertTrue(Path(f"{d}/new/timeseries.json").exists())
            self.assertTrue(Path(f"{d}/new/run_spec.resolved.json").exists())

    def test_example_spec_for_every_preset(self):
        presets = {load_run_spec(f).scenario.source.preset for f in (ROOT / "examples" / "specs").glob("*.json")}
        self.assertTrue(set(PRESETS) <= presets)

    def test_employed_drivers_and_crn_seed(self):
        spec = small_run_spec("weekday_am_peak", "baseline", employed_drivers=True)
        self.assertIsInstance(build_run(spec).behavior.driver_accept, AlwaysAccept)
        a = api_run("weekday_am_peak", "baseline", behavior=BehaviorSuite.employed_drivers())
        assert_metrics_equal(self, a.metrics(), run_spec(spec).metrics())
        spec.crn_seed = 99
        sc = BUILDER.preset("weekday_am_peak", seed=1, demand_per_hour=120, n_drivers=40, t_end=8 * 3600)
        c = Simulation(sc, Baseline(), BehaviorSuite.employed_drivers(), crn_seed=99).run()
        assert_metrics_equal(self, c.metrics(), run_spec(spec).metrics())

    def test_run_seed_overrides_scenario_seed(self):
        spec = small_run_spec(seed=1)
        spec.seed = 5
        self.assertEqual(build_run(spec).scenario.seed, 5)
        assert_metrics_equal(self, api_run("weekday_am_peak", "baseline", seed=5).metrics(), run_spec(spec).metrics())


class TestFleets(unittest.TestCase):
    def test_single_fleet_single_type_is_identical(self):
        spec = small_run_spec()
        spec.vehicle_types = [VehicleTypeSpec("car4", "car", 4)]
        spec.fleets = [FleetSpec("all", [FleetComposition("car4", 40)])]
        spec.scenario.n_drivers = 1   # ignored: fleets decide the number of vehicles
        sim = run_spec(spec)
        assert_metrics_equal(self, api_run("weekday_am_peak", "baseline").metrics(), sim.metrics())
        self.assertTrue(all(d.attrs["fleet_id"] == "all" for d in sim.scenario.drivers))

    def test_fleet_assignment_rule(self):
        spec = small_run_spec()
        spec.vehicle_types = [VehicleTypeSpec("car4", "car", 4), VehicleTypeSpec("bike", "bike", 1)]
        spec.fleets = [FleetSpec("a", [FleetComposition("car4", 30)]), FleetSpec("b", [FleetComposition("bike", 20)])]
        sc = build_run(spec).scenario
        self.assertEqual(len(sc.drivers), 50)
        self.assertEqual(sum(d.attrs["fleet_id"] == "a" for d in sc.drivers), 30)
        self.assertEqual([d.capacity for d in sc.drivers if d.attrs["vehicle_type"] == "bike"], [1] * 20)
        # D6: drivers keep the random draws of an unfleeted scenario of the same size
        plain = small_run_spec(drivers=50)
        base = build_scenario(plain.scenario)
        self.assertEqual([(d.loc, d.shift_start, d.shift_end) for d in base.drivers],
                         [(d.loc, d.shift_start, d.shift_end) for d in sc.drivers])

    def test_supply_multiplier_still_applies(self):
        spec = small_run_spec("undersupply")
        spec.vehicle_types = [VehicleTypeSpec("car4")]
        spec.fleets = [FleetSpec("a", [FleetComposition("car4", 50)])]
        sc = build_run(spec).scenario
        self.assertEqual(len(sc.drivers), 30)                                  # 50 × 0.6
        self.assertEqual({d.attrs["fleet_id"] for d in sc.drivers}, {"a"})


class TestPolicyGroup(unittest.TestCase):
    def test_composition_rules(self):
        self.assertIsInstance(build_policy(PolicyGroupSpec()), Baseline)
        p = build_policy(PolicyGroupSpec(members=[PolicyGroupMember(PolicySpec("surge", {"every": 30}))]))
        self.assertIsInstance(p, SurgePricing)
        self.assertEqual(p.tick_intervals, {"PRICE_UPDATE": 30})
        g = PolicyGroupSpec(members=[PolicyGroupMember(PolicySpec("surge")),
                                     PolicyGroupMember(PolicySpec("pool_after_wait"), enabled=False),
                                     PolicyGroupMember(PolicySpec("heatmap_reposition"), {"max_moves": 3})])
        c = build_policy(g)
        self.assertIsInstance(c, Composite)
        self.assertEqual([type(x) for x in c.policies], [SurgePricing, HeatmapReposition])
        self.assertEqual(c.policies[1].max_moves, 3)

    def test_matching_params(self):
        p = build_policy(PolicyGroupSpec(members=[PolicyGroupMember(PolicySpec(
            "pool_after_wait", {"matching": {"max_pickup_eta": 300, "solver": "greedy"}, "batch_window": 20}))]))
        self.assertIsInstance(p, PoolAfterWait)
        self.assertEqual((p.matching.max_pickup_eta, p.matching.solver, p.batch_window), (300, "greedy", 20))

    def test_composite_equals_python_api(self):
        spec = small_run_spec()
        spec.policy_group = PolicyGroupSpec("g", [PolicyGroupMember(PolicySpec("surge", {"every": 60})),
                                                  PolicyGroupMember(PolicySpec("heatmap_reposition"))])
        sc = BUILDER.preset("weekday_am_peak", seed=1, demand_per_hour=120, n_drivers=40, t_end=8 * 3600)
        a = Simulation(sc, Composite(SurgePricing(every=60), HeatmapReposition())).run()
        assert_metrics_equal(self, a.metrics(), run_spec(spec).metrics())

    def test_unresolved_reference_refused(self):
        spec = small_run_spec()
        spec.policy_group = PolicyGroupSpec(members=[PolicyGroupMember(Ref("stored"))])
        with self.assertRaises(SpecError):
            build_run(spec)


class TestBehaviorAndConfig(unittest.TestCase):
    def test_models_and_registry(self):
        with tempfile.TemporaryDirectory() as d:
            ModelRegistry(d).save("booking", LogitBooking(LogitBookingParams(asc=1.0)), "v1")
            suite = build_behavior(BehaviorSpec.from_dict({
                "registry": d, "models": {"cancel_wait": {"class": "HazardScaler",
                                                          "params": {"inner": {"class": "WeibullCancel"},
                                                                     "factor": 1.5}}}}))
            self.assertEqual(suite.booking.params.asc, 1.0)
            self.assertIsInstance(suite.cancel_wait, HazardScaler)
            self.assertEqual(suite.cancel_wait.factor, 1.5)
            spec = small_run_spec(registry=d)
            reg_suite = ModelRegistry(d).suite({"booking": "latest"})
            assert_metrics_equal(self, api_run("weekday_am_peak", "baseline", behavior=reg_suite).metrics(),
                                 run_spec(spec).metrics())

    def test_sim_config(self):
        spec = small_run_spec()
        spec = RunSpec.from_dict(dict(spec.to_dict(), sim_config={"batch_window": 20, "fare": {"base": 10000}}))
        cfg = build_run(spec).config
        self.assertEqual((cfg.batch_window, cfg.fare.base, cfg.fare.per_km), (20, 10000, SimConfig().fare.per_km))
        self.assertEqual(cfg.timeseries_interval_s, 300)
        spec = RunSpec.from_dict(dict(spec.to_dict(), sim_config={"timeseries_interval_s": None}))
        self.assertIsNone(build_run(spec).config.timeseries_interval_s)

    def test_synthetic_source(self):
        doc = {"name": "syn", "network": {"kind": "grid", "width_m": 5000, "height_m": 5000},
               "source": {"kind": "synthetic", "t_start": 25200, "t_end": 28800, "demand_per_hour": 100,
                          "weather": [[25200, "rain"]], "incidents": [{"t_offset": 600, "duration": 900}]},
               "n_drivers": 30, "seed": 4}
        sc = build_scenario(RunSpec.from_dict({"scenario": doc}).scenario)
        ref = BUILDER.synthetic(name="syn", seed=4, t_start=25200, t_end=28800, demand_per_hour=100, n_drivers=30,
                                weather=[(25200, "rain")], incidents=[{"t_offset": 600, "duration": 900}])
        self.assertEqual([(r.t, r.origin, r.dest) for r in sc.requests], [(r.t, r.origin, r.dest) for r in ref.requests])
        self.assertEqual(sc.weather, ref.weather)
        self.assertEqual(len(sc.incidents), 1)


class TestRoadSpec(unittest.TestCase):
    def test_fleetpy_demand_file_relative_to_data_root(self):
        spec = load_run_spec(ROOT / "benchmarks" / "specs" / "road_example_400.json")
        sc = build_scenario(spec.scenario)
        self.assertGreater(len(sc.requests), 300)
        self.assertEqual(len(sc.drivers), 25)


if __name__ == "__main__":
    unittest.main()
