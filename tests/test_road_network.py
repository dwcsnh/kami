"""Road networks (``kami.network.road``): Python and C++ routers, zone files, demand replay, dynamic travel times."""
import heapq
import math
import shutil
import tempfile
import unittest
from pathlib import Path

from kami.core.engine import Simulation
from kami.network import FileZoneSystem, FleetPyNetwork, FleetPyZoneSystem, RoadNetwork
from kami.network.road import default_data_root, network_path
from kami.network.road.cpp import PyNetwork
from kami.policy import Baseline
from kami.scenario import ScenarioBuilder

DEMAND = default_data_root() / "demand/example_demand/matched/example_network/example_100.csv"
PY = RoadNetwork("example_network", backend="python")
CPP = RoadNetwork("example_network", backend="cpp") if PyNetwork is not None else None

try:
    import pyproj  # noqa: F401
    HAVE_PYPROJ = True
except ImportError:
    HAVE_PYPROJ = False


def dijkstra(net, o, d):
    """Reference shortest travel time (plain Dijkstra, stop-only nodes are not passed through)."""
    g = net.graph
    best = {o: 0.0}
    pq = [(0.0, o)]
    while pq:
        c, n = heapq.heappop(pq)
        if n == d:
            return c
        if c > best.get(n, math.inf) or (n != o and g.stop_only[n]):
            continue
        for m, (tt, _dist) in g.out_edges[n].items():
            if c + tt < best.get(m, math.inf):
                best[m] = c + tt
                heapq.heappush(pq, (c + tt, m))
    return math.inf


def pairs(net, k=25):
    locs = net.location_nodes()
    return [(locs[(i * 37) % len(locs)], locs[(i * 101 + 7) % len(locs)]) for i in range(k)]


class TestRoadNetwork(unittest.TestCase):
    def test_loads_example_network(self):
        self.assertEqual(PY.num_nodes(), 7617)
        self.assertGreater(len(PY.location_nodes()), 0.9 * PY.num_nodes())
        self.assertIs(FleetPyNetwork, RoadNetwork)          # kami 0.1 names still work
        self.assertIs(FleetPyZoneSystem, FileZoneSystem)

    def test_python_router_is_shortest(self):
        for o, d in pairs(PY):
            tt, _dist = PY.base_travel(o, d)
            self.assertAlmostEqual(tt, dijkstra(PY, o, d), places=6)

    def test_path_matches_travel_time(self):
        for net in filter(None, (PY, CPP)):
            for o, d in pairs(net, 10):
                p = net.path(o, d)
                self.assertEqual((p[0][0], p[-1][0]), (o, d))
                self.assertAlmostEqual(p[-1][1], net.base_travel(o, d)[0], delta=1e-6)
                self.assertTrue(all(b in net.graph.out_edges[a] for (a, _), (b, _) in zip(p, p[1:])))

    def test_many_to_one_respects_radius(self):
        ps = pairs(PY, 30)
        d = ps[0][1]
        res = PY.many_to_one([o for o, _ in ps], d, max_tt=600)
        self.assertTrue(res)
        for o, (tt, _dist) in res.items():
            self.assertLessEqual(tt, 600)
            self.assertAlmostEqual(tt, dijkstra(PY, o, d), places=6)

    def test_node_factor_slows_routes(self):
        slow = lambda n: 3.0
        o, d = pairs(PY, 1)[0]
        self.assertAlmostEqual(PY.base_travel(o, d, slow)[0], 3 * PY.base_travel(o, d)[0], places=6)

    @unittest.skipIf(CPP is None, "C++ router not built (python -m kami.network.road.cpp.build)")
    def test_cpp_matches_python(self):
        ps = pairs(PY, 40)
        for o, d in ps:
            self.assertAlmostEqual(CPP.base_travel(o, d)[0], PY.base_travel(o, d)[0], places=6)
            self.assertEqual([n for n, _ in CPP.path(o, d)], [n for n, _ in PY.path(o, d)])
        d = ps[0][1]
        a = PY.many_to_one([o for o, _ in ps], d, max_tt=900)
        b = CPP.many_to_one([o for o, _ in ps], d, max_tt=900)
        self.assertEqual(set(a), set(b))

    @unittest.skipIf(CPP is None, "C++ router not built")
    def test_live_factors(self):
        net = RoadNetwork("example_network", backend="cpp")
        o, d = pairs(net, 1)[0]
        route = [n for n, _ in net.path(o, d)]
        net.apply_live_factors({n: 4.0 for n in route[1:]})
        self.assertGreater(net.live_travel(o, d)[0], net.base_travel(o, d)[0])
        net.apply_live_factors({})
        self.assertAlmostEqual(net.live_travel(o, d)[0], net.base_travel(o, d)[0], places=6)

    @unittest.skipUnless(HAVE_PYPROJ, "pyproj not installed")
    def test_lonlat(self):
        lon, lat = PY.lonlat(PY.location_nodes()[0])
        self.assertTrue(11 < lon < 12 and 48 < lat < 49)   # example network: Munich

    def test_zone_file(self):
        zones = FileZoneSystem(PY, "example_zones")
        self.assertEqual(len(zones.node_zone), PY.num_nodes())
        self.assertGreater(len(zones.zones()), 1)

    def test_network_folder_path_and_data_root(self):
        self.assertEqual(network_path("example_network"), default_data_root() / "networks/example_network")
        self.assertEqual(RoadNetwork(default_data_root() / "networks/example_network", backend="python").num_nodes(),
                         PY.num_nodes())
        with self.assertRaises(FileNotFoundError):
            RoadNetwork("no_such_network")

    def test_replay_demand_and_incident(self):
        builder = ScenarioBuilder(PY, FileZoneSystem(PY, "example_zones"))
        sc = builder.from_fleetpy_demand(DEMAND, n_drivers=20)
        self.assertEqual(len(sc.requests), 100)
        self.assertGreater(Simulation(sc, Baseline()).run().metrics()["platform.trips"], 50)
        net = CPP or PY
        builder = ScenarioBuilder(net, FileZoneSystem(net, "example_zones"))
        sc = builder.preset("accident", seed=1, demand_per_hour=80, n_drivers=30, t_end=8.5 * 3600)
        sim = Simulation(sc, Baseline()).run()
        self.assertIn("INCIDENT_START", sim.log.counts())
        if net.backend == "cpp":
            self.assertFalse(net._live_factor)   # live state restored after the incident


