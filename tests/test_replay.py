"""Replay files for the web visualizer (sprint 03: S03-1…S03-3; AC03-1, AC03-3, AC03-5, AC03-9)."""
import gzip
import json
import math
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from kami.core.engine import SimConfig, Simulation
from kami.network import FileZoneSystem, GridNetwork, RoadNetwork, SquareZoneSystem
from kami.replay import SimplifyParams, export, from_simulation, load, simplify, tables, validate
from kami.replay.query import ReplayIndex, position_in
from kami.replay.schema import SCHEMA_VERSION, read_json
from kami.replay.simplify import max_deviation
from kami.scenario import ScenarioBuilder
from tests.helpers import cpp_router, fixture_data_root, hanoi_built, osm_build_deps

H = 3600.0
ROOT = Path(__file__).resolve().parents[1]
NET = GridNetwork(5000, 5000, 250)
ZONES = SquareZoneSystem(NET, 1000)


def grid_sim(seed=3, **cfg):
    sc = ScenarioBuilder(NET, ZONES).preset("weekday_am_peak", seed=seed, demand_per_hour=150, n_drivers=30,
                                            t_end=8.25 * H)
    return Simulation(sc, config=SimConfig(record_trajectories=True, timeseries_interval_s=60, **cfg)).run()


def files_bytes(folder):
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir())}


# ----------------------------------------------------------------------------- independent state from the event log
def states_from_log(sim):
    """Per driver: [(t, state)] from the event log only (no trajectories), and the times that are ambiguous."""
    changes, fuzzy = {}, {}
    for t, ev, rid, did, info in sim.log.rows:
        if did is None:
            continue
        st = None
        if ev == "DRIVER_ONLINE":
            st = "idle"
        elif ev == "TRIP_ACCEPTED":
            st = "pickup"
        elif ev == "PICKUP":
            st = "on_trip"
        elif ev == "DROPOFF":
            st = "idle"
        elif ev == "RIDER_CANCEL" and info.get("phase") == "matched":
            st = "idle"
        elif ev == "IDLE_MOVE":
            st = "cruising" if info["purpose"] == "idle" else "reposition"
            # arrival: the move turns idle at t + tt unless re-timed by congestion → ambiguous around it
            changes.setdefault(did, []).append((t, st))
            changes[did].append((t + info["tt"], "idle?"))
            fuzzy.setdefault(did, []).append((t + info["tt"] * 0.8 - 60, t + info["tt"] * 1.2 + 60))
            continue
        elif ev == "DRIVER_OFFLINE":
            st = "offline"
        if st:
            changes.setdefault(did, []).append((t, st))
    return changes, fuzzy


def log_state_at(changes, t):
    """State at ``t``; an ``idle?`` (scheduled arrival) only applies if nothing else happened before ``t``."""
    cur, cur_t = None, None
    for tc, st in sorted(changes, key=lambda x: x[0]):
        if tc > t:
            break
        if st == "idle?":
            if cur in ("cruising", "reposition"):
                cur, cur_t = "idle", tc
            continue
        cur, cur_t = st, tc
    return cur, cur_t


