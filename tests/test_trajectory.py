"""Routes and trajectories (sprint 02: S02-6; AC02-6)."""
import tempfile
import unittest
from pathlib import Path

from kami.core.engine import SimConfig, Simulation
from kami.network import FileZoneSystem, GridNetwork, RoadNetwork, SquareZoneSystem
from kami.scenario import ScenarioBuilder
from kami.trajectory import load
from tests.helpers import fixture_data_root, osm_build_deps

H = 3600.0
NET = GridNetwork(6000, 6000, 250)
ZONES = SquareZoneSystem(NET, 1000)

try:
    import pyarrow  # noqa: F401
    HAVE_PYARROW = True
except ImportError:
    HAVE_PYARROW = False


def run(scenario, record=True, **cfg):
    return Simulation(scenario, config=SimConfig(record_trajectories=record, **cfg)).run()


class TrajectoryChecks:
    """AC02-6 assertions shared by the grid and road-network cases."""

    def is_edge(self, net, a, b) -> bool:
        raise NotImplementedError

    def check_ac02_6(self, sim):
        net, rec = sim.network, sim.trajectories
        self.assertGreater(len(rec), 0)
        for drv in rec.drivers():
            legs = sorted(rec.legs_of(drv), key=lambda t: t.leg_seq)
            last_t, last_node = None, None
            for t in legs:
                self.assertEqual(len(t.nodes), len(t.times))
                for a, b in zip(t.nodes[:-1], t.nodes[1:]):
                    self.assertTrue(self.is_edge(net, a, b), f"driver {drv} leg {t.leg_seq}: {a}->{b} is no edge")
                for x, y in zip(t.times[:-1], t.times[1:]):
                    self.assertLessEqual(x, y + 1e-9)
                if last_t is not None:
                    self.assertGreaterEqual(t.times[0], last_t - 1e-9)
                    self.assertEqual(t.nodes[0], last_node, f"driver {drv}: leg {t.leg_seq} starts elsewhere")
                last_t, last_node = t.times[-1], t.nodes[-1]
        # the end of every pick-up / drop-off leg is the PICKUP / DROPOFF event
        ends = {}
        for t in rec.legs:
            if t.purpose == "stop" and not t.cut:
                ends.setdefault((t.driver_id, t.rider_id), []).append((t.times[-1], t.nodes[-1]))
        for kind in ("PICKUP", "DROPOFF"):
            rows = sim.log.filter(kind)
            self.assertTrue(rows)
            for t_ev, _, rid, did, _ in rows:
                r = sim.riders[rid]
                node, exact = (r.origin, r.t_pickup) if kind == "PICKUP" else (r.dest, r.t_dropoff)
                self.assertLessEqual(abs(exact - t_ev), 5e-4)          # the event log keeps 3 decimals
                hits = [x for x in ends.get((did, rid), []) if abs(x[0] - exact) <= 1e-6]
                self.assertTrue(hits, f"{kind} of rider {rid} at {t_ev}: no leg ends then")
                self.assertTrue(any(n == node for _, n in hits))

    def check_neutral(self, scenario):
        a, b = run(scenario, record=False), run(scenario, record=True)
        self.assertEqual(a.metrics(), b.metrics())
        self.assertEqual(list(a.log), list(b.log))
        self.assertIsNone(a.trajectories)


def grid_scenario(**kw):
    b = ScenarioBuilder(NET, ZONES, traffic=kw.pop("traffic", {}))
    return b.preset(kw.pop("preset", "weekday_am_peak"), seed=2, demand_per_hour=120, n_drivers=30,
                    t_end=kw.pop("t_end", 8.5 * H), **kw)


