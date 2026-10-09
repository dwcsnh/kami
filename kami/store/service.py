"""Persistence for the optional HTTP service. SQL remains outside the engine/web layer."""
from __future__ import annotations

import json
from contextlib import contextmanager

from kami.config import RunSpec, Ref, SpecError
from kami.config.specs import ScenarioSpec
from kami.store.db import utcnow
from kami.store.repository import Repository, SPEC_TABLES, _js


class Conflict(ValueError):
    """A valid request conflicts with an entity or lifecycle state (HTTP 409)."""


class ServiceRepository(Repository):
    @contextmanager
    def _tx(self):
        if self.conn.in_transaction:
            yield
            return
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def _row(self, table, key, what=None):
        # Library history reads still use Repository; API resolution only sees active rows.
        row = super()._row(table, key, what)
        if row["deleted_at"] is not None:
            raise KeyError(f"{what or table} {key!r} không tồn tại")
        return row

    def entity(self, kind, entity_id):
        row = self._row(kind, entity_id)
        if kind == "scenario":
            template = self.conn.execute("SELECT run_spec_json FROM service_scenario WHERE scenario_id = ?",
                                         (row["id"],)).fetchone()
            if template is None:
                raise KeyError(f"mẫu kịch bản {entity_id} không tồn tại")
            spec = json.loads(template[0])
            spec.pop("policy_group", None)
        else:
            spec = self._get(kind, entity_id).to_dict()
        return {"id": row["id"], "name": row["name"], "spec": spec}

    def entities(self, kind):
        ids = [r["id"] for r in self._list(kind)]
        if kind == "scenario":
            templates = {r[0] for r in self.conn.execute("SELECT scenario_id FROM service_scenario")}
            ids = [i for i in ids if i in templates]
        return [self.entity(kind, i) for i in ids]

    def put_entity(self, kind, spec, entity_id=None):
        scenario = kind == "scenario"
        if scenario and not isinstance(spec.scenario, ScenarioSpec):
            raise SpecError([("scenario", "mẫu kịch bản cần nội dung inline, không phải ref")])
        value = spec.scenario if scenario else spec
        with self._tx():
            previous = self._row(kind, entity_id) if entity_id is not None else None
            duplicate = self.conn.execute(f"SELECT id FROM {kind} WHERE name = ? AND deleted_at IS NULL",
                                          (value.name,)).fetchone()
            if duplicate and (previous is None or duplicate[0] != entity_id):
                raise Conflict(f"tên {value.name!r} đã tồn tại")
            if previous is not None and previous["name"] != value.name:
                if kind == "vehicle_type" and self.conn.execute(
                    "SELECT 1 FROM fleet_vehicle fv JOIN fleet f ON f.id = fv.fleet_id "
                    "WHERE fv.vehicle_type_id = ? AND f.deleted_at IS NULL", (entity_id,)).fetchone():
                    raise Conflict("không đổi tên loại xe đang được fleet sử dụng")
                self.conn.execute(f"UPDATE {kind} SET name = ? WHERE id = ?", (value.name, entity_id))
            if scenario:
                self.resolve(spec)  # validates all active references before saving anything
                saved = self.save_scenario(value)
                self.conn.execute("INSERT OR REPLACE INTO service_scenario VALUES (?, ?)",
                                  (saved, _js(spec.to_dict())))
            else:
                saved = getattr(self, "save_" + kind)(spec)
            return self.entity(kind, saved)

    def remove_entity(self, kind, entity_id):
        with self._tx():
            self.entity(kind, entity_id)
            getattr(self, "delete_" + kind)(entity_id)

    def template(self, entity_id):
        return RunSpec.from_dict(self.entity("scenario", entity_id)["spec"])

    def queue_run(self, source, template_id=None):
        import kami
        from kami.store.runs import _check_output_deps

        with self._tx():
            resolved, provenance = self.resolve(source)
            _check_output_deps(resolved)
            if template_id is not None:
                self.entity("scenario", template_id)
                provenance["scenario"] = [{"id": template_id, "name": resolved.scenario.name}]
            run_id = self.create_run(resolved, source=source, provenance=provenance,
                                     kami_version=kami.__version__, status="queued")
            self.conn.execute("INSERT INTO service_run (run_id, updated_at) VALUES (?, ?)", (run_id, utcnow()))
            return run_id

    def managed(self, run_id):
        self.get_run(run_id)
        row = self.conn.execute("SELECT * FROM service_run WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise Conflict("run không thuộc bộ quản lý service")
        return dict(row)

    def detail(self, run_id):
        result = self.get_run(run_id)
        row = self.conn.execute("SELECT * FROM service_run WHERE run_id = ?", (run_id,)).fetchone()
        result["progress"] = json.loads(row["progress_json"]) if row else {}
        result["error_code"] = row["error_code"] if row else None
        result["managed"] = row is not None
        # Preserve the runnable resolved snapshot, but do not expose legacy policy APIs in input.
        return result

    def claim(self, run_id, owner):
        with self._tx():
            self.managed(run_id)
            if self.get_run(run_id)["status"] != "queued":
                raise Conflict("chỉ bắt đầu được run queued")
            if self.conn.execute("SELECT 1 FROM run WHERE status = 'running'").fetchone():
                raise Conflict("đang có một run running")
            self.conn.execute("UPDATE run SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
                              (utcnow(), run_id))
            self.conn.execute("UPDATE service_run SET owner = ?, error_code = NULL, progress_json = ?, "
                              "updated_at = ? WHERE run_id = ?",
                              (owner, _js({"phase": "loading", "fraction": 0.0, "eta_s": None}), utcnow(), run_id))

    def owns_running(self, run_id, owner):
        row = self.conn.execute("SELECT 1 FROM run r JOIN service_run s ON s.run_id = r.id "
                                "WHERE r.id = ? AND r.status = 'running' AND s.owner = ?", (run_id, owner)).fetchone()
        return row is not None

    def progress(self, run_id, owner, progress):
        self.conn.execute("UPDATE service_run SET progress_json = ?, updated_at = ? WHERE run_id = ? AND owner = ? "
                          "AND EXISTS (SELECT 1 FROM run WHERE id = ? AND status = 'running')",
                          (_js(progress), utcnow(), run_id, owner, run_id))

    def finish(self, run_id, owner, status, error=None, error_code=None, wall_s=None, events=None):
        with self._tx():
            if not self.owns_running(run_id, owner):
                return False
            self.finish_run(run_id, status, wall_s, events, error)
            self.conn.execute("UPDATE service_run SET error_code = ?, updated_at = ? WHERE run_id = ?",
                              (error_code, utcnow(), run_id))
            return True

    def cancel_queued(self, run_id):
        with self._tx():
            self.managed(run_id)
            if self.get_run(run_id)["status"] != "queued":
                raise Conflict("run không còn queued")
            self.finish_run(run_id, "cancelled")

    def recover(self):
        # Caller holds both service and execution locks; no old worker can still execute.
        with self._tx():
            rows = self.conn.execute("SELECT r.id, s.owner FROM run r JOIN service_run s ON r.id = s.run_id "
                                     "WHERE r.status = 'running'").fetchall()
            for row in rows:
                self.finish(row["id"], row["owner"], "failed", "supervisor bị gián đoạn", "interrupted")
            return [r["id"] for r in rows]
