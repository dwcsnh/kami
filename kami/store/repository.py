"""Repository: the only code that reads or writes the database (S01-4, S01-5).

It takes and returns **specs** (``kami.config``), never engine objects. ``save_*``
validates before writing; an entity is looked up by id (``int``, also when soft-deleted)
or by name (``str``, active rows only).
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from kami.config.specs import (SCHEMA_VERSION, ChargingStationSpec, FleetSpec, PolicyGroupMember, PolicyGroupSpec,
                               PolicySpec, Ref, RunSpec, ScenarioSpec, VehicleTypeSpec)
from kami.config.validate import Errors, SpecError
from kami.store.db import connect, migrate, utcnow

Key = Union[int, str]
SPEC_TABLES = {"vehicle_type": VehicleTypeSpec, "fleet": FleetSpec, "charging_station": ChargingStationSpec,
               "policy_group": PolicyGroupSpec, "scenario": ScenarioSpec}


def _js(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _num(v) -> Optional[float]:
    """SQLite has no NaN: store NULL."""
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) or math.isinf(v) else v


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def open(cls, path: Union[str, Path] = ":memory:", migrate_db: bool = True) -> "Repository":
        conn = connect(path)
        if migrate_db:
            migrate(conn)
        return cls(conn)

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def _tx(self):
        if self.conn.in_transaction:      # nested call: join the outer transaction
            yield
            return
        self.conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")

    # ================================================================== generic entities
    def _row(self, table: str, key: Key, what: Optional[str] = None) -> sqlite3.Row:
        if isinstance(key, Ref):
            key = key.ref
        if isinstance(key, int) and not isinstance(key, bool):
            row = self.conn.execute(f"SELECT * FROM {table} WHERE id = ?", (key,)).fetchone()
        else:
            row = self.conn.execute(f"SELECT * FROM {table} WHERE name = ? AND deleted_at IS NULL",
                                    (key,)).fetchone()
        if row is None:
            raise KeyError(f"{what or table} {key!r} không tồn tại")
        return row

    def _upsert(self, table: str, name: str, spec_json: str) -> int:
        now = utcnow()
        row = self.conn.execute(f"SELECT id FROM {table} WHERE name = ? AND deleted_at IS NULL", (name,)).fetchone()
        if row:
            self.conn.execute(f"UPDATE {table} SET spec_json = ?, updated_at = ? WHERE id = ?",
                              (spec_json, now, row["id"]))
            return row["id"]
        cur = self.conn.execute(f"INSERT INTO {table} (name, spec_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                                (name, spec_json, now, now))
        return cur.lastrowid

    def _get(self, table: str, key: Key):
        return SPEC_TABLES[table].from_dict(json.loads(self._row(table, key)["spec_json"]))

    def _list(self, table: str, include_deleted: bool = False) -> List[Dict[str, Any]]:
        where = "" if include_deleted else "WHERE deleted_at IS NULL"
        rows = self.conn.execute(f"SELECT id, name, created_at, updated_at, deleted_at FROM {table} {where} "
                                 f"ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def _soft_delete(self, table: str, key: Key) -> None:
        row = self._row(table, key)
        self.conn.execute(f"UPDATE {table} SET deleted_at = ? WHERE id = ?", (utcnow(), row["id"]))

    @staticmethod
    def _validated(spec, cls):
        """Round-trip through ``from_dict`` so a hand-built spec is validated like a JSON document."""
        if not isinstance(spec, cls):
            raise TypeError(f"expected {cls.__name__}, got {type(spec).__name__}")
        return cls.from_dict(spec.to_dict())

    # ================================================================== vehicle types
    def save_vehicle_type(self, spec: VehicleTypeSpec) -> int:
        spec = self._validated(spec, VehicleTypeSpec)
        with self._tx():
            return self._upsert("vehicle_type", spec.name, _js(spec.to_dict()))

    def get_vehicle_type(self, key: Key) -> VehicleTypeSpec:
        return self._get("vehicle_type", key)

    def list_vehicle_types(self) -> List[Dict[str, Any]]:
        return self._list("vehicle_type")

    def delete_vehicle_type(self, key: Key) -> None:
        row = self._row("vehicle_type", key)
        used = self.conn.execute("SELECT f.name FROM fleet_vehicle fv JOIN fleet f ON f.id = fv.fleet_id "
                                 "WHERE fv.vehicle_type_id = ? AND f.deleted_at IS NULL", (row["id"],)).fetchall()
        if used:
            raise ValueError(f"loại xe {row['name']!r} đang được dùng bởi fleet {[r[0] for r in used]}")
        with self._tx():
            self._soft_delete("vehicle_type", row["id"])

    # ================================================================== fleets
    def save_fleet(self, spec: FleetSpec) -> int:
        spec = self._validated(spec, FleetSpec)
        errs = Errors()
        type_ids = []
        for i, c in enumerate(spec.composition):
            try:
                type_ids.append(self._row("vehicle_type", c.vehicle_type)["id"])
            except KeyError:
                errs.add(f"composition[{i}].vehicle_type", f"loại xe {c.vehicle_type!r} chưa có trong DB")
        errs.check()
        with self._tx():
            fid = self._upsert("fleet", spec.name, _js(spec.to_dict()))
            self.conn.execute("DELETE FROM fleet_vehicle WHERE fleet_id = ?", (fid,))
            self.conn.executemany("INSERT INTO fleet_vehicle (fleet_id, position, vehicle_type_id, count) "
                                  "VALUES (?, ?, ?, ?)",
                                  [(fid, i, tid, c.count) for i, (tid, c) in enumerate(zip(type_ids,
                                                                                           spec.composition))])
            return fid

    def get_fleet(self, key: Key) -> FleetSpec:
        return self._get("fleet", key)

    def list_fleets(self) -> List[Dict[str, Any]]:
        return self._list("fleet")

    def delete_fleet(self, key: Key) -> None:
        with self._tx():
            self._soft_delete("fleet", key)

    # ================================================================== charging stations
    def save_charging_station(self, spec: ChargingStationSpec) -> int:
        spec = self._validated(spec, ChargingStationSpec)
        with self._tx():
            return self._upsert("charging_station", spec.name, _js(spec.to_dict()))

    def get_charging_station(self, key: Key) -> ChargingStationSpec:
        return self._get("charging_station", key)

    def list_charging_stations(self) -> List[Dict[str, Any]]:
        return self._list("charging_station")

    def delete_charging_station(self, key: Key) -> None:
        with self._tx():
            self._soft_delete("charging_station", key)

    # ================================================================== scenarios
    def save_scenario(self, spec: ScenarioSpec) -> int:
        spec = self._validated(spec, ScenarioSpec)
        with self._tx():
            return self._upsert("scenario", spec.name, _js(spec.to_dict()))

    def get_scenario(self, key: Key) -> ScenarioSpec:
        return self._get("scenario", key)

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return self._list("scenario")

    def delete_scenario(self, key: Key) -> None:
        with self._tx():
            self._soft_delete("scenario", key)

    # ================================================================== policies (versioned)
    def save_policy(self, spec: PolicySpec, name: Optional[str] = None) -> Tuple[int, int]:
        """Create the policy, or add a version if the parameters changed. Returns ``(policy_id, version)``."""
        spec = self._validated(spec, PolicySpec)
        name = name or spec.name or spec.plugin
        with self._tx():
            row = self.conn.execute("SELECT * FROM policy WHERE name = ? AND deleted_at IS NULL", (name,)).fetchone()
            if row is None:
                now = utcnow()
                pid = self.conn.execute("INSERT INTO policy (name, plugin, created_at, updated_at) VALUES (?, ?, ?, ?)",
                                        (name, spec.plugin, now, now)).lastrowid
                return pid, self._insert_version(pid, spec.params)
            if row["plugin"] != spec.plugin:
                raise SpecError([("plugin", f"policy {name!r} đã tồn tại với plugin {row['plugin']!r}")])
            latest = self._latest_version(row["id"])
            if latest is not None and json.loads(latest["params_json"]) == spec.params:
                return row["id"], latest["version"]
            return row["id"], self._insert_version(row["id"], spec.params)

    def add_policy_version(self, key: Key, params: Dict[str, Any]) -> int:
        row = self._row("policy", key)
        PolicySpec.from_dict({"plugin": row["plugin"], "params": params})
        with self._tx():
            return self._insert_version(row["id"], params)

    def _latest_version(self, policy_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM policy_version WHERE policy_id = ? ORDER BY version DESC LIMIT 1",
                                 (policy_id,)).fetchone()

    def _insert_version(self, policy_id: int, params: Dict[str, Any]) -> int:
        latest = self._latest_version(policy_id)
        version = (latest["version"] if latest else 0) + 1
        self.conn.execute("INSERT INTO policy_version (policy_id, version, params_json, created_at) "
                          "VALUES (?, ?, ?, ?)", (policy_id, version, _js(params), utcnow()))
        self.conn.execute("UPDATE policy SET updated_at = ? WHERE id = ?", (utcnow(), policy_id))
        return version

    def _version_row(self, key: Key, version: Optional[int] = None) -> Tuple[sqlite3.Row, sqlite3.Row]:
        prow = self._row("policy", key)
        if version is None:
            vrow = self._latest_version(prow["id"])
        else:
            vrow = self.conn.execute("SELECT * FROM policy_version WHERE policy_id = ? AND version = ?",
                                     (prow["id"], version)).fetchone()
        if vrow is None:
            raise KeyError(f"policy {prow['name']!r} không có phiên bản {version}")
        return prow, vrow

    def get_policy(self, key: Key, version: Optional[int] = None) -> PolicySpec:
        prow, vrow = self._version_row(key, version)
        return PolicySpec(plugin=prow["plugin"], params=json.loads(vrow["params_json"]), name=prow["name"],
                          version=vrow["version"])

    def policy_versions(self, key: Key) -> List[int]:
        pid = self._row("policy", key)["id"]
        return [r[0] for r in self.conn.execute("SELECT version FROM policy_version WHERE policy_id = ? "
                                                "ORDER BY version", (pid,))]

    def list_policies(self) -> List[Dict[str, Any]]:
        rows = self.conn.execute("SELECT p.id, p.name, p.plugin, p.source_kind, p.created_at, p.updated_at, "
                                 "MAX(v.version) AS latest_version FROM policy p "
                                 "JOIN policy_version v ON v.policy_id = p.id WHERE p.deleted_at IS NULL "
                                 "GROUP BY p.id ORDER BY p.id").fetchall()
        return [dict(r) for r in rows]

    def delete_policy(self, key: Key) -> None:
        with self._tx():
            self._soft_delete("policy", key)

    # ================================================================== policy groups
    def save_policy_group(self, spec: PolicyGroupSpec) -> int:
        """References without a version are pinned to the latest version at save time."""
        spec = self._validated(spec, PolicyGroupSpec)
        errs = Errors()
        members, rows = [], []
        for i, m in enumerate(spec.members):
            if isinstance(m.policy, Ref):
                try:
                    prow, vrow = self._version_row(m.policy.ref, m.policy.version)
                except KeyError as e:
                    errs.add(f"members[{i}].policy", str(e.args[0]))
                    continue
                pol = PolicySpec(prow["plugin"], json.loads(vrow["params_json"]))
                member = replace(m, policy=Ref(m.policy.ref, vrow["version"]))
                pv_id = vrow["id"]
            else:
                pol, member, pv_id = m.policy, m, None
            if m.params:
                PolicyGroupMember.parse({"policy": pol.to_dict(), "params": m.params}, f"members[{i}]", errs)
            members.append(member)
            rows.append((i, pv_id, pol.plugin, _js(dict(pol.params, **m.params)), int(m.enabled)))
        errs.check()
        pinned = replace(spec, members=members)
        with self._tx():
            gid = self._upsert("policy_group", spec.name, _js(pinned.to_dict()))
            self.conn.execute("DELETE FROM policy_group_member WHERE group_id = ?", (gid,))
            self.conn.executemany("INSERT INTO policy_group_member (group_id, position, policy_version_id, plugin, "
                                  "params_json, enabled) VALUES (?, ?, ?, ?, ?, ?)",
                                  [(gid,) + r for r in rows])
            return gid

    def get_policy_group(self, key: Key) -> PolicyGroupSpec:
        return self._get("policy_group", key)

    def list_policy_groups(self) -> List[Dict[str, Any]]:
        return self._list("policy_group")

    def delete_policy_group(self, key: Key) -> None:
        with self._tx():
            self._soft_delete("policy_group", key)

    # ================================================================== resolution (NFR-4)
    def resolve(self, spec: RunSpec) -> Tuple[RunSpec, Dict[str, Any]]:
        """Replace every reference by its content. Returns ``(resolved spec, provenance)``.

        The provenance lists the ids / names / policy versions the references resolved to.
        """
        prov: Dict[str, Any] = {}
        errs = Errors()

        def fetch(table, ref, path, label):
            try:
                row = self._row(table, ref)
            except KeyError as e:
                errs.add(path, str(e.args[0]))
                return None
            prov.setdefault(label, []).append({"id": row["id"], "name": row["name"]})
            return SPEC_TABLES[table].from_dict(json.loads(row["spec_json"]))

        scenario = spec.scenario
        if isinstance(scenario, Ref):
            scenario = fetch("scenario", scenario, "scenario", "scenario")
        lists = {}
        for kind, table in (("vehicle_types", "vehicle_type"), ("fleets", "fleet"),
                            ("charging_stations", "charging_station")):
            lists[kind] = [fetch(table, x, f"{kind}[{i}]", kind) if isinstance(x, Ref) else x
                           for i, x in enumerate(getattr(spec, kind))]
        # vehicle types used by stored fleets come along with them
        have = {v.name for v in lists["vehicle_types"] if v is not None}
        for fl in lists["fleets"]:
            for c in (fl.composition if fl is not None else []):
                if c.vehicle_type not in have:
                    vt = fetch("vehicle_type", c.vehicle_type, f"fleets.{fl.name}", "vehicle_types")
                    if vt is not None:
                        lists["vehicle_types"].append(vt)
                        have.add(vt.name)
        group = spec.policy_group
        if isinstance(group, Ref):
            group = fetch("policy_group", group, "policy_group", "policy_group")
        members = []
        for i, m in enumerate(group.members if group is not None else []):
            if isinstance(m.policy, Ref):
                try:
                    pol = self.get_policy(m.policy.ref, m.policy.version)
                except KeyError as e:
                    errs.add(f"policy_group.members[{i}].policy", str(e.args[0]))
                    continue
                pid = self._row("policy", pol.name)["id"] if isinstance(m.policy.ref, str) else m.policy.ref
                prov.setdefault("policies", []).append({"position": i, "policy_id": pid, "name": pol.name,
                                                        "version": pol.version})
                m = replace(m, policy=pol)
            members.append(m)
        errs.check()
        resolved = replace(spec, scenario=scenario, policy_group=replace(group, members=members), **lists)
        resolved = RunSpec.from_dict(resolved.to_dict())    # validates cross references
        return resolved, prov

    # ================================================================== runs (S01-7)
    def create_run(self, spec: RunSpec, source: Optional[RunSpec] = None, provenance: Optional[Dict] = None,
                   kami_version: str = "", status: str = "running") -> int:
        if spec.has_refs():
            raise ValueError("create_run needs a resolved RunSpec (Repository.resolve)")
        prov = provenance or {}
        now = utcnow()
        sid = (prov.get("scenario") or [{}])[0].get("id")
        gid = (prov.get("policy_group") or [{}])[0].get("id")
        cur = self.conn.execute(
            "INSERT INTO run (name, status, run_spec_json, source_spec_json, provenance_json, kami_version, "
            "schema_version, seed, scenario_id, policy_group_id, created_at, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (spec.name, status, _js(spec.to_dict()), _js((source or spec).to_dict()), _js(prov), kami_version,
             SCHEMA_VERSION, spec.effective_seed, sid, gid, now, now if status == "running" else None))
        return cur.lastrowid

    def finish_run(self, run_id: int, status: str, wall_s: Optional[float] = None, events: Optional[int] = None,
                   error: Optional[str] = None) -> None:
        self.conn.execute("UPDATE run SET status = ?, finished_at = ?, wall_s = ?, events = ?, error = ? "
                          "WHERE id = ?", (status, utcnow(), wall_s, events, error, run_id))

    def save_run_metrics(self, run_id: int, metrics: Dict[str, float]) -> None:
        with self._tx():
            self.conn.executemany("INSERT OR REPLACE INTO run_metric_summary (run_id, name, value) VALUES (?, ?, ?)",
                                  [(run_id, k, _num(v)) for k, v in metrics.items()])

    def save_run_timeseries(self, run_id: int, rows: Iterable[Dict[str, float]]) -> None:
        with self._tx():
            self.conn.executemany(
                "INSERT OR REPLACE INTO run_metric_timeseries (run_id, t, name, value) VALUES (?, ?, ?, ?)",
                [(run_id, r["t"], k, _num(v)) for r in rows for k, v in r.items() if k != "t"])

    def add_run_artifact(self, run_id: int, kind: str, path: Union[str, Path], fmt: str,
                         rows: Optional[int] = None) -> int:
        path = Path(path)
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        cur = self.conn.execute("INSERT INTO run_artifact (run_id, kind, path, format, size_bytes, sha256, rows, "
                                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (run_id, kind, str(path), fmt, path.stat().st_size, h.hexdigest(), rows, utcnow()))
        return cur.lastrowid

    def get_run(self, run_id: int) -> Dict[str, Any]:
        row = self.conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"run {run_id} không tồn tại")
        out = dict(row)
        for k in ("run_spec_json", "source_spec_json", "provenance_json"):
            out[k[:-5]] = json.loads(out.pop(k))
        return out

    def run_spec(self, run_id: int) -> RunSpec:
        """The resolved snapshot: re-runnable without any other DB content."""
        return RunSpec.from_dict(self.get_run(run_id)["run_spec"])

    def list_runs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        q = "SELECT id, name, status, seed, created_at, finished_at, wall_s, events FROM run"
        args: Tuple = ()
        if status:
            q, args = q + " WHERE status = ?", (status,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id", args)]

    def run_metrics(self, run_id: int) -> Dict[str, float]:
        return {r["name"]: (math.nan if r["value"] is None else r["value"]) for r in
                self.conn.execute("SELECT name, value FROM run_metric_summary WHERE run_id = ?", (run_id,))}

    def run_timeseries(self, run_id: int) -> List[Dict[str, float]]:
        rows: Dict[float, Dict[str, float]] = {}
        for r in self.conn.execute("SELECT t, name, value FROM run_metric_timeseries WHERE run_id = ? ORDER BY t",
                                   (run_id,)):
            rows.setdefault(r["t"], {"t": r["t"]})[r["name"]] = math.nan if r["value"] is None else r["value"]
        return [rows[t] for t in sorted(rows)]

    def run_artifacts(self, run_id: int) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM run_artifact WHERE run_id = ? ORDER BY id",
                                                   (run_id,))]
