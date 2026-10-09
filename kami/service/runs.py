"""Run lifecycle and persisted result routes."""
from typing import Any, Optional
from fastapi import Body, Header, Query, Request
from fastapi.responses import StreamingResponse

from kami.config import SpecError
from kami.service.input import public_spec
from kami.service.metrics import compare, require_results, summary
from kami.service.stream import clean, events


def register(app, supervisor, prefix):
    @app.get(prefix + "/runs")
    def listing(status: Optional[str] = None):
        if status is not None and status not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise SpecError([("status", "trạng thái không hợp lệ")])
        with supervisor.repository() as repo:
            return repo.list_runs(status)

    @app.post(prefix + "/runs", status_code=201)
    def create(doc: Any = Body(...)):
        if not isinstance(doc, dict) or set(doc) not in ({"scenario_id"}, {"spec"}):
            raise SpecError([("", "cần đúng một trong scenario_id hoặc spec")])
        with supervisor.repository() as repo:
            template_id = doc.get("scenario_id")
            if "scenario_id" in doc:
                if type(template_id) is not int or template_id < 1:
                    raise SpecError([("scenario_id", "cần số nguyên dương")])
                spec = repo.template(template_id)
            else:
                spec = public_spec(doc["spec"])
            run_id = repo.queue_run(spec, template_id)
            return clean(repo.detail(run_id))

    @app.get(prefix + "/runs/compare")
    def comparison(ids: str = Query(...)):
        try:
            run_ids = [int(i) for i in ids.split(",")]
        except ValueError:
            raise SpecError([("ids", "cần danh sách run id, cách nhau bằng dấu phẩy")]) from None
        if len(run_ids) < 2 or len(run_ids) > 20 or len(set(run_ids)) != len(run_ids) or min(run_ids) < 1:
            raise SpecError([("ids", "cần 2–20 run id dương không trùng")])
        with supervisor.repository() as repo:
            return compare(repo, run_ids)

    @app.get(prefix + "/runs/{run_id}")
    def detail(run_id: int):
        return clean(supervisor.detail(run_id))

    @app.post(prefix + "/runs/{run_id}/start", status_code=202)
    def start(run_id: int):
        return clean(supervisor.start(run_id))

    @app.post(prefix + "/runs/{run_id}/cancel")
    def cancel(run_id: int):
        return clean(supervisor.cancel(run_id))

    @app.get(prefix + "/runs/{run_id}/metrics")
    def metrics(run_id: int):
        with supervisor.repository() as repo:
            return {"run_id": run_id, "summary": summary(repo, run_id)}

    @app.get(prefix + "/runs/{run_id}/timeseries")
    def timeseries(run_id: int):
        with supervisor.repository() as repo:
            require_results(repo, run_id)
            return {"run_id": run_id, "rows": clean(repo.run_timeseries(run_id))}

    @app.get(prefix + "/runs/{run_id}/artifacts")
    def artifacts(run_id: int):
        with supervisor.repository() as repo:
            require_results(repo, run_id)
            return repo.run_artifacts(run_id)

    @app.get(prefix + "/runs/{run_id}/stream")
    async def stream(run_id: int, request: Request, last_event_id: Optional[str] = Header(default=None)):
        supervisor.detail(run_id)  # fail before response headers if missing
        try:
            cursor = int(last_event_id) if last_event_id is not None else 0
            if cursor < 0:
                raise ValueError()
        except ValueError:
            raise SpecError([("Last-Event-ID", "cần số nguyên không âm")]) from None
        return StreamingResponse(events(supervisor, run_id, cursor, request), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