class StateChecks:
    def check_states_match_log(self, sim, n=2000):
        docs = tables(from_simulation(sim))
        idx = ReplayIndex(docs["trips"])
        changes, fuzzy = states_from_log(sim)
        rng = random.Random(0)
        vehicles = sorted(changes)
        t_lo, t_hi = docs["manifest"]["time"]["start"], docs["manifest"]["time"]["end"]
        checked = 0
        for _ in range(n):
            v = vehicles[int(rng.random() * len(vehicles))]
            t = t_lo + rng.random() * (t_hi - t_lo)
            ch = changes[v]
            if any(abs(t - tc) < 1.0 for tc, _ in ch):
                continue                          # within 1 s of a state change (times rounded to 0.1 s)
            if any(a <= t <= b for a, b in fuzzy.get(v, [])):
                continue
            want, _ = log_state_at(ch, t)
            got = idx.state_at(v, t)
            if want in (None, "offline"):
                self.assertIsNone(got, f"vehicle {v} t={t:.1f}: offline in the log, {got} in the replay")
                continue
            checked += 1
            if got != want:
                self.fail(f"vehicle {v} t={t:.1f}: log says {want}, replay says {got}")
        self.assertGreater(checked, n // 4)
        return checked


# ----------------------------------------------------------------------------- tests
class TestSimplify(unittest.TestCase):
    def test_keeps_ends_and_bounds_error(self):
        rng = random.Random(1)
        for trial in range(30):
            n = 2 + int(rng.random() * 200)
            xs, ys, ts = [105.85], [21.03], [0.0]
            for _ in range(n - 1):
                xs.append(xs[-1] + (rng.random() - 0.3) * 2e-4)
                ys.append(ys[-1] + (rng.random() - 0.5) * 2e-5)
                ts.append(ts[-1] + rng.random() * 3)
            keep = simplify(xs, ys, ts, 1.0, 0.5)
            self.assertEqual(keep[0], 0)
            self.assertEqual(keep[-1], n - 1)
            self.assertEqual(keep, sorted(set(keep)))
            d, dt = max_deviation(xs, ys, ts, keep)
            self.assertLessEqual(d, 1.0 + 1e-9)
            self.assertLessEqual(dt, 0.5 + 1e-9)

    def test_drops_collinear_constant_speed_points(self):
        xs = [0.0, 10.0, 20.0, 30.0, 40.0]
        ys = [0.0] * 5
        ts = [0.0, 1.0, 2.0, 3.0, 4.0]
        self.assertEqual(simplify(xs, ys, ts, lonlat=False), [0, 4])
        # same line, but the vehicle stops in the middle: the timing must be kept
        ts2 = [0.0, 1.0, 10.0, 11.0, 12.0]
        self.assertIn(2, simplify(xs, ys, ts2, lonlat=False))

    def test_repeated_points(self):
        self.assertEqual(simplify([1.0, 1.0, 1.0], [2.0, 2.0, 2.0], [5.0, 5.0, 5.0], lonlat=False), [0, 2])

    def test_position_in(self):
        path, ts = [0.0, 0.0, 10.0, 0.0, 10.0, 20.0], [0.0, 10.0, 30.0]
        self.assertEqual(position_in(path, ts, -1), (0.0, 0.0))
        self.assertEqual(position_in(path, ts, 5), (5.0, 0.0))
        self.assertEqual(position_in(path, ts, 20), (10.0, 10.0))
        self.assertEqual(position_in(path, ts, 99), (10.0, 20.0))


class TestReplayGrid(unittest.TestCase, StateChecks):
    @classmethod
    def setUpClass(cls):
        cls.sim = grid_sim()
        cls.tmp = Path(tempfile.mkdtemp(prefix="kami-replay-"))
        cls.out = export(cls.sim, cls.tmp / "a")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_valid_and_deterministic(self):
        self.assertEqual(validate(self.out), [])
        again = export(grid_sim(), self.tmp / "b")
        self.assertEqual(files_bytes(self.out), files_bytes(again))
        plain = export(grid_sim(), self.tmp / "c", compress=False)
        self.assertEqual(validate(plain), [])
        self.assertEqual(load(plain)["trips"], load(self.out)["trips"])

    def test_manifest(self):
        man = read_json(self.out / "manifest.json")
        self.assertEqual(man["schema_version"], SCHEMA_VERSION)
        self.assertEqual(man["kind"], "kami.replay")
        self.assertEqual(man["coords"], "xy")
        self.assertEqual([s["id"] for s in man["states"]], ["idle", "cruising", "pickup", "on_trip", "reposition"])
        self.assertEqual(man["counts"]["vehicles"], 30)
        self.assertNotIn("created", json.dumps(man))

    def test_segments_continuous_and_cover_shift(self):
        d = load(self.out)
        tr = d["trips"]
        by = {}
        for i, v in enumerate(tr["vehicle"]):
            by.setdefault(v, []).append(i)
        for v in d["vehicles"]:
            idx = by[v["id"]]
            self.assertEqual(tr["t0"][idx[0]], v["shift"][0])
            self.assertEqual(tr["t1"][idx[-1]], v["shift"][1])
            for a, b in zip(idx, idx[1:]):
                self.assertAlmostEqual(tr["t1"][a], tr["t0"][b], delta=0.11)
                self.assertEqual(tr["path"][a][-2:], tr["path"][b][:2])

    def test_ac03_3_states_match_event_log(self):
        self.check_states_match_log(self.sim)

    def test_ac03_5_metrics_are_the_engine_time_series(self):
        m = load(self.out)["metrics"]
        rows = self.sim.timeseries.rows
        self.assertEqual(m["interval_s"], 60)
        self.assertEqual(m["t"], [r["t"] for r in rows])
        self.assertIn("rider.pickup_mean", m["series"])
        for name, col in m["series"].items():
            want = [None if isinstance(r[name], float) and math.isnan(r[name]) else r[name] for r in rows]
            self.assertEqual(col, want, name)

    def test_events(self):
        ev = load(self.out)["events"]
        types = set(ev["type"])
        self.assertTrue({"request", "booked", "matched", "pickup", "dropoff"} <= types)
        n_req = sum(1 for t in ev["type"] if t == "request")
        self.assertEqual(n_req, len(self.sim.scenario.requests))
        i = ev["type"].index("request")
        self.assertIsNotNone(ev["to_lon"][i])

    def test_validate_catches_errors(self):
        def broken(mutate):
            d = self.tmp / f"x{len(list(self.tmp.iterdir()))}"
            shutil.copytree(self.out, d)
            mutate(d)
            return validate(d)

        self.assertTrue(any("thiếu file" in e for e in broken(lambda d: (d / "events.json.gz").unlink())))

        def flip_byte(d):
            p = d / "vehicles.json.gz"
            raw = gzip.decompress(p.read_bytes()).replace(b'"seats":4', b'"seats":5')
            p.write_bytes(gzip.compress(raw))
        self.assertTrue(any("sha256" in e for e in broken(flip_byte)))

        def rewrite(d, fn):
            p = d / "trips.json.gz"
            tr = json.loads(gzip.decompress(p.read_bytes()))
            fn(tr)
            p.write_bytes(gzip.compress(json.dumps(tr).encode()))
            man = json.loads((d / "manifest.json").read_text())
            del man["files"]["trips"]["sha256"]
            (d / "manifest.json").write_text(json.dumps(man))

        def time_back(tr):
            i = max(range(len(tr["ts"])), key=lambda k: len(tr["ts"][k]))
            tr["ts"][i][1] = tr["ts"][i][0] - 5
        self.assertTrue(any("thời gian giảm" in e for e in broken(lambda d: rewrite(d, time_back))))
        self.assertTrue(any("trạng thái lạ" in e for e in broken(
            lambda d: rewrite(d, lambda tr: tr["state"].__setitem__(0, "flying")))))

        def newer(d):
            man = json.loads((d / "manifest.json").read_text())
            man["schema_version"] = SCHEMA_VERSION + 1
            (d / "manifest.json").write_text(json.dumps(man))
        self.assertTrue(any("mới hơn" in e for e in broken(newer)))

    def test_forward_compatible_extra_state_and_field(self):
        d = self.tmp / "fwd"
        shutil.copytree(self.out, d)
        man = json.loads((d / "manifest.json").read_text())
        man["states"].append({"id": "charging", "label": "Đang sạc", "color": "state.charging"})
        man["future_field"] = {"x": 1}
        (d / "manifest.json").write_text(json.dumps(man))
        self.assertEqual(validate(d), [])

    def test_needs_trajectories(self):
        sc = ScenarioBuilder(NET, ZONES).preset("weekday_am_peak", seed=1, demand_per_hour=50, n_drivers=5,
                                                t_end=7.2 * H)
        with self.assertRaises(ValueError):
            from_simulation(Simulation(sc).run())

    def test_cut_legs_and_cancellations_with_reposition_policy(self):
        from kami.policy import POLICIES

        sc = ScenarioBuilder(NET, ZONES).preset("weekday_am_peak", seed=2, demand_per_hour=200, n_drivers=60,
                                                t_end=8.0 * H)
        sim = Simulation(sc, POLICIES["heatmap_reposition"](), config=SimConfig(record_trajectories=True)).run()
        self.assertTrue(any(s == "reposition" for s in tables(from_simulation(sim))["trips"]["state"]))
        out = export(sim, self.tmp / "repo")
        self.assertEqual(validate(out), [])
        self.check_states_match_log(sim, n=1000)


@unittest.skipUnless(osm_build_deps(), "needs pyosmium, pyproj and h3 to build the OSM fixture")
class TestReplayRoad(unittest.TestCase, StateChecks):
    """AC03-3 on real roads (Hồ Gươm OSM fixture) with congestion, an incident and vehicle groups."""

    @classmethod
    def setUpClass(cls):
        root = fixture_data_root()
        cls.net = RoadNetwork("hoan_kiem_fixture", data_root=root)
        cls.zones = FileZoneSystem(cls.net, "fixture_h3_r8", data_root=root, neighbor_radius_m=600)
        b = ScenarioBuilder(cls.net, cls.zones, traffic={"congestion": {}, "vehicle_groups": {"car": {}, "bike": {}}})
        sc = b.zonal(name="replay", seed=1, t_start=7.5 * H, t_end=8.6 * H, demand_per_hour=150, n_drivers=25,
                     min_trip_m=300,
                     incidents=[{"t_offset": 0.3 * H, "duration": 0.4 * H, "at": {"lon": 105.852, "lat": 21.028},
                                 "radius_m": 400, "factor": 3.0}])
        cls.sim = Simulation(sc, config=SimConfig(record_trajectories=True, timeseries_interval_s=60)).run()
        cls.tmp = Path(tempfile.mkdtemp(prefix="kami-replay-road-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_ac03_1_deterministic_and_valid(self):
        a = export(self.sim, self.tmp / "a")
        self.assertEqual(validate(a), [])
        man = read_json(a / "manifest.json")
        self.assertEqual(man["coords"], "lonlat")
        x0, y0, x1, y1 = man["bounds"]
        self.assertTrue(105.83 < x0 < x1 < 105.88 and 21.01 < y0 < y1 < 21.04, man["bounds"])
        self.assertIn("zoom", man["area"])
        b = export(self.sim, self.tmp / "b")
        self.assertEqual(files_bytes(a), files_bytes(b))

    def test_ac03_3_points_stay_on_the_road(self):
        """Kept points are points of the edge-geometry polyline; dropped ones are ≤ 1 m / 0.5 s away."""
        rows, _ = self.sim.trajectories.rows(geometry=True)
        worst_d = worst_t = 0.0
        for r in rows:
            xs, ys, ts = r["path_lon"], r["path_lat"], r["path_t"]
            keep = simplify(xs, ys, ts, 1.0, 0.5)
            d, dt = max_deviation(xs, ys, ts, keep)
            worst_d, worst_t = max(worst_d, d), max(worst_t, dt)
        self.assertLessEqual(worst_d, 1.0 + 1e-6)
        self.assertLessEqual(worst_t, 0.5 + 1e-6)
        # after rounding to 6 decimals (≈ 0.1 m), every exported point is within 1.5 m of the road polyline
        docs = tables(from_simulation(self.sim))
        orig = {}
        for r in rows:
            orig.setdefault(r["driver_id"], []).append(r)
        tr = docs["trips"]
        for path, v, st in zip(tr["path"], tr["vehicle"], tr["state"]):
            if len(path) <= 2:
                continue
            pts = [(x, y) for r in orig[v] for x, y in zip(r["path_lon"], r["path_lat"])]
            for x, y in list(zip(path[0::2], path[1::2]))[:: max(1, len(path) // 20)]:
                best = min(_m(x, y, px, py) for px, py in pts)
                self.assertLessEqual(best, 1.5)

    def test_ac03_3_states_match_event_log(self):
        self.check_states_match_log(self.sim)

    def test_simplification_reduces_points(self):
        rows, _ = self.sim.trajectories.rows(geometry=True)
        raw = sum(len(r["path_t"]) for r in rows)
        man = tables(from_simulation(self.sim))["manifest"]
        self.assertLess(man["counts"]["points"], raw)


def _m(x0, y0, x1, y1):
    k = math.cos(math.radians(y0))
    return math.hypot((x1 - x0) * k, y1 - y0) * 111_320.0


class TestSpecAndCli(unittest.TestCase):
    def test_zonal_area_limits_requests_and_starts(self):
        from kami.config.specs import RunSpec

        doc = json.loads((ROOT / "scenarios" / "hanoi" / "demo_center.json").read_text())

        rs = RunSpec.from_dict(doc)
        self.assertEqual(rs.scenario.source.area["bbox"], [105.8, 20.995, 105.87, 21.05])
        self.assertEqual(rs.outputs.replay, "json")
        self.assertEqual(RunSpec.from_dict(json.loads(rs.to_json())).to_dict(), rs.to_dict())
        # an old spec dumps exactly as before (no new keys)
        old = json.loads((ROOT / "scenarios" / "hanoi" / "am_peak.json").read_text())
        dumped = RunSpec.from_dict(old).to_dict()
        self.assertNotIn("replay", dumped["outputs"])
        self.assertNotIn("area", dumped["scenario"]["source"])
        # grid: area in network x/y
        b = ScenarioBuilder(NET, ZONES)
        sc = b.zonal(name="a", seed=1, t_start=7 * H, t_end=8 * H, demand_per_hour=200, n_drivers=20,
                     area=[0, 0, 2000, 2000])
        self.assertTrue(sc.requests)
        for r in sc.requests:
            self.assertIn(ZONES.zone_of(r.origin), {z for z in ZONES.zones()
                                                     if _center_in(ZONES, NET, z, 2000)})
        for d in sc.drivers:
            x, y = NET.coords(d.loc)
            self.assertLessEqual(max(x, y), 2250)
        full = b.zonal(name="a", seed=1, t_start=7 * H, t_end=8 * H, demand_per_hour=200, n_drivers=20)
        self.assertNotEqual([r.origin for r in full.requests], [r.origin for r in sc.requests])

    def test_bad_area(self):
        from kami.config import SpecError
        from kami.config.specs import RunSpec

        doc = json.loads((ROOT / "scenarios" / "hanoi" / "demo_center.json").read_text())
        doc["scenario"]["source"]["area"] = {"bbox": [105.9, 21.0, 105.8, 21.1]}
        with self.assertRaises(SpecError):
            RunSpec.from_dict(doc)

    def test_run_spec_out_writes_replay(self):
        from kami.cli import main
        from tests.helpers import small_run_spec

        spec = small_run_spec()
        spec.outputs.replay = "json"
        spec.outputs.event_log = "none"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "spec.json"
            p.write_text(spec.to_json())
            self.assertEqual(main(["run", "--spec", str(p), "--out", str(Path(d) / "out")]), 0)
            self.assertEqual(validate(Path(d) / "out" / "replay"), [])
            self.assertEqual(main(["replay", "validate", str(Path(d) / "out" / "replay")]), 0)
            man = read_json(Path(d) / "out" / "replay" / "manifest.json")
            self.assertEqual(len(man["run"]["spec_sha256"]), 64)

    def test_store_records_replay_artifact(self):
        from kami.store import Repository, execute
        from tests.helpers import small_run_spec

        spec = small_run_spec()
        spec.outputs.replay = "json"
        spec.outputs.event_log = "csv.gz"
        with tempfile.TemporaryDirectory() as d:
            repo = Repository.open(str(Path(d) / "k.db"))
            res = execute(spec, repo, Path(d) / "runs")
            self.assertEqual(res.status, "succeeded", res.error)
            kinds = [r[0] for r in repo.conn.execute("SELECT kind FROM run_artifact WHERE run_id = ?", (res.run_id,))]
            self.assertIn("replay", kinds)
            self.assertEqual(validate(Path(d) / "runs" / str(res.run_id) / "replay"), [])
            repo.close()

    def test_export_from_run_folder(self):
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            self.skipTest("needs pyarrow")
        from kami.cli import main
        from tests.helpers import small_run_spec

        spec = small_run_spec()
        spec.outputs.trajectories = "parquet"
        spec.outputs.event_log = "parquet"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "spec.json"
            p.write_text(spec.to_json())
            self.assertEqual(main(["run", "--spec", str(p), "--out", str(Path(d) / "run")]), 0)
            self.assertEqual(main(["replay", "export", str(Path(d) / "run"), "--out", str(Path(d) / "rp")]), 0)
            self.assertEqual(main(["replay", "export", "--spec", str(p), "--out", str(Path(d) / "rp2")]), 0)
            a, b = load(Path(d) / "rp"), load(Path(d) / "rp2")
            self.assertEqual(a["manifest"]["counts"]["segments"], b["manifest"]["counts"]["segments"])
            self.assertEqual(a["trips"]["state"], b["trips"]["state"])
            self.assertEqual(a["metrics"], b["metrics"])


def _center_in(zones, net, z, lim):
    nodes = zones.location_nodes_in(z)
    cx = sum(net.coords(n)[0] for n in nodes) / len(nodes)
    cy = sum(net.coords(n)[1] for n in nodes) / len(nodes)
    return cx <= lim and cy <= lim


class TestWebSamples(unittest.TestCase):
    """The small replay + samples the web tests (Vitest) use are the output of this kami version."""

    def test_web_samples_up_to_date(self):
        import importlib.util

        script = ROOT / "tests" / "data" / "replay" / "make_web_samples.py"
        spec = importlib.util.spec_from_file_location("make_web_samples", script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as d:
            mod.write(Path(d))
            self.assertEqual(files_bytes(Path(d)), files_bytes(mod.OUT),
                             "web test fixture outdated: python tests/data/replay/make_web_samples.py")


@unittest.skipUnless(hanoi_built() and cpp_router(), "needs the Hà Nội network (python -m kami.osm build hanoi)")
class TestDemoFixture(unittest.TestCase):
    """AC03-1: `python -m kami replay demo` twice → identical files, equal to the fixture in the repo, valid."""

    def test_ac03_1_demo_reproducible(self):
        from kami.replay.cli import DEMO_OUT, main

        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["demo", "--out", str(Path(d) / "a")]), 0)
            self.assertEqual(main(["demo", "--out", str(Path(d) / "b")]), 0)
            a = files_bytes(Path(d) / "a")
            self.assertEqual(a, files_bytes(Path(d) / "b"))
            self.assertEqual(validate(Path(d) / "a"), [])
            if DEMO_OUT.exists():
                self.assertEqual(a, files_bytes(DEMO_OUT), "committed fixture outdated: python -m kami replay demo")
            man = read_json(Path(d) / "a" / "manifest.json")
            self.assertEqual(man["counts"]["vehicles"], 300)
            self.assertLessEqual(sum(f["bytes"] for f in man["files"].values()), 3_000_000)


if __name__ == "__main__":
    unittest.main()
