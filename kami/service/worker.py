"""Spawn-safe engine adapter. Uses existing public APIs and never changes engine state."""
from __future__ import annotations

import os
import queue
import threading
import time
import traceback
from pathlib import Path

from kami.config import build_run
from kami.service.locks import FileLock
from kami.service.stream import clean
from kami.store.service import ServiceRepository


def execute_worker(db, artifacts, run_id, owner, execution_lock, messages, lifeline, interval_s):
    stop = threading.Event()

    def watchdog():
        while not stop.is_set():
            try:
                if lifeline.poll(0.1):
                    lifeline.recv()  # EOF means the supervisor has disappeared.
            except (EOFError, OSError):
                os._exit(70)  # release OS locks, SQLite transactions and worker slot

    thread = threading.Thread(target=watchdog, daemon=True)
    thread.start()
    # Bounded IPC must not hold the worker alive after the supervisor has gone.
    messages.cancel_join_thread()
    overflow = False

    def send(kind, data):
        nonlocal overflow
        try:
            if overflow:
                messages.put_nowait(("resync", {"run_id": run_id, "reason": "ipc_overflow"}))
                overflow = False
            messages.put_nowait((kind, clean(data)))
        except queue.Full:
            overflow = True

    repo = None
    try:
        with FileLock(execution_lock):
            repo = ServiceRepository.open(db, migrate_db=False)
            if not repo.owns_running(run_id, owner):
                return  # stale spawn from a supervisor that crashed before hand-off
            spec = repo.run_spec(run_id)
            sim = build_run(spec).simulation()
            clock = time.perf_counter()
            last_emit = -float("inf")
            row_index = 0

            def progress(phase="running"):
                total = max(sim.t_stop - sim.scenario.t_start, 0.0)
                fraction = max(0.0, min(0.999, (sim.t - sim.scenario.t_start) / total)) if total else 0.0
                elapsed = time.perf_counter() - clock
                return {"phase": phase, "simulation_time": sim.t, "scenario_end": sim.scenario.t_end,
                        "stop_time": sim.t_stop, "fraction": fraction,
                        "eta_s": elapsed * (1 - fraction) / fraction if fraction > 0 else None}

            def sample(*_):
                nonlocal last_emit, row_index
                now = time.perf_counter()
                if now - last_emit < interval_s:
                    return
                last_emit = now
                send("progress", progress())
                if sim.timeseries is not None:
                    rows = sim.timeseries.rows
                    while row_index < len(rows):
                        send("metric", {"run_id": run_id, "row": rows[row_index]})
                        row_index += 1

            sim.log.subscribe(sample)
            sim.run()
            last_emit = -float("inf")
            sample()  # include the final sampler row, even for very short simulations
            send("progress", progress("persisting"))
            folder = Path(artifacts) / str(run_id)
            prepared = []
            fmt = spec.outputs.event_log
            if fmt != "none":
                path = folder / ("events.parquet" if fmt == "parquet" else "events.csv.gz")
                sim.log.save(path, fmt)
                prepared.append(("event_log", path, fmt, len(sim.log)))
            if spec.outputs.trajectories == "parquet" and sim.trajectories is not None:
                path = sim.trajectories.save(folder / "trajectories.parquet")
                prepared.append(("trajectories", path, "parquet", len(sim.trajectories)))
            if spec.outputs.replay == "json" and sim.trajectories is not None:
                from kami.replay.cli import export_run
                path = export_run(spec, sim, folder / "replay")
                prepared.append(("replay", path / "manifest.json", "kami.replay", None))
            with repo._tx():
                if not repo.owns_running(run_id, owner):
                    return
                repo.save_run_metrics(run_id, sim.metrics())
                if sim.timeseries is not None:
                    repo.save_run_timeseries(run_id, sim.timeseries.rows)
                for kind, path, fmt, rows in prepared:
                    repo.add_run_artifact(run_id, kind, path, fmt, rows)
                complete = progress("finished")
                complete.update(fraction=1.0, eta_s=0.0)
                repo.progress(run_id, owner, complete)
                repo.finish(run_id, owner, "succeeded", wall_s=sim.wall_time, events=sim.events_processed)
    except BaseException:
        if repo is not None:
            repo.finish(run_id, owner, "failed", traceback.format_exc(), "execution_failed")
    finally:
        if repo is not None:
            repo.close()
        stop.set()
        thread.join(timeout=0.5)
        lifeline.close()
