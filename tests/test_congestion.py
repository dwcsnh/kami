"""Zone × hour congestion (sprint 02: S02-4, S02-5; AC02-4, AC02-5)."""
import tempfile
import unittest
from pathlib import Path

from kami.config import RunSpec, SpecError, TrafficSpec, build_run
from kami.congestion import DEFAULT_GROUP_PROFILES, CongestionModel
from kami.core.engine import SimConfig, Simulation
from kami.network import FileZoneSystem, GridNetwork, RoadNetwork, SquareZoneSystem
from kami.scenario import ScenarioBuilder
from kami.traffic import TrafficLayer
from tests.helpers import cpp_router, fixture_data_root, hanoi_built, osm_build_deps

H = 3600.0
NET = GridNetwork(16000, 16000, 250)
ZONES = SquareZoneSystem(NET, 1000)


def grid_od(net, x0, y0, x1, y1):
    return net.nearest_node(x0, y0), net.nearest_node(x1, y1)


def travel_at(traffic, o, d, t, **kw):
    traffic.apply_period(t)
    return traffic.travel(o, d, t, **kw)[0]


class TestCongestionGrid(unittest.TestCase):
    def setUp(self):
        self.tl = TrafficLayer(NET, ZONES, congestion={})        # default profiles, ring around the grid centre

    def test_ac02_4_peaks_slower_than_night(self):
        o, d = grid_od(NET, 7000, 7500, 9000, 8500)             # inside the core ring
        t23 = travel_at(self.tl, o, d, 23 * H)
        for h in (8, 18):
            self.assertGreater(travel_at(self.tl, o, d, h * H), 1.5 * t23, h)
        # the profile decides: 8 h / 23 h = core profile ratio on a uniform grid
        ratio = travel_at(self.tl, o, d, 8 * H) / t23
        self.assertAlmostEqual(ratio, DEFAULT_GROUP_PROFILES["core"][8] / DEFAULT_GROUP_PROFILES["core"][23], places=6)

    def test_ac02_5_zones_differ_in_the_same_hour(self):
        m = self.tl.congestion
        groups = {m.zone_group(z) for z in ZONES.zones()}
        self.assertEqual(groups, {"core", "inner", "outer"})
        core = next(z for z in ZONES.zones() if m.zone_group(z) == "core")
        outer = next(z for z in ZONES.zones() if m.zone_group(z) == "outer")
        self.assertNotEqual(m.zone_factor(core, 8), m.zone_factor(outer, 8))
        # same length OD (2 km) in the core and in the outer ring
        co, cd = grid_od(NET, 7000, 8000, 9000, 8000)
        oo, od = grid_od(NET, 500, 500, 2500, 500)
        r_core = travel_at(self.tl, co, cd, 8 * H) / travel_at(self.tl, co, cd, 23 * H)
        r_outer = travel_at(self.tl, oo, od, 8 * H) / travel_at(self.tl, oo, od, 23 * H)
        self.assertGreater(r_core, r_outer * 1.2)

    def test_replaces_hour_profile_and_keeps_weather(self):
        tl = TrafficLayer(NET, ZONES, congestion={}, hour_profile=[5.0] * 24)
        self.assertEqual(tl.multiplier(8 * H), 1.0)            # decision D11
        tl.set_weather("rain")
        self.assertEqual(tl.multiplier(8 * H), 1.25)
        plain = TrafficLayer(NET, ZONES)
        self.assertEqual(plain.multiplier(8 * H), plain.hour_profile[8])

    def test_zone_hour_file(self):
        z = ZONES.zone_of(NET.nearest_node(100, 100))
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("zone,hour,factor\n")
            fh.write(f"{z},8,3.0\n")
        tl = TrafficLayer(NET, ZONES, congestion={"kind": "file", "file": fh.name})
        Path(fh.name).unlink()
        n = NET.nearest_node(100, 100)
        self.assertEqual(tl.congestion.node_factor(n, 8), 3.0)
        self.assertEqual(tl.congestion.node_factor(n, 9), 1.0)
        other = NET.nearest_node(8000, 8000)
        self.assertEqual(tl.congestion.node_factor(other, 8), 1.0)

    def test_explicit_zone_groups_and_validation(self):
        zg = {str(z): ("core" if i % 2 else "outer") for i, z in enumerate(ZONES.zones())}
        m = CongestionModel(zone_groups=zg).bind(NET, ZONES)
        self.assertEqual({m.zone_group(z) for z in ZONES.zones()}, {"core", "outer"})
        with self.assertRaises(ValueError):
            CongestionModel(zone_groups={str(z): "nope" for z in ZONES.zones()}).bind(NET, ZONES)
        with self.assertRaises(SpecError):
            TrafficSpec.from_dict({"congestion": {"profiles": {"core": [1.0] * 23}}})
        with self.assertRaises(SpecError):
            TrafficSpec.from_dict({"congestion": {"kind": "file"}})
        with self.assertRaises(SpecError):
            TrafficSpec.from_dict({"vehicle_groups": {"truck": {}}})
        spec = TrafficSpec.from_dict({"congestion": {"period_s": 1800, "center": {"lon": 105.85, "lat": 21.03}},
                                      "vehicle_groups": {"bike": {"speed_factor": 0.8}}})
        self.assertEqual(TrafficSpec.from_dict(spec.to_dict()), spec)
        self.assertEqual(TrafficSpec.from_dict({}).to_dict(), TrafficSpec().to_dict())
        self.assertNotIn("congestion", TrafficSpec().to_dict())   # kami 0.1 documents are unchanged


