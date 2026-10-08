"""Zone × hour demand, Hà Nội presets, spec fields and outputs of sprint 02 (S02-8, decisions D15–D17)."""
import json
import tempfile
import unittest
from pathlib import Path

from kami.cli import main as cli
from kami.config import RunSpec, SpecError, build_run, build_scenario, load_run_spec
from kami.network import GridNetwork, SquareZoneSystem
from kami.scenario import ScenarioBuilder
from tests.helpers import fixture_data_root, hanoi_built, osm_build_deps

H = 3600.0
NET = GridNetwork(6000, 6000, 250)
ZONES = SquareZoneSystem(NET, 1000)
SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios" / "hanoi"

try:
    import pyarrow  # noqa: F401
    HAVE_PYARROW = True
except ImportError:
    HAVE_PYARROW = False


def two_zone_weights():
    """Zone '0_0' residential, zone '5_5' workplaces, everything else empty."""
    w = {z: {"nodes": len(ZONES.nodes_in(z)), "residential": 0, "work": 0, "poi": 0} for z in ZONES.zones()}
    w["0_0"]["residential"] = 1000
    w["5_5"]["work"] = 1000
    return w


class TestZonalSource(unittest.TestCase):
    def setUp(self):
        self.b = ScenarioBuilder(NET, ZONES)

    def test_deterministic(self):
        a = self.b.zonal(seed=1, t_start=7 * H, t_end=8 * H, demand_per_hour=200, n_drivers=20)
        b = self.b.zonal(seed=1, t_start=7 * H, t_end=8 * H, demand_per_hour=200, n_drivers=20)
        c = self.b.zonal(seed=2, t_start=7 * H, t_end=8 * H, demand_per_hour=200, n_drivers=20)
        key = lambda s: [(r.t, r.origin, r.dest) for r in s.requests] + [(d.loc, d.shift_start) for d in s.drivers]
        self.assertEqual(key(a), key(b))
        self.assertNotEqual(key(a), key(c))
        self.assertTrue(all(NET.crow_dist(r.origin, r.dest) >= 1000 for r in a.requests))
        self.assertEqual(a.tags["generator"], "zonal")

    def test_time_of_day_weights(self):
        w = two_zone_weights()
        kw = dict(seed=3, demand_per_hour=400, n_drivers=10, weights=w, smoothing=0.0, gravity_lambda_m=1e9,
                  min_trip_m=0)
        am = self.b.zonal(t_start=7 * H, t_end=8 * H, **kw)
        pm = self.b.zonal(t_start=17 * H, t_end=18 * H, **kw)
        zone = ZONES.zone_of
        self.assertTrue(all(zone(r.origin) == "0_0" and zone(r.dest) == "5_5" for r in am.requests))
        self.assertTrue(all(zone(r.origin) == "5_5" and zone(r.dest) == "0_0" for r in pm.requests))
        self.assertTrue(all(zone(d.loc) == "0_0" for d in am.drivers))     # drivers live in residential zones

    def test_gravity_shortens_trips(self):
        kw = dict(seed=4, t_start=12 * H, t_end=13 * H, demand_per_hour=400, n_drivers=5, min_trip_m=0)
        near = self.b.zonal(gravity_lambda_m=500, **kw)
        far = self.b.zonal(gravity_lambda_m=1e9, **kw)
        mean = lambda s: sum(NET.crow_dist(r.origin, r.dest) for r in s.requests) / len(s.requests)
        self.assertLess(mean(near), 0.8 * mean(far))

    def test_spec(self):
        doc = {"name": "z", "scenario": {"network": {"kind": "grid", "width_m": 6000, "height_m": 6000},
                                         "source": {"kind": "zonal", "t_start": 25200, "t_end": 28800,
                                                    "demand_per_hour": 150}, "n_drivers": 15}}
        spec = RunSpec.from_dict(doc)
        self.assertEqual(RunSpec.from_dict(spec.to_dict()).to_dict(), spec.to_dict())
        sim = build_run(spec).simulation().run()
        self.assertGreater(sim.metrics()["platform.trips"], 0)
        bad = json.loads(json.dumps(doc))
        bad["scenario"]["source"]["incidents"] = [{"at": "hotspot0"}]
        with self.assertRaises(SpecError):
            RunSpec.from_dict(bad)
        bad["scenario"]["source"]["incidents"] = [{"at": {"lon": 105.8}}]
        with self.assertRaises(SpecError) as e:
            RunSpec.from_dict(bad)
        self.assertIn("lat", str(e.exception))
        bad["scenario"]["source"] = {"kind": "zonal", "t_start": 10, "t_end": 5}
        with self.assertRaises(SpecError):
            RunSpec.from_dict(bad)


