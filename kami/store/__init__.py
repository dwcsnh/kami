"""Database storage of configurations and runs (sprint 01, SQLite via the standard library).

Never imported by ``kami`` or the engine (NFR-5): the simulator runs as a plain library
without it. Every database access goes through ``Repository``.

    from kami.store import Repository, execute
    repo = Repository.open("kami.db")           # creates / migrates the schema
    result = execute(run_spec, repo, artifacts_dir="runs")
"""
from kami.store.db import connect, current_version, migrate
from kami.store.repository import Repository
from kami.store.runs import RunResult, execute

__all__ = ["connect", "current_version", "migrate", "Repository", "RunResult", "execute"]