class TestDynamicTravelTimes(unittest.TestCase):
    """Time-dependent travel times: numbered folders and a travel-time-factor dynamics file."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        src = default_data_root() / "networks/example_network/base"
        cls.dir = cls.tmp / "net"
        shutil.copytree(src, cls.dir / "base")
        o, d = pairs(PY, 1)[0]
        cls.o, cls.d = o, d
        route = [n for n, _ in PY.path(o, d)]
        (cls.dir / "3600").mkdir()
        with open(cls.dir / "3600" / "edges_td_att.csv", "w") as f:
            f.write("from_node,to_node,edge_tt\n")
            for a, b in zip(route, route[1:]):
                f.write(f"{a},{b},{PY.graph.out_edges[a][b][0] * 10}\n")
        (cls.dir / "factors.csv").write_text("simulation_time,travel_time_factor\n0,1.0\n7200,2.0\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_folder_dynamics(self):
        for backend in ["python"] + (["cpp"] if PyNetwork is not None else []):
            net = RoadNetwork(self.dir, backend=backend)
            before = net.base_travel(self.o, self.d)[0]
            self.assertFalse(net.update_network(1800))
            self.assertTrue(net.update_network(3600))
            self.assertGreater(net.base_travel(self.o, self.d)[0], before)
            loaded = RoadNetwork(self.dir, backend=backend, scenario_time=5000)
            self.assertAlmostEqual(loaded.base_travel(self.o, self.d)[0], net.base_travel(self.o, self.d)[0], places=6)

    def test_factor_dynamics(self):
        net = RoadNetwork(self.dir, backend="python", network_dynamics_file="factors.csv")
        before = net.base_travel(self.o, self.d)[0]
        self.assertTrue(net.update_network(7200))
        self.assertAlmostEqual(net.base_travel(self.o, self.d)[0], 2 * before, places=6)


if __name__ == "__main__":
    unittest.main()
