"""Sprint 01 — declarative specs: validation (AC01-3) and dict round-trip (AC01-4)."""
import json
import tempfile
import unittest
from pathlib import Path

from kami.config import (BehaviorSpec, ChargingStationSpec, FleetComposition, FleetSpec, PolicyGroupMember,
                         PolicyGroupSpec, PolicySpec, Ref, RunSpec, ScenarioSpec, SpecError, VehicleTypeSpec,
                         load_run_spec, policy_params_schema)
from kami.policy import POLICIES
from tests.helpers import small_run_spec

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "specs"


def errors(cls, doc):
    with unittest.TestCase().assertRaises(SpecError) as cm:
        cls.from_dict(doc)
    return dict(cm.exception.errors)


class TestValidation(unittest.TestCase):
    def test_missing_required_field(self):
        e = errors(RunSpec, {"name": "x"})
        self.assertIn("scenario", e)
        self.assertIn("thiếu", e["scenario"])
        e = errors(ScenarioSpec, {"source": {"kind": "preset"}})
        self.assertIn("source.preset", e)

    def test_wrong_type(self):
        e = errors(ScenarioSpec, {"source": {"kind": "preset", "preset": "rain"}, "n_drivers": "many"})
        self.assertIn("n_drivers", e)
        self.assertIn("sai kiểu", e["n_drivers"])
        e = errors(ScenarioSpec, {"source": {"kind": "preset", "preset": "rain"}, "seed": True})
        self.assertIn("seed", e)

    def test_out_of_range_and_enum(self):
        e = errors(ScenarioSpec, {"source": {"kind": "preset", "preset": "rain", "demand_per_hour": -1},
                                  "network": {"kind": "grid", "spacing_m": 0}, "zones": {"kind": "hexagon"}})
        self.assertIn("source.demand_per_hour", e)
        self.assertIn("network.spacing_m", e)
        self.assertIn("zones.kind", e)

    def test_unknown_field_with_suggestion(self):
        e = errors(ScenarioSpec, {"source": {"kind": "preset", "preset": "rain"}, "n_driver": 10})
        self.assertIn("n_driver", e)
        self.assertIn("n_drivers", e["n_driver"])

    def test_unknown_preset_and_plugin(self):
        e = errors(ScenarioSpec, {"source": {"kind": "preset", "preset": "rainy"}})
        self.assertIn("'rain'", e["source.preset"])
        e = errors(PolicySpec, {"plugin": "surge_pricing"})
        self.assertIn("plugin", e)

    def test_policy_param_typo_points_to_field(self):
        doc = {"scenario": {"source": {"kind": "preset", "preset": "rain"}},
               "policy_group": {"members": [{"policy": {"plugin": "pool_after_wait",
                                                        "params": {"wait_treshold": 120}}}]}}
        e = errors(RunSpec, doc)
        path = "policy_group.members[0].policy.params.wait_treshold"
        self.assertIn(path, e)
        self.assertIn("wait_threshold", e[path])

    def test_policy_param_types_and_matching(self):
        e = errors(PolicySpec, {"plugin": "surge", "params": {"every": "often", "matching": {"solver": "lp"}}})
        self.assertIn("params.every", e)
        self.assertIn("params.matching.solver", e)
        PolicySpec.from_dict({"plugin": "pool_after_wait", "params": {"retry_every": None, "surcharge": 15000.5,
                                                                      "matching": {"max_pickup_eta": 600}}})

    def test_all_errors_reported_at_once(self):
        e = errors(RunSpec, {"scenario": {"source": {"kind": "preset", "preset": "rain"}, "seed": "x",
                                          "n_drivers": 0}, "seed": 1.5, "colour": "red"})
        self.assertEqual({"scenario.seed", "scenario.n_drivers", "seed", "colour"}, set(e))

    def test_fleet_vehicle_type_must_exist(self):
        doc = {"scenario": {"source": {"kind": "preset", "preset": "rain"}},
               "vehicle_types": [{"name": "car4"}],
               "fleets": [{"name": "a", "composition": [{"vehicle_type": "car5", "count": 2}]}]}
        e = errors(RunSpec, doc)
        self.assertIn("fleets[0].composition[0].vehicle_type", e)
        e = errors(FleetSpec, {"name": "a", "composition": [{"vehicle_type": "car4", "count": 0}]})
        self.assertIn("composition[0].count", e)

    def test_time_window_and_schema_version(self):
        e = errors(ScenarioSpec, {"source": {"kind": "preset", "preset": "rain", "overrides": {"t_end": 3600}}})
        self.assertIn("source.overrides", e)
        e = errors(ScenarioSpec, {"source": {"kind": "synthetic", "t_start": 7200, "t_end": 3600}})
        self.assertIn("source.t_end", e)
        e = errors(RunSpec, {"schema_version": 99, "scenario": {"source": {"kind": "preset", "preset": "rain"}}})
        self.assertIn("schema_version", e)

    def test_charging_station_location(self):
        errors(ChargingStationSpec, {"name": "a"})
        errors(ChargingStationSpec, {"name": "a", "lon": 105.8, "lat": 21.0, "node": 3})
        errors(ChargingStationSpec, {"name": "a", "lon": 105.8})
        ChargingStationSpec.from_dict({"name": "a", "lon": 105.8, "lat": 21.0})

    def test_behavior_models(self):
        e = errors(BehaviorSpec, {"models": {"booking": {"class": "WeibullCancel"}}})
        self.assertIn("models.booking.class", e)
        e = errors(BehaviorSpec, {"models": {"booking": {"class": "LogitBooking", "params": {"asc": "x", "b": 1}}}})
        self.assertIn("models.booking.params.asc", e)
        self.assertIn("models.booking.params.b", e)
        BehaviorSpec.from_dict({"models": {"cancel_wait": {"class": "HazardScaler",
                                                           "params": {"inner": {"class": "WeibullCancel"},
                                                                      "factor": 1.3}}}})

    def test_sim_config(self):
        e = errors(RunSpec, {"scenario": {"source": {"kind": "preset", "preset": "rain"}},
                             "sim_config": {"batch_window": 0, "fare": {"take_rate": 2}, "speed": 3}})
        self.assertEqual({"sim_config.batch_window", "sim_config.fare.take_rate", "sim_config.speed"}, set(e))

    def test_invalid_json_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text("{not json")
            with self.assertRaises(SpecError):
                load_run_spec(p)