def grid_scenario(**kw):
    b = ScenarioBuilder(NET, ZONES, traffic=dict(kw.pop("traffic", {})))
    return b.preset("weekday_am_peak", seed=3, demand_per_hour=150, n_drivers=40, t_start=7 * H, t_end=9.2 * H, **kw)


class TestCongestionUpdates(unittest.TestCase):
    """S02-5: CONGESTION_UPDATE at every period, legs re-timed when their remaining time changes enough."""

    def run_sim(self, **cfg):
        sc = grid_scenario(traffic={"congestion": {}})
        return Simulation(sc, config=SimConfig(**cfg)).run()

    def test_updates_logged_and_deterministic(self):
        a, b = self.run_sim(), self.run_sim()
        ups = a.log.filter("CONGESTION_UPDATE")
        self.assertEqual([r[0] for r in ups][:3], [7 * H, 8 * H, 9 * H])
        self.assertTrue(any(r[4]["retimed"] > 0 for r in ups))
        self.assertEqual(a.metrics(), b.metrics())
        self.assertEqual(list(a.log), list(b.log))

    def test_threshold_controls_retiming(self):
        never = self.run_sim(retime_threshold=1e9)
        self.assertTrue(all(r[4]["retimed"] == 0 for r in never.log.filter("CONGESTION_UPDATE")))
        always = self.run_sim(retime_threshold=0.0, retime_min_s=0.0)
        n_always = sum(r[4]["retimed"] for r in always.log.filter("CONGESTION_UPDATE"))
        n_default = sum(r[4]["retimed"] for r in self.run_sim().log.filter("CONGESTION_UPDATE"))
        self.assertGreaterEqual(n_always, n_default)

    def test_no_congestion_no_event(self):
        sim = Simulation(grid_scenario()).run()
        self.assertEqual(sim.log.filter("CONGESTION_UPDATE"), [])

    def test_spec_run(self):
        doc = {"name": "c", "scenario": {"network": {"kind": "grid", "width_m": 6000, "height_m": 6000},
                                         "traffic": {"congestion": {}},
                                         "source": {"kind": "synthetic", "t_start": 25200, "t_end": 28800,
                                                    "demand_per_hour": 100}, "n_drivers": 20}}
        sim = build_run(RunSpec.from_dict(doc)).simulation().run()
        self.assertTrue(sim.log.filter("CONGESTION_UPDATE"))


