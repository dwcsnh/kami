"""CRUD routes around the existing specs and a request-local Repository."""
from typing import Any
from fastapi import Body, Response
from kami.store.repository import SPEC_TABLES
from kami.service.input import finite_json, public_spec
from kami.store.service import Conflict


def register(app, supervisor, prefix):
    for resource, table in (("vehicle-types", "vehicle_type"), ("fleets", "fleet"),
                            ("charging-stations", "charging_station"), ("scenarios", "scenario")):
        _resource(app, supervisor, prefix + "/" + resource, table)


def _resource(app, supervisor, path, table):
    def listing():
        with supervisor.repository() as repo:
            return repo.entities(table)

    def get(entity_id: int):
        with supervisor.repository() as repo:
            return repo.entity(table, entity_id)

    def parse(doc):
        finite_json(doc)
        return public_spec(doc) if table == "scenario" else SPEC_TABLES[table].from_dict(doc)

    def create(doc: Any = Body(...)):
        spec = parse(doc)
        with supervisor.repository() as repo:
            return repo.put_entity(table, spec)

    def update(entity_id: int, doc: Any = Body(...)):
        spec = parse(doc)
        with supervisor.repository() as repo:
            return repo.put_entity(table, spec, entity_id)

    def delete(entity_id: int):
        with supervisor.repository() as repo:
            try:
                repo.remove_entity(table, entity_id)
            except ValueError as exc:
                raise Conflict(str(exc)) from exc
        return Response(status_code=204)

    for route, method, handler, code in ((path, "GET", listing, 200), (path, "POST", create, 201),
                                         (path + "/{entity_id}", "GET", get, 200),
                                         (path + "/{entity_id}", "PUT", update, 200),
                                         (path + "/{entity_id}", "DELETE", delete, 204)):
        app.add_api_route(route, handler, methods=[method], status_code=code, tags=[table],
                          name=method.lower() + "_" + table + ("_one" if "{" in route else ""))
