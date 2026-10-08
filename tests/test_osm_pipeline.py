"""OSM → network pipeline (sprint 02: S02-1, S02-2, S02-3; AC02-1, AC02-2, AC02-3).

Builds the committed Hồ Gươm fixture (``tests/data/osm``) — needs pyosmium, pyproj and h3, else skipped. Tests on
the full Hà Nội network run only when it has been built (``python -m kami.osm build hanoi``).
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kami.network import FileZoneSystem, FleetPyNetwork, RoadNetwork
from kami.osm.geo import Polygon, assemble_rings, haversine, in_ring
from kami.osm.graph import _largest_scc, direction, parse_maxspeed
from kami.osm.extract import motor_access
from tests.helpers import OSM_FIXTURE_CONFIG, cpp_router, fixture_data_root, hanoi_built, osm_build_deps

FIXTURE = "hoan_kiem_fixture"


def _digest(folder: Path):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


class TestPipelineHelpers(unittest.TestCase):
    """Pure-Python parts (no pyosmium needed)."""

    def test_direction_and_access(self):
        self.assertEqual(direction({"highway": "primary", "oneway": "yes"}), 1)
        self.assertEqual(direction({"highway": "primary", "oneway": "-1"}), -1)
        self.assertEqual(direction({"highway": "residential"}), 0)
        self.assertEqual(direction({"highway": "tertiary", "junction": "roundabout"}), 1)
        self.assertEqual(direction({"highway": "motorway"}), 1)
        self.assertEqual(direction({"highway": "motorway", "oneway": "no"}), 0)
        self.assertIsNone(direction({"highway": "primary", "oneway": "reversible"}))
        self.assertEqual(motor_access({}), (True, True))
        self.assertEqual(motor_access({"motorcar": "no", "motorcycle": "yes"}), (False, True))
        self.assertEqual(motor_access({"motorcycle": "no"}), (True, False))
        self.assertEqual(motor_access({"access": "no", "motorcycle": "yes"}), (False, True))
        self.assertEqual(motor_access({"motor_vehicle": "no"}), (False, False))
        self.assertEqual(parse_maxspeed("50"), 50.0)
        self.assertAlmostEqual(parse_maxspeed("30 mph"), 48.28, places=2)
        self.assertIsNone(parse_maxspeed("VN:urban"))

    def test_geometry(self):
        sq = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
        self.assertTrue(in_ring((0.5, 0.5), sq))
        self.assertFalse(in_ring((1.5, 0.5), sq))
        poly = Polygon([[sq, [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6), (0.4, 0.4)]]])
        self.assertTrue(poly.contains((0.2, 0.2)))
        self.assertFalse(poly.contains((0.5, 0.5)))           # in the hole
        rings = assemble_rings([[(1, (0, 0)), (2, (1, 0))], [(3, (1, 1)), (2, (1, 0))], [(3, (1, 1)), (1, (0, 0))]])
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(haversine((105.85, 21.0), (105.86, 21.0)), 1038.4, delta=1.0)

    def test_largest_scc(self):
        edges = {(1, 2): 0, (2, 1): 0, (2, 3): 0, (3, 4): 0, (4, 3): 0, (4, 5): 0, (5, 3): 0}
        self.assertEqual(_largest_scc([1, 2, 3, 4, 5], edges), {3, 4, 5})


@unittest.skipUnless(osm_build_deps(), "needs pyosmium, pyproj and h3 (pip install kami[osm])")
class TestFixtureBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(fixture_data_root())
        cls.net = RoadNetwork(FIXTURE, data_root=cls.root, backend="python")

    def test_ac02_1_rebuild_is_identical_and_readable(self):
        from kami.osm import build, load_config

        tmp = Path(tempfile.mkdtemp(prefix="kami-osm-rebuild-"))
        try:
            manifest = build(load_config(OSM_FIXTURE_CONFIG), tmp, log=lambda *a: None)
            for sub in ("networks/" + FIXTURE, "zones/fixture_h3_r8/" + FIXTURE, "zones/fixture_wards/" + FIXTURE):
                a, b = _digest(self.root / sub), _digest(tmp / sub)
                self.assertTrue(a, sub)
                self.assertEqual(a, b, f"{sub} differs between two builds")
        finally:
            shutil.rmtree(tmp, True)
        src = json.loads((OSM_FIXTURE_CONFIG).read_text())["source"]
        self.assertEqual(manifest["source"]["sha256"], src["sha256"])
        self.assertEqual(manifest["source"]["date"], "2026-10-06")
        self.assertIn("ODbL", manifest["source"]["license"])
        self.assertEqual(manifest["crs"], "EPSG:32648")
        self.assertIs(FleetPyNetwork, RoadNetwork)
        net = FleetPyNetwork(FIXTURE, data_root=self.root)
        self.assertEqual(net.num_nodes(), manifest["graph"]["nodes"])
        self.assertEqual(len(net.edge_list()), manifest["graph"]["edges"])

    def test_wrong_sha256_refuses_to_build(self):
        from kami.osm import fetch, load_config

        cfg = load_config(OSM_FIXTURE_CONFIG)
        cfg["source"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            fetch(cfg, log=lambda *a: None)

    def test_kami_extension_files(self):
        g = self.net.graph
        self.assertIsNotNone(g.lons)                           # lon/lat without pyproj
        lon, lat = self.net.lonlat(0)
        self.assertTrue(105.84 < lon < 105.86 and 21.02 < lat < 21.04)
        self.assertIsNotNone(g.road_class)
        self.assertIn("bike", g.allow)                        # the simulated motorcycle=no way
        self.assertIn("car", g.allow)                         # motorcar=no alleys of the real data
        a, b = g.edges[0]
        geom = self.net.edge_geometry(a, b)
        self.assertGreaterEqual(len(geom), 2)
        self.assertAlmostEqual(geom[0][0], g.lons[a], places=6)
        self.assertAlmostEqual(geom[-1][1], g.lats[b], places=6)

    def test_ac02_2_connectivity(self):
        net = self.net
        g = net.graph
        # the pipeline keeps the largest SCC of the car ∪ motorbike graph: every node is in it
        self.assertEqual(len(net._main_scc()), net.num_nodes())
        # location nodes are reachable by *every* vehicle group (motorbike-only alleys are excluded)
        share = len(net.location_nodes()) / net.num_nodes()
        self.assertGreaterEqual(share, 0.9)
        for grp, allowed in g.allow.items():
            scc = net._main_scc(allowed)
            self.assertTrue(set(net.location_nodes()) <= scc, grp)

    def test_ac02_3_every_node_one_zone(self):
        for name in ("fixture_h3_r8", "fixture_wards"):
            zs = FileZoneSystem(self.net, name, data_root=self.root)
            self.assertEqual(set(zs.node_zone), set(range(self.net.num_nodes())), name)
            self.assertTrue(all(zs.nodes_in(z) for z in zs.zones()), name)
            rows = (self.root / "zones" / name / FIXTURE / "zone_definitions.csv").read_text().splitlines()
            self.assertEqual(len(rows) - 1, len(zs.zones()), name)
        wards = (self.root / "zones" / "fixture_wards" / FIXTURE / "zone_definitions.csv").read_text()
        self.assertIn("Phường Hoàn Kiếm", wards)              # wards after the 2025 reform

    @unittest.skipUnless(cpp_router(), "C++ router not built")
    def test_s02_2_check_command(self):
        from kami.osm.check import check

        res = check(FIXTURE, n_pairs=100, python_pairs=50, data_root=str(self.root))
        self.assertEqual(res["reachable_share"], 1.0)
        self.assertEqual(res["python_vs_cpp_same_route_or_cost"], "50/50")


@unittest.skipUnless(hanoi_built(), "Hà Nội network not built (python -m kami.osm build hanoi)")
class TestHanoiNetwork(unittest.TestCase):
    def test_hanoi_network_and_zones(self):
        net = RoadNetwork("hanoi", backend="python")
        manifest = json.loads((net.network_dir / "manifest.json").read_text())
        self.assertEqual(manifest["graph"]["nodes"], net.num_nodes())
        self.assertEqual(len(net._main_scc()), net.num_nodes())
        self.assertGreaterEqual(len(net.location_nodes()) / net.num_nodes(), 0.9)
        for name in ("hanoi_h3_r8", "hanoi_wards"):
            zs = FileZoneSystem(net, name)
            self.assertEqual(len(zs.node_zone), net.num_nodes())
            self.assertEqual(len(zs.zones()), manifest["zones"][name]["zones"])
            self.assertTrue(all(zs.nodes_in(z) for z in zs.zones()))


if __name__ == "__main__":
    unittest.main()
