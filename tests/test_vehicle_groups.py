"""Vehicle groups on the network (sprint 02: S02-7; AC02-7)."""
import copy
import unittest

from kami.config import RunSpec, build_run
from kami.core.engine import SimConfig
from kami.network import FileZoneSystem, GridNetwork, RoadNetwork, SquareZoneSystem
from kami.network.road.network import FORBIDDEN_TT
from kami.traffic import TrafficLayer
from tests.helpers import cpp_router, fixture_data_root, osm_build_deps

H = 3600.0
NET = GridNetwork(8000, 8000, 250)
ZONES = SquareZoneSystem(NET, 1000)

FLEET_DOC = {
    "name": "groups",
    "scenario": {"network": {"kind": "grid", "width_m": 6000, "height_m": 6000},
                 "source": {"kind": "synthetic", "t_start": 25200, "t_end": 30600, "demand_per_hour": 160},
                 "seed": 4},
    "vehicle_types": [{"name": "car4", "group": "car", "seats": 4}, {"name": "bike1", "group": "bike", "seats": 1}],
    "fleets": [{"name": "cars", "composition": [{"vehicle_type": "car4", "count": 15}]},
               {"name": "bikes", "composition": [{"vehicle_type": "bike1", "count": 15}]}],
}


class TestGroupsGrid(unittest.TestCase):
    def test_ac02_7_speed_factor(self):
        tl = TrafficLayer(NET, ZONES, vehicle_groups={"car": {}, "bike": {"speed_factor": 0.8}})
        o, d = NET.nearest_node(500, 500), NET.nearest_node(6000, 4000)
        car = tl.travel(o, d, 8 * H, group="car")[0]
        bike = tl.travel(o, d, 8 * H, group="bike")[0]
        self.assertAlmostEqual(bike / car, 1 / 0.8, places=9)
        m = tl.many_to_one([o], d, 8 * H, group="bike")
        self.assertAlmostEqual(m[o][0], bike, places=6)

    def test_congestion_scale(self):
        tl = TrafficLayer(NET, ZONES, congestion={}, vehicle_groups={"car": {}, "bike": {"speed_factor": 1.0}})
        tl.apply_period(8 * H)
        o, d = NET.nearest_node(3500, 3500), NET.nearest_node(4500, 4500)     # core
        car = tl.travel(o, d, 8 * H, group="car")[0]
        bike = tl.travel(o, d, 8 * H, group="bike")[0]
        free = NET.base_travel(o, d)[0]
        self.assertAlmostEqual((bike / free - 1) / (car / free - 1), 0.5, places=6)   # default bike scale

    def test_undeclared_group_drives_as_car(self):
        tl = TrafficLayer(NET, ZONES)
        o, d = 3, 700
        self.assertEqual(tl.group("bike"), "car")
        self.assertEqual(tl.travel(o, d, 8 * H, group="bike"), tl.travel(o, d, 8 * H))

    def test_engine_uses_driver_group(self):
        doc = copy.deepcopy(FLEET_DOC)
        plain = build_run(RunSpec.from_dict(doc)).simulation().run()
        # without traffic.vehicle_groups bikes drive as cars: same run as an all-car fleet of the same seats
        self.assertTrue(all(d.group == "car" for d in plain.drivers.values()))
        doc["scenario"]["traffic"] = {"vehicle_groups": {"car": {}, "bike": {"speed_factor": 0.5}}}
        sim = build_run(RunSpec.from_dict(doc)).simulation().run()
        self.assertEqual({d.group for d in sim.drivers.values()}, {"car", "bike"})
        self.assertNotEqual(plain.metrics(), sim.metrics())
        built = build_run(RunSpec.from_dict(doc))
        built.config = SimConfig(record_trajectories=True)
        rec = built.simulation().run()
        groups = {t.group for t in rec.trajectories.legs}
        self.assertEqual(groups, {"car", "bike"})
        by_driver = {d.id: d.group for d in rec.drivers.values()}
        self.assertTrue(all(t.group == by_driver[t.driver_id] for t in rec.trajectories.legs))


@unittest.skipUnless(osm_build_deps(), "needs pyosmium, pyproj and h3 to build the OSM fixture")
class TestGroupsRoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_data_root()

    def backends(self):
        return ["python"] + (["cpp"] if cpp_router() else [])

    def network(self, backend):
        net = RoadNetwork("hoan_kiem_fixture", data_root=self.root, backend=backend)
        return net, FileZoneSystem(net, "fixture_h3_r8", data_root=self.root)

    def _route_edges(self, path):
        return list(zip([n for n, _ in path][:-1], [n for n, _ in path][1:]))

    def test_ac02_7_forbidden_edges_never_used(self):
        for backend in self.backends():
            net, zones = self.network(backend)
            tl = TrafficLayer(net, zones, vehicle_groups={"car": {}, "bike": {}})
            g = net.graph
            closed = {grp: {g.edges[i] for i, ok in enumerate(a) if not ok} for grp, a in g.allow.items()}
            self.assertTrue(closed["bike"] and closed["car"])
            locs = net.location_nodes()
            # routes from/to the ends of every forbidden edge: the group's routes must avoid it
            ends = sorted({n for es in closed.values() for e in es for n in e if n in set(locs)})
            used = {"car": 0, "bike": 0}
            for grp in ("car", "bike"):
                for i, o in enumerate(ends):
                    d = ends[(i * 5 + 1) % len(ends)]
                    if o == d:
                        continue
                    path = tl.path(o, d, group=grp)
                    edges = set(self._route_edges(path))
                    self.assertFalse(edges & closed[grp], f"{backend}/{grp}: {o}->{d} uses a forbidden edge")
                    other = "bike" if grp == "car" else "car"
                    used[other] += bool(edges & closed[other])
            # the other group does take some of these edges (they are real shortcuts)
            self.assertGreater(used["car"] + used["bike"], 0, backend)

    def test_ac02_7_speed_factor_on_open_route(self):
        for backend in self.backends():
            net, zones = self.network(backend)
            tl = TrafficLayer(net, zones, vehicle_groups={"car": {}, "bike": {"speed_factor": 0.9}})
            g = net.graph
            closed = {g.edges[i] for a in g.allow.values() for i, ok in enumerate(a) if not ok}
            locs = net.location_nodes()
            checked = 0
            for i in range(0, len(locs), 7):
                o, d = locs[i], locs[(i * 11 + 5) % len(locs)]
                if o == d:
                    continue
                pc = tl.path(o, d, group="car")
                pb = tl.path(o, d, group="bike")      # the bike may take a car-forbidden shortcut
                if [n for n, _ in pc] != [n for n, _ in pb] or set(self._route_edges(pc)) & closed:
                    continue
                car = tl.travel(o, d, 0.0, group="car")[0]
                bike = tl.travel(o, d, 0.0, group="bike")[0]
                self.assertAlmostEqual(bike / car, 1 / 0.9, places=6)
                checked += 1
            self.assertGreater(checked, 5)

    def test_forbidden_time_constant(self):
        net, _ = self.network("python")
        a, b = next(e for e, ok in zip(net.graph.edges, net.graph.allow["bike"]) if not ok)
        st = net._st("bike")
        self.assertEqual(st.graph.out_edges[a][b][0], FORBIDDEN_TT)
        self.assertNotEqual(net.graph.out_edges[a][b][0], FORBIDDEN_TT)   # cars may use it


if __name__ == "__main__":
    unittest.main()
