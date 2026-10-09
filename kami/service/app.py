"""Optional FastAPI factory; startup owns all process lifecycle and database migration."""
from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kami.config import SpecError
from kami.service import entities, runs
from kami.service.supervisor import Supervisor
from kami.store.service import Conflict


def create_app(db="kami.db", artifacts="runs", interval_s=0.25, history_size=256):
    supervisor = Supervisor(db, artifacts, interval_s, history_size)

    @asynccontextmanager
    async def lifespan(app):
        supervisor.open()
        try:
            yield
        finally:
            supervisor.close()

    app = FastAPI(title="kami simulation service", version="0.2-a", lifespan=lifespan)
    app.state.supervisor = supervisor

    @app.exception_handler(SpecError)
    async def spec_error(request: Request, exc):
        return JSONResponse(status_code=422, content={"errors": [{"path": p, "message": m} for p, m in exc.errors]})

    @app.exception_handler(RequestValidationError)
    async def request_error(request: Request, exc):
        return JSONResponse(status_code=422, content={"errors": [
            {"path": ".".join(str(x) for x in e["loc"] if x != "body"), "message": e["msg"]} for e in exc.errors()]})

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc.args[0])})

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ImportError)
    async def dependency(request: Request, exc):
        return JSONResponse(status_code=422, content={"errors": [{"path": "outputs", "message": str(exc)}]})

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok", "capabilities": {"stage": "A", "max_running": 1,
                "live_metrics": True, "live_vehicle_snapshots": False, "ev": False, "pricing_v2": False,
                "shared_ride_versions": [1]}}

    entities.register(app, supervisor, "/api/v1")
    runs.register(app, supervisor, "/api/v1")
    return app