class TestRoundTrip(unittest.TestCase):
    def roundtrip(self, spec):
        cls = type(spec)
        again = cls.from_dict(json.loads(json.dumps(spec.to_dict())))
        self.assertEqual(spec, again)
        self.assertEqual(spec.to_dict(), again.to_dict())

    def test_every_spec_kind(self):
        self.roundtrip(VehicleTypeSpec("bike", "bike", 1, range_km=90.0))
        self.roundtrip(FleetSpec("f", [FleetComposition("bike", 3), FleetComposition("car", 2)]))
        self.roundtrip(ChargingStationSpec("c", node=4, ports=3, power_kw=22.0))
        self.roundtrip(PolicySpec("surge", {"every": 60}, name="s", version=2))
        self.roundtrip(PolicyGroupSpec("g", [PolicyGroupMember(Ref("s", 2), {"every": 30}),
                                             PolicyGroupMember(PolicySpec("baseline"), enabled=False)]))
        self.roundtrip(small_run_spec("accident", "pool_after_wait", {"surcharge": 0}))
        self.roundtrip(small_run_spec().scenario)

    def test_example_files(self):
        files = sorted(EXAMPLES.glob("*.json"))
        self.assertTrue(files)
        for f in files:
            self.roundtrip(load_run_spec(f))

    def test_policy_params_schema(self):
        s = policy_params_schema(POLICIES["pool_after_wait"])
        self.assertIn("wait_threshold", s)
        self.assertIn("matching", s)
        self.assertEqual(set(policy_params_schema(POLICIES["baseline"])), {"matching", "batch_window"})


if __name__ == "__main__":
    unittest.main()
