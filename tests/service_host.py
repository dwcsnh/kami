"""Crash-test host: intentionally killed by test_service_stream, never used in production."""
import json
import sys
import time
from pathlib import Path
from kami.config import RunSpec
from kami.service.supervisor import Supervisor
from tests.service_helpers import document


def main():
    db, artifacts, ready = sys.argv[1:]
    supervisor = Supervisor(db, artifacts, interval_s=0.01).open()
    try:
        with supervisor.repository() as repo:
            run_id = repo.queue_run(RunSpec.from_dict(document(True)))
        supervisor.start(run_id)
        # Do not report readiness until the actual engine emits progress.
        while supervisor.detail(run_id)["progress"].get("simulation_time") is None:
            if supervisor.detail(run_id)["status"] != "running":
                raise RuntimeError("worker stopped before crash test")
            time.sleep(0.01)
        Path(ready).write_text(json.dumps({"run_id": run_id, "pid": supervisor.process.pid}), encoding="utf-8")
        while True:
            time.sleep(0.1)
    finally:
        supervisor.close()


if __name__ == "__main__":
    main()