@unittest.skipUnless(osm_build_deps(), "needs pyosmium, pyproj and h3 to build the OSM fixture")
class TestCongestionRoad(unittest.TestCase):
    """Edge travel times re-set per period on a real (fixture) road network, C++ and Python backends."""

    @classmethod
    def setUpClass(cls):
        cls.root = fixture_data_root()

    def backends(self):
        return ["python"] + (["cpp"] if cpp_router() else [])

    def test_ac02_4_and_5_on_fixture(self):
        for backend in self.backends():
            net = RoadNetwork("hoan_kiem_fixture", data_root=self.root, backend=backend)
            zones = FileZoneSystem(net, "fixture_h3_r8", data_root=self.root)
            # Hoàn Kiếm is the default centre: the whole fixture is "core"
            tl = TrafficLayer(net, zones, congestion={})
            self.assertEqual({tl.congestion.zone_group(z) for z in zones.zones()}, {"core"})
            locs = net.location_nodes()
            o, d = locs[0], locs[-1]
            t23 = travel_at(tl, o, d, 23 * H)
            self.assertGreater(travel_at(tl, o, d, 8 * H), 1.4 * t23, backend)
            self.assertGreater(travel_at(tl, o, d, 18 * H), 1.4 * t23, backend)
            # ring centred elsewhere: two groups inside the fixture, different factors in the same hour
            tl2 = TrafficLayer(net, zones, congestion={"center": (105.8445, 21.0225), "ring_radii_m": [700, 5000]})
            groups = {tl2.congestion.zone_group(z) for z in zones.zones()}
            self.assertGreaterEqual(len(groups), 2)
            f = {g: tl2.congestion.profiles[g][8] for g in groups}
            self.assertGreater(len(set(f.values())), 1)

    def test_cpp_and_python_agree_under_congestion(self):
        if not cpp_router():
            self.skipTest("C++ router not built")
        nets = {b: RoadNetwork("hoan_kiem_fixture", data_root=self.root, backend=b) for b in ("python", "cpp")}
        tls = {b: TrafficLayer(n, FileZoneSystem(n, "fixture_h3_r8", data_root=self.root), congestion={},
                               vehicle_groups={"car": {}, "bike": {}}) for b, n in nets.items()}
        locs = nets["python"].location_nodes()
        pairs = [(locs[i], locs[(i * 7 + 3) % len(locs)]) for i in range(0, len(locs), 9)]
        for h in (8, 23):
            for b in tls:
                tls[b].apply_period(h * H)
            for g in ("car", "bike"):
                for o, d in pairs:
                    a = tls["python"].travel(o, d, h * H, group=g)[0]
                    c = tls["cpp"].travel(o, d, h * H, group=g)[0]
                    self.assertAlmostEqual(a, c, places=4)

    def test_incident_on_top_of_congestion(self):
        if not cpp_router():
            self.skipTest("C++ router not built")
        from kami.traffic import Incident

        net = RoadNetwork("hoan_kiem_fixture", data_root=self.root, backend="cpp")
        zones = FileZoneSystem(net, "fixture_h3_r8", data_root=self.root)
        tl = TrafficLayer(net, zones, congestion={})
        locs = net.location_nodes()
        o, d = locs[3], locs[-3]
        tl.apply_period(8 * H)
        base = tl.travel(o, d, 8 * H)[0]
        tl.start_incident(Incident("x", set(zones.zones()), 2.0))
        live = tl.travel(o, d, 8 * H)[0]
        self.assertAlmostEqual(live, 2 * base, places=4)
        self.assertAlmostEqual(tl.estimate(o, d, 8 * H)[0], base, places=6)     # platform does not see it
        tl.apply_period(23 * H)                                                 # base changes, incident kept
        self.assertAlmostEqual(tl.travel(o, d, 23 * H)[0], 2 * tl.estimate(o, d, 23 * H)[0], places=4)
        tl.end_incident("x")
        self.assertAlmostEqual(tl.travel(o, d, 23 * H)[0], tl.estimate(o, d, 23 * H)[0], places=6)

    def test_network_state_is_reset_between_runs(self):
        net = RoadNetwork("hoan_kiem_fixture", data_root=self.root)
        zones = FileZoneSystem(net, "fixture_h3_r8", data_root=self.root)
        locs = net.location_nodes()
        o, d = locs[1], locs[-2]
        free = net.base_travel(o, d)[0]
        TrafficLayer(net, zones, congestion={}).apply_period(8 * H)
        self.assertGreater(net.base_travel(o, d)[0], free)
        TrafficLayer(net, zones)                                 # a new run without congestion
        self.assertEqual(net.base_travel(o, d)[0], free)


@unittest.skipUnless(hanoi_built(), "Hà Nội network not built")
class TestCongestionHanoi(unittest.TestCase):
    def test_ac02_4_inner_city_od(self):
        net = RoadNetwork("hanoi")
        zones = FileZoneSystem(net, "hanoi_h3_r8")
        tl = TrafficLayer(net, zones, congestion={})
        o = net.node_at_lonlat(105.8412, 21.0245)      # Văn Miếu
        d = net.node_at_lonlat(105.8558, 21.0285)      # Hồ Gươm
        t23 = travel_at(tl, o, d, 23 * H)
        self.assertGreater(travel_at(tl, o, d, 8 * H), 1.5 * t23)
        self.assertGreater(travel_at(tl, o, d, 18 * H), 1.5 * t23)
        groups = {tl.congestion.zone_group(z) for z in zones.zones()}
        self.assertEqual(groups, {"core", "inner", "outer"})


if __name__ == "__main__":
    unittest.main()