class TestTrajectoryGrid(unittest.TestCase, TrajectoryChecks):
    def is_edge(self, net, a, b):
        return net.crow_dist(a, b) == net.spacing

    def test_ac02_6_baseline(self):
        self.check_ac02_6(run(grid_scenario()))

    def test_ac02_6_with_incident_and_congestion(self):
        sc = grid_scenario(preset="accident", traffic={"congestion": {}}, t_end=9.2 * H)
        sim = run(sc)
        self.assertTrue(any(t.cut for t in sim.trajectories.legs))     # re-planned / re-timed legs
        self.check_ac02_6(sim)

    def test_recording_does_not_change_results(self):
        self.check_neutral(grid_scenario())
        self.check_neutral(grid_scenario(preset="accident", traffic={"congestion": {}}, t_end=9.2 * H))

    def test_of_driver(self):
        sim = run(grid_scenario())
        drv = sim.trajectories.drivers()[0]
        pts = sim.trajectories.of(drv)
        self.assertGreater(len(pts), 2)
        self.assertTrue(all(p[2] <= q[2] + 1e-9 for p, q in zip(pts, pts[1:])))
        x0, y0, x1, y1 = NET.bounds()
        self.assertTrue(all(x0 <= x <= x1 and y0 <= y <= y1 for x, y, _ in pts))   # planar x/y on a grid

    @unittest.skipUnless(HAVE_PYARROW, "needs pyarrow")
    def test_parquet_round_trip(self):
        sim = run(grid_scenario())
        with tempfile.TemporaryDirectory() as d:
            path = sim.trajectories.save(Path(d) / "trajectories.parquet")
            rows, meta = load(path)
        self.assertEqual(meta["coords"], "xy")
        self.assertEqual(len(rows), len(sim.trajectories))
        r = rows[0]
        t = sim.trajectories.legs[0]
        self.assertEqual(r["nodes"], t.nodes)
        self.assertEqual(r["times"], t.times)
        self.assertEqual(len(r["path_lon"]), len(r["path_t"]))


@unittest.skipUnless(osm_build_deps(), "needs pyosmium, pyproj and h3 to build the OSM fixture")
class TestTrajectoryRoad(unittest.TestCase, TrajectoryChecks):
    @classmethod
    def setUpClass(cls):
        root = fixture_data_root()
        cls.net = RoadNetwork("hoan_kiem_fixture", data_root=root)
        cls.zones = FileZoneSystem(cls.net, "fixture_h3_r8", data_root=root, neighbor_radius_m=600)

    def is_edge(self, net, a, b):
        return b in net.graph.out_edges[a]

    def scenario(self, **traffic):
        b = ScenarioBuilder(self.net, self.zones, traffic=traffic)
        return b.zonal(name="traj", seed=1, t_start=7.5 * H, t_end=8.6 * H, demand_per_hour=150, n_drivers=25,
                       min_trip_m=300,
                       incidents=[{"t_offset": 0.3 * H, "duration": 0.4 * H, "at": {"lon": 105.852, "lat": 21.028},
                                   "radius_m": 400, "factor": 3.0}])

    def test_ac02_6_on_roads(self):
        sim = run(self.scenario(congestion={}, vehicle_groups={"car": {}, "bike": {}}))
        self.check_ac02_6(sim)

    def test_neutral_on_roads(self):
        self.check_neutral(self.scenario(congestion={}))

    @unittest.skipUnless(HAVE_PYARROW, "needs pyarrow")
    def test_lonlat_export_follows_geometry(self):
        sim = run(self.scenario())
        with tempfile.TemporaryDirectory() as d:
            rows, meta = load(sim.trajectories.save(Path(d) / "t.parquet"))
        self.assertEqual(meta["coords"], "lonlat")
        self.assertEqual(meta["network"], "hoan_kiem_fixture")
        row = max(rows, key=lambda r: len(r["nodes"]))
        self.assertGreaterEqual(len(row["path_lon"]), len(row["nodes"]))
        self.assertTrue(all(105.84 < x < 105.87 for x in row["path_lon"]))
        self.assertTrue(all(a <= b + 1e-9 for a, b in zip(row["path_t"], row["path_t"][1:])))


if __name__ == "__main__":
    unittest.main()
