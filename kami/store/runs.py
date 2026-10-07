"""Execute and record one run (S01-7).

``execute``: resolve references → snapshot → run record ``running`` → simulate → summary
metrics, time series and event log file → ``succeeded`` (or ``failed`` with the error;
a run is never left ``running``).
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from kami.config import RunSpec, build_run
from kami.eventlog import FORMATS
from kami.store.repository import Repository

EVENT_LOG_FILES = {"parquet": "events.parquet", "csv.gz": "events.csv.gz"}


@dataclass
class RunResult:
    run_id: int
    status: str                       # succeeded | failed
    sim: object = None                # the finished Simulation (None when failed)
    error: Optional[str] = None


def _check_output_deps(spec: RunSpec) -> None:
    if spec.outputs.event_log == "parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError as e:
            from kami.eventlog import PARQUET_HINT

            raise ImportError(PARQUET_HINT) from e


def execute(spec: RunSpec, repo: Repository, artifacts_dir: Union[str, Path] = "runs") -> RunResult:
    """Run ``spec`` and store it. Invalid specs / missing references raise before any record is created."""
    import kami

    resolved, provenance = repo.resolve(spec)
    _check_output_deps(resolved)
    run_id = repo.create_run(resolved, source=spec, provenance=provenance, kami_version=kami.__version__)
    wall = time.perf_counter()
    sim = None
    try:
        sim = build_run(resolved).simulation().run()
        repo.save_run_metrics(run_id, sim.metrics())
        if sim.timeseries is not None:
            repo.save_run_timeseries(run_id, sim.timeseries.rows)
        fmt = resolved.outputs.event_log
        if fmt in FORMATS:
            path = Path(artifacts_dir) / str(run_id) / EVENT_LOG_FILES[fmt]
            sim.log.save(path, fmt)
            repo.add_run_artifact(run_id, "event_log", path, fmt, rows=len(sim.log))
    except Exception:
        err = traceback.format_exc()
        repo.finish_run(run_id, "failed", wall_s=time.perf_counter() - wall,
                        events=getattr(sim, "events_processed", None), error=err)
        return RunResult(run_id, "failed", None, err)
    repo.finish_run(run_id, "succeeded", wall_s=sim.wall_time, events=sim.events_processed)
    return RunResult(run_id, "succeeded", sim)
