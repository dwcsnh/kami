"""Sprint 01 — database storage: migrations (AC01-5), round-trip (AC01-4), recorded runs (AC01-6)."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from kami.config import (ChargingStationSpec, FleetComposition, FleetSpec, PolicyGroupMember, PolicyGroupSpec,
                         PolicySpec, Ref, RunSpec, SpecError, VehicleTypeSpec, run_spec)
from kami.eventlog import load
from kami.store import Repository, connect, current_version, execute, migrate
from kami.store.db import migrations
from tests.helpers import assert_metrics_equal, small_run_spec

TABLES = {"vehicle_type", "fleet", "fleet_vehicle", "charging_station", "policy", "policy_version", "policy_group",
          "policy_group_member", "scenario", "run", "run_metric_summary", "run_metric_timeseries", "run_artifact",
          "schema_migrations"}


def tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


class TestMigrations(unittest.TestCase):
    def test_migrate_empty_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            conn = connect(Path(d) / "k.db")
            self.assertEqual(current_version(conn), 0)
            applied = migrate(conn)
            self.assertEqual(applied, [v for v, _, _ in migrations()])
            self.assertTrue(TABLES <= tables(conn))
            before = conn.execute("SELECT * FROM schema_migrations").fetchall()
            self.assertEqual(migrate(conn), [])
            self.assertEqual([tuple(r) for r in before],
                             [tuple(r) for r in conn.execute("SELECT * FROM schema_migrations").fetchall()])
            conn.close()
            conn = connect(Path(d) / "k.db")        # reopen an existing database
            self.assertEqual(migrate(conn), [])
            self.assertEqual(current_version(conn), max(v for v, _, _ in migrations()))
            conn.close()


class TestRepository(unittest.TestCase):
    def setUp(self):
        self.repo = Repository.open()

    def tearDown(self):
        self.repo.close()

    def test_round_trip_every_entity(self):
        r = self.repo
        vt = VehicleTypeSpec("vf_e34", "car", 4, range_km=285.0)
        bike = VehicleTypeSpec("bike", "bike", 1)
        self.assertEqual(r.get_vehicle_type(r.save_vehicle_type(vt)), vt)
        r.save_vehicle_type(bike)
        self.assertEqual(r.get_vehicle_type("bike"), bike)
        fl = FleetSpec("taxi", [FleetComposition("vf_e34", 10), FleetComposition("bike", 5)])
        self.assertEqual(r.get_fleet(r.save_fleet(fl)), fl)
        cs = ChargingStationSpec("hub", lon=105.85, lat=21.03, ports=8, power_kw=60.0)
        self.assertEqual(r.get_charging_station(r.save_charging_station(cs)), cs)
        sc = small_run_spec("rain").scenario
        self.assertEqual(r.get_scenario(r.save_scenario(sc)), sc)
        pid, v = r.save_policy(PolicySpec("surge", {"every": 60}), name="surge_fast")
        self.assertEqual(r.get_policy(pid), PolicySpec("surge", {"every": 60}, name="surge_fast", version=v))
        g = PolicyGroupSpec("g", [PolicyGroupMember(Ref("surge_fast", 1), {"max_surge": 1.5}),
                                  PolicyGroupMember(PolicySpec("heatmap_reposition", {"max_moves": 4}), enabled=False)])
        self.assertEqual(r.get_policy_group(r.save_policy_group(g)), g)
        self.assertEqual([x["name"] for x in r.list_vehicle_types()], ["vf_e34", "bike"])

    def test_update_and_soft_delete(self):
        r = self.repo
        i = r.save_vehicle_type(VehicleTypeSpec("car", seats=4))
        self.assertEqual(r.save_vehicle_type(VehicleTypeSpec("car", seats=7)), i)
        self.assertEqual(r.get_vehicle_type("car").seats, 7)
        r.save_fleet(FleetSpec("f", [FleetComposition("car", 2)]))
        with self.assertRaises(ValueError):           # in use by a fleet
            r.delete_vehicle_type("car")
        r.delete_fleet("f")
        r.delete_vehicle_type("car")
        self.assertEqual(r.list_vehicle_types(), [])
        with self.assertRaises(KeyError):
            r.get_vehicle_type("car")
        self.assertEqual(r.get_vehicle_type(i).seats, 7)   # history stays readable by id
        j = r.save_vehicle_type(VehicleTypeSpec("car", seats=5))   # name reusable after delete
        self.assertNotEqual(i, j)

    def test_fleet_needs_stored_vehicle_types(self):
        with self.assertRaises(SpecError) as cm:
            self.repo.save_fleet(FleetSpec("f", [FleetComposition("ghost", 2)]))
        self.assertIn("composition[0].vehicle_type", cm.exception.paths())

    def test_save_validates(self):
        with self.assertRaises(SpecError):
            self.repo.save_policy(PolicySpec("surge", {"evry": 3}))
        with self.assertRaises(SpecError):
            self.repo.save_vehicle_type(VehicleTypeSpec("x", seats=0))

    def test_policy_versions_are_immutable(self):
        r = self.repo
        self.assertEqual(r.save_policy(PolicySpec("surge", {"every": 60}), "s"), (1, 1))
        self.assertEqual(r.save_policy(PolicySpec("surge", {"every": 60}), "s"), (1, 1))   # unchanged
        self.assertEqual(r.save_policy(PolicySpec("surge", {"every": 30}), "s"), (1, 2))
        self.assertEqual(r.add_policy_version("s", {"every": 10}), 3)
        self.assertEqual(r.policy_versions("s"), [1, 2, 3])
        self.assertEqual(r.get_policy("s", 1).params, {"every": 60})
        self.assertEqual(r.get_policy("s").version, 3)
        with self.assertRaises(SpecError):
            r.save_policy(PolicySpec("heatmap_reposition"), "s")   # same name, other plug-in
        # an unversioned reference is pinned at save time
        gid = r.save_policy_group(PolicyGroupSpec("g", [PolicyGroupMember(Ref("s"))]))
        self.assertEqual(r.get_policy_group(gid).members[0].policy, Ref("s", 3))
        row = r.conn.execute("SELECT * FROM policy_group_member WHERE group_id = ?", (gid,)).fetchone()
        self.assertEqual((row["plugin"], json.loads(row["params_json"])), ("surge", {"every": 10}))
        with self.assertRaises(SpecError):
            r.save_policy_group(PolicyGroupSpec("h", [PolicyGroupMember(Ref("s", 9))]))

    def test_resolve(self):
        r = self.repo
        r.save_vehicle_type(VehicleTypeSpec("car4"))
        r.save_fleet(FleetSpec("taxi", [FleetComposition("car4", 40)]))
        r.save_scenario(small_run_spec().scenario)
        r.save_policy(PolicySpec("surge", {"every": 60}), "s")
        spec = RunSpec.from_dict({"name": "x", "scenario": {"ref": "weekday_am_peak"}, "fleets": [{"ref": "taxi"}],
                                  "policy_group": {"members": [{"policy": {"ref": "s"}}]}})
        resolved, prov = r.resolve(spec)
        self.assertFalse(resolved.has_refs())
        self.assertEqual([v.name for v in resolved.vehicle_types], ["car4"])   # pulled in with the fleet
        self.assertEqual(resolved.policy_group.members[0].policy.version, 1)
        self.assertEqual(prov["policies"][0]["version"], 1)
        with self.assertRaises(SpecError) as cm:
            r.resolve(RunSpec.from_dict({"scenario": {"ref": "nope"}, "fleets": [{"ref": 99}]}))
        self.assertEqual(set(cm.exception.paths()), {"scenario", "fleets[0]"})


class TestExecute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repository.open(Path(self.tmp.name) / "k.db")
        self.artifacts = Path(self.tmp.name) / "runs"

    def tearDown(self):
        self.repo.close()
        self.tmp.cleanup()

    def test_execute_records_run(self):
        spec = small_run_spec("rain", "surge", {"every": 60})
        self.repo.save_scenario(spec.scenario)
        self.repo.save_policy(PolicySpec("surge", {"every": 60}), "surge60")
        by_ref = RunSpec.from_dict({"name": "r", "scenario": {"ref": "rain"},
                                    "policy_group": {"members": [{"policy": {"ref": "surge60"}}]}})
        res = execute(by_ref, self.repo, self.artifacts)
        self.assertEqual(res.status, "succeeded", res.error)
        run = self.repo.get_run(res.run_id)
        self.assertEqual(run["status"], "succeeded")
        self.assertIsNotNone(run["finished_at"])
        self.assertEqual(run["events"], res.sim.events_processed)
        self.assertEqual(run["source_spec"]["scenario"], {"ref": "rain"})
        self.assertEqual(run["provenance"]["policies"][0]["version"], 1)
        # snapshot: re-runnable without the database, same metrics (NFR-4 + NFR-1)
        snap = self.repo.run_spec(res.run_id)
        self.assertFalse(snap.has_refs())
        fresh = run_spec(snap).metrics()
        stored = self.repo.run_metrics(res.run_id)
        assert_metrics_equal(self, fresh, stored)
        assert_metrics_equal(self, run_spec(spec).metrics(), stored)
        ts = self.repo.run_timeseries(res.run_id)
        self.assertEqual(len(ts), len(res.sim.timeseries.rows))
        for a, b in zip(ts, res.sim.timeseries.rows):
            assert_metrics_equal(self, a, b)
        (art,) = self.repo.run_artifacts(res.run_id)
        self.assertEqual(art["kind"], "event_log")
        self.assertEqual(art["rows"], len(res.sim.log))
        self.assertEqual(len(load(art["path"])), len(res.sim.log))
        self.assertEqual(Path(art["path"]).stat().st_size, art["size_bytes"])

    def test_csv_and_no_event_log(self):
        for fmt, n in (("csv.gz", 1), ("none", 0)):
            spec = small_run_spec()
            spec.outputs.event_log = fmt
            res = execute(spec, self.repo, self.artifacts)
            arts = self.repo.run_artifacts(res.run_id)
            self.assertEqual(len(arts), n)
            if n:
                self.assertEqual(arts[0]["format"], "csv.gz")
                self.assertEqual(len(load(arts[0]["path"])), len(res.sim.log))

    def test_failed_run_is_recorded(self):
        spec = small_run_spec()
        spec.behavior.registry = str(Path(self.tmp.name) / "no_such_registry")   # fails while building
        res = execute(spec, self.repo, self.artifacts)
        self.assertEqual(res.status, "failed")
        run = self.repo.get_run(res.run_id)
        self.assertEqual(run["status"], "failed")
        self.assertIn("no_such_registry", run["error"])
        self.assertEqual(self.repo.list_runs(status="running"), [])

    def test_invalid_reference_creates_no_run(self):
        with self.assertRaises(SpecError):
            execute(RunSpec.from_dict({"scenario": {"ref": "missing"}}), self.repo, self.artifacts)
        self.assertEqual(self.repo.list_runs(), [])

    def test_nan_metrics_stored_as_null(self):
        spec = small_run_spec()
        res = execute(spec, self.repo, self.artifacts)
        nan_keys = [k for k, v in res.sim.metrics().items() if isinstance(v, float) and math.isnan(v)]
        self.assertTrue(nan_keys)
        row = self.repo.conn.execute("SELECT value FROM run_metric_summary WHERE run_id = ? AND name = ?",
                                     (res.run_id, nan_keys[0])).fetchone()
        self.assertIsNone(row[0])


if __name__ == "__main__":
    unittest.main()