@unittest.skipUnless(osm_build_deps(), "needs pyosmium, pyproj and h3 to build the OSM fixture")
class TestZonalFixture(unittest.TestCase):
    def test_weights_file_and_lonlat_incident(self):
        root = fixture_data_root()
        doc = {"name": "fx", "scenario": {
            "network": {"kind": "road", "name": "hoan_kiem_fixture", "data_root": root},
            "zones": {"kind": "file", "name": "fixture_h3_r8"},
            "source": {"kind": "zonal", "t_start": 27000, "t_end": 28800, "demand_per_hour": 100, "min_trip_m": 300,
                       "incidents": [{"at": {"lon": 105.8522, "lat": 21.0287}, "t_offset": 600, "duration": 600}]},
            "n_drivers": 10}}
        sc = build_scenario(RunSpec.from_dict(doc).scenario)
        self.assertTrue(sc.tags["weighted"])                       # zone_weights.csv next to the zone file
        net = sc.network
        lon, lat = net.lonlat(sc.incidents[0].center)
        self.assertLess(abs(lon - 105.8522) + abs(lat - 21.0287), 0.003)


class TestHanoiPresets(unittest.TestCase):
    def test_preset_files_are_valid(self):
        files = sorted(SCENARIOS.glob("*.json"))
        self.assertEqual({p.stem for p in files}, {"weekday", "am_peak", "pm_peak_rain", "incident_arterial"})
        for p in files:
            spec = load_run_spec(p)
            sc = spec.scenario
            self.assertEqual(sc.network.name, "hanoi")
            self.assertEqual(sc.source.kind, "zonal")
            self.assertIsNotNone(sc.traffic.congestion)
            self.assertEqual(set(sc.traffic.vehicle_groups), {"car", "bike"})
        rain = load_run_spec(SCENARIOS / "pm_peak_rain.json").scenario.source
        self.assertEqual(rain.weather, [(16.5 * H, "rain")])
        inc = load_run_spec(SCENARIOS / "incident_arterial.json").scenario.source.incidents[0]
        self.assertEqual(inc["at"], {"lon": 105.8032, "lat": 20.9916})

    def test_presets_command_lists_them(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli(["presets"])
        self.assertIn("scenarios/hanoi/am_peak.json", out.getvalue())

    @unittest.skipUnless(hanoi_built(), "Hà Nội network not built")
    def test_ac02_8_am_peak_size(self):
        spec = load_run_spec(SCENARIOS / "am_peak.json")
        built = build_run(spec)
        self.assertGreaterEqual(len(built.scenario.requests), 10_000)
        self.assertGreaterEqual(len(built.scenario.drivers), 1_000)
        groups = {d.attrs["vehicle_group"] for d in built.scenario.drivers}
        self.assertEqual(groups, {"car", "bike"})
        self.assertTrue(built.config.record_trajectories)
        inc = build_scenario(load_run_spec(SCENARIOS / "incident_arterial.json").scenario).incidents[0]
        lon, lat = built.scenario.network.lonlat(inc.center)
        self.assertLess(abs(lon - 105.8032) + abs(lat - 20.9916), 0.002)


@unittest.skipUnless(HAVE_PYARROW, "needs pyarrow")
class TestTrajectoryOutputs(unittest.TestCase):
    DOC = {"name": "out", "scenario": {"network": {"kind": "grid", "width_m": 5000, "height_m": 5000},
                                       "source": {"kind": "zonal", "t_start": 25200, "t_end": 27000,
                                                  "demand_per_hour": 120}, "n_drivers": 10},
           "outputs": {"event_log": "none", "trajectories": "parquet"}}

    def test_cli_out_and_store(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "spec.json"
            spec.write_text(json.dumps(self.DOC))
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli(["run", "--spec", str(spec), "--out", str(Path(d) / "o")]), 0)
            self.assertTrue((Path(d) / "o" / "trajectories.parquet").exists())
            from kami.store import Repository, execute

            repo = Repository.open(str(Path(d) / "k.db"))
            res = execute(RunSpec.from_dict(self.DOC), repo, Path(d) / "runs")
            self.assertEqual(res.status, "succeeded")
            kinds = {a["kind"] for a in repo.run_artifacts(res.run_id)}
            self.assertIn("trajectories", kinds)


if __name__ == "__main__":
    unittest.main()
